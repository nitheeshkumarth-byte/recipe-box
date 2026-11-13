import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from sqlalchemy import or_
from model import db, Recipe, Tag, RecipeIngredient
from ai_helper import get_recipe_origin, get_nutrition_estimate, get_recipe_from_web
from swagger_docs import swagger_bp

load_dotenv()

app = Flask(__name__)
database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///recipes.db"
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key-change-me")

# Photos live in Supabase Storage (S3-compatible); Render's disk is wiped on deploy.
S3_BUCKET = os.environ.get("S3_BUCKET", "uploads")
S3_PREFIX = os.environ.get("S3_PREFIX", "")  # e.g. "uploads/" if photos sit in a folder
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ.get("S3_ENDPOINT"),
    region_name=os.environ.get("S3_REGION"),
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
    aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

db.init_app(app)
migrate = Migrate(app, db)
app.register_blueprint(swagger_bp)

RECIPES_PER_PAGE = 9


# --- Helpers -------------------------------------------------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file):
    """Validates and saves an uploaded image file. Returns the saved
    filename, or None if no file was provided, or the string "INVALID"
    if a file was given but rejected (invalid type / too large)."""
    if not file or file.filename == "":
        return None

    if not allowed_file(file.filename):
        flash("Image must be a png, jpg, jpeg, gif, or webp file.", "error")
        return "INVALID"

    filename = secure_filename(file.filename)
    unique_filename = f"{os.urandom(8).hex()}_{filename}"

    try:
        s3.upload_fileobj(
            file, S3_BUCKET, S3_PREFIX + unique_filename,
            ExtraArgs={"ContentType": file.mimetype or "application/octet-stream"},
        )
    except (BotoCoreError, ClientError):
        flash("Could not upload the image. Please try again.", "error")
        return "INVALID"

    return unique_filename


def delete_image_file(filename):
    """Deletes an uploaded image from storage, ignoring failures."""
    if not filename:
        return
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=S3_PREFIX + filename)
    except (BotoCoreError, ClientError):
        pass


@app.context_processor
def image_helpers():
    return {"image_url": lambda filename: f"{IMAGE_BASE_URL}/{S3_PREFIX}{filename}"}

def get_or_create_tags(tag_string):
    """Takes 'dinner, quick, veg' and returns a list of Tag objects,
    reusing existing tags and creating new ones as needed."""
    tag_names = [t.strip() for t in tag_string.split(",") if t.strip()]
    tags = []
    for name in tag_names:
        tag = Tag.query.filter_by(name=name).first()
        if tag is None:
            tag = Tag(name=name)
            db.session.add(tag)
        tags.append(tag)
    return tags


def parse_ingredients_from_form():
    """Reads parallel lists of amount/unit/name submitted from the form
    and returns a list of RecipeIngredient objects (not yet saved)."""
    amounts = request.form.getlist("ing_amount")
    units = request.form.getlist("ing_unit")
    names = request.form.getlist("ing_name")

    ingredients = []
    for amount, unit, name in zip(amounts, units, names):
        name = name.strip()
        if not name:
            continue
        ingredients.append(RecipeIngredient(
            amount=float(amount) if amount.strip() else 0,
            unit=unit.strip(),
            name=name
        ))
    return ingredients


# --- Routes ----------------------------------------------------------------

@app.route("/")
def home():
    search = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    favorites_only = request.args.get("favorites") == "1"
    page = request.args.get("page", 1, type=int)

    query = Recipe.query

    if search:
        pattern = f"%{search}%"
        query = query.outerjoin(Recipe.tags).outerjoin(
            Recipe.ingredient_lines
        ).filter(or_(
            Recipe.title.ilike(pattern),
            Recipe.instructions.ilike(pattern),
            Tag.name.ilike(pattern),
            RecipeIngredient.name.ilike(pattern),
        ))
        if tag:
            query = query.filter(Tag.name == tag)
        query = query.distinct()

    elif tag:
        query = query.join(Recipe.tags).filter(Tag.name == tag)

    if favorites_only:
        query = query.filter(Recipe.is_favorite == True)

    pagination = query.order_by(Recipe.id.desc()).paginate(
        page=page, per_page=RECIPES_PER_PAGE, error_out=False
    )

    return render_template(
        "index.html",
        recipes=pagination.items,
        pagination=pagination,
        search=search,
        tag=tag,
        favorites_only=favorites_only,
    )


@app.route("/recipe/<int:recipe_id>")
def view_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template("recipe.html", recipe=recipe)


@app.route("/add", methods=["GET", "POST"])
def add_recipe():
    if request.method == "POST":
        image_filename = save_uploaded_image(request.files.get("image"))
        if image_filename == "INVALID":
            return render_template("add.html", recipe=None)

        new_recipe = Recipe(
            title=request.form["title"],
            instructions=request.form["instructions"],
            servings=request.form.get("servings", type=int) or 4,
            tags=get_or_create_tags(request.form.get("tags", "")),
            ingredient_lines=parse_ingredients_from_form(),
            image_filename=image_filename
        )
        db.session.add(new_recipe)
        db.session.commit()
        flash(f'"{new_recipe.title}" was added!', "success")
        return redirect(url_for("home"))

    return render_template("add.html", recipe=None)


@app.route("/api/recipe/suggest", methods=["POST"])
def api_recipe_suggest():
    title = request.get_json(silent=True) or {}
    title = (title.get("title") or "").strip()

    if not title:
        return jsonify({"success": False, "error": "Please enter a recipe title first."}), 400

    existing = Recipe.query.filter(
        Recipe.title.ilike(f"%{title}%")
    ).first()

    if existing is not None:
        return jsonify({
            "success": False,
            "already_exists": True,
            "title": existing.title,
            "message": f'"{existing.title}" is already in your box.',
        }), 409

    result = get_recipe_from_web(title)

    if result is None:
        return jsonify({"success": False, "error": "Couldn't fetch a recipe right now. Try again later."}), 500

    return jsonify({"success": True, "recipe": result})


@app.route("/edit/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)

    if request.method == "POST":
        recipe.title = request.form["title"]
        recipe.instructions = request.form["instructions"]
        recipe.servings = request.form.get("servings", type=int) or 4
        recipe.tags = get_or_create_tags(request.form.get("tags", ""))
        recipe.ingredient_lines = parse_ingredients_from_form()

        new_image = save_uploaded_image(request.files.get("image"))
        if new_image == "INVALID":
            return render_template("add.html", recipe=recipe)
        if new_image:
            delete_image_file(recipe.image_filename)
            recipe.image_filename = new_image

        # Ingredients changed — clear cached nutrition so it gets recalculated
        recipe.calories = None
        recipe.protein_g = None
        recipe.carbs_g = None
        recipe.fat_g = None

        db.session.commit()
        flash(f'"{recipe.title}" was updated!', "success")
        return redirect(url_for("view_recipe", recipe_id=recipe.id))

    return render_template("add.html", recipe=recipe)


@app.route("/delete/<int:recipe_id>", methods=["POST"])
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    title = recipe.title
    image_filename = recipe.image_filename
    db.session.delete(recipe)
    db.session.commit()
    delete_image_file(image_filename)
    flash(f'"{title}" was deleted.', "info")
    return redirect(url_for("home"))


@app.route("/api/delete/<int:recipe_id>", methods=["POST"])
def api_delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    image_filename = recipe.image_filename
    db.session.delete(recipe)
    db.session.commit()
    delete_image_file(image_filename)
    return jsonify({"success": True, "id": recipe_id})


@app.route("/favorite/<int:recipe_id>", methods=["POST"])
def toggle_favorite(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.is_favorite = not recipe.is_favorite
    db.session.commit()
    flash(
        f'"{recipe.title}" {"added to" if recipe.is_favorite else "removed from"} favorites.',
        "success"
    )
    return redirect(request.referrer or url_for("home"))


@app.route("/rate/<int:recipe_id>", methods=["POST"])
def rate_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)

    rating = request.form.get("rating", type=int)

    if rating is None or not (1 <= rating <= 5):
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("view_recipe", recipe_id=recipe.id))

    recipe.rating = rating
    db.session.commit()
    flash(f'Rated "{recipe.title}" {rating} stars.', "success")
    return redirect(url_for("view_recipe", recipe_id=recipe.id))


@app.route("/api/origin/<int:recipe_id>", methods=["POST"])
def api_recipe_origin(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)

    if recipe.origin:
        return jsonify({"success": True, "origin": recipe.origin})

    try:
        origin_text = get_recipe_origin(recipe.title)
        recipe.origin = origin_text
        db.session.commit()
        return jsonify({"success": True, "origin": origin_text})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/nutrition/<int:recipe_id>", methods=["POST"])
def api_nutrition(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)

    if recipe.calories is not None:
        return jsonify({
            "success": True,
            "calories": recipe.calories,
            "protein_g": recipe.protein_g,
            "carbs_g": recipe.carbs_g,
            "fat_g": recipe.fat_g,
        })

    if not recipe.ingredient_lines:
        return jsonify({"success": False, "error": "No ingredients to estimate from."}), 400

    result = get_nutrition_estimate(recipe.ingredient_lines, recipe.servings)

    if result is None:
        return jsonify({"success": False, "error": "Couldn't estimate nutrition right now."}), 500

    recipe.calories = result.get("calories", 0)
    recipe.protein_g = result.get("protein_g", 0)
    recipe.carbs_g = result.get("carbs_g", 0)
    recipe.fat_g = result.get("fat_g", 0)
    db.session.commit()

    return jsonify({
        "success": True,
        "calories": recipe.calories,
        "protein_g": recipe.protein_g,
        "carbs_g": recipe.carbs_g,
        "fat_g": recipe.fat_g,
    })


if __name__ == "__main__":
    app.run(debug=True)
