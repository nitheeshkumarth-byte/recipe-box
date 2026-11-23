import argparse
import hashlib
import hmac
import math
import os
import secrets
import time
from contextlib import closing
from functools import lru_cache
from itertools import zip_longest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import boto3
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from botocore.exceptions import BotoCoreError, ClientError
from boto3.exceptions import Boto3Error
from dotenv import load_dotenv
from flask import (
    Flask, Response, abort, flash, g, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from flask_migrate import Migrate, upgrade
from werkzeug.utils import secure_filename
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from model import db, Recipe, Tag, RecipeIngredient
from ai_helper import (
    AIUnavailable, generate_recipe_photo, get_recipe_origin, get_nutrition_estimate, get_recipe_suggestion,
)
from chef_memory import cache_key, load_memory, remember
from chef_rag import answer_question
from chef_vectors import register_vector_commands
from recipe_access import audit, recipe_query, register_access_commands
from recipe_auth import configure_auth, signed_in_user
from recipe_chat import answer_recipe_question
from pwa import pwa_bp
from shared_cache import CacheUnavailable, allow_ai_request, allow_guest_request
from swagger_docs import swagger_bp

load_dotenv()

launch_args = None
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Recipe Box on this computer.")
    parser.add_argument("--configured-services", action="store_true", help="Use the services configured in .env.")
    parser.add_argument("--port", type=int, default=5000)
    launch_args = parser.parse_args()

app = Flask(__name__)
ON_RENDER = os.getenv("RENDER") == "true"
local_development = not ON_RENDER and (
    not launch_args.configured_services if launch_args is not None else os.getenv("RECIPE_BOX_LOCAL") == "1"
)
app.config["LOCAL_DEVELOPMENT"] = local_development
database_url = None if local_development else os.getenv("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///recipes.db"
ACCESS_PASSWORD = None if local_development else os.getenv("RECIPE_BOX_PASSWORD")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_SECURE"] = ON_RENDER
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

S3_BUCKET = os.getenv("S3_BUCKET", "uploads")
S3_PREFIX = os.getenv("S3_PREFIX", "").strip("/")
if S3_PREFIX:
    S3_PREFIX += "/"
IMAGE_BASE_URL = "" if local_development else os.getenv("IMAGE_BASE_URL", "").rstrip("/")
S3_ENDPOINT = None if local_development else os.getenv("S3_ENDPOINT")
LOCAL_UPLOADS = Path(app.instance_path) / "uploads"
MAX_FILE_SIZE = 5 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE + 512 * 1024

IMAGE_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "webp": "image/webp",
}


@lru_cache(maxsize=1)
def storage_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=os.getenv("S3_REGION"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
    )

db.init_app(app)
migrate = Migrate(app, db)
app.register_blueprint(swagger_bp)
app.register_blueprint(pwa_bp)
configure_auth(app)
register_access_commands(app)
register_vector_commands(app)

RECIPES_PER_PAGE = 9


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def editor_password():
    if app.config["ACCOUNT_AUTH"] or ACCESS_PASSWORD or not os.getenv("SECRET_KEY"):
        return None
    return os.getenv("RECIPE_BOX_EDITOR_PASSWORD") or None


def editor_proof(password):
    return hmac.digest(app.secret_key.encode(), b"recipe-box-editor:" + password.encode(), "sha256").hex()


def editor_signed_in():
    password = editor_password()
    return bool(password and session.get("editor_until", 0) > time.time() and
                hmac.compare_digest(session.get("editor_proof", ""), editor_proof(password)))


@app.before_request
def protect_recipe_box():
    if request.endpoint in {
        "health", "ready", "site_styles", "pwa.favicon", "pwa.manifest", "pwa.service_worker", "pwa.offline",
    }:
        return None
    if request.endpoint == "static" and not request.view_args["filename"].startswith("uploads/"):
        return None
    auth_route = request.blueprint == "auth"
    if app.config["ACCOUNT_AUTH"]:
        g.recipe_user_id = signed_in_user()
        if not auth_route and not g.recipe_user_id:
            if request.path.startswith("/api/"):
                return jsonify(success=False, error="Sign in to continue."), 401
            return redirect(url_for("auth.sign_in"))
    elif ACCESS_PASSWORD:
        credentials = request.authorization
        if (
            credentials is None or credentials.type != "basic"
            or credentials.username != "recipebox"
            or not hmac.compare_digest(
                (credentials.password or "").encode(), ACCESS_PASSWORD.encode()
            )
        ):
            return (
                "Recipe Box sign-in required.", 401,
                {"WWW-Authenticate": 'Basic realm="Recipe Box", charset="UTF-8"'},
            )
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return None
    if (ON_RENDER and not app.config["ACCOUNT_AUTH"] and not editor_signed_in()
            and (not ACCESS_PASSWORD or not os.getenv("SECRET_KEY")) and request.endpoint != "editor_sign_in"):
        if request.endpoint == "chef_chat" and os.getenv("SECRET_KEY"):
            g.public_chef = True
        else:
            if editor_password():
                if request.path.startswith("/api/"):
                    return jsonify(success=False, error="Sign in as an editor to use this feature."), 401
                return redirect(url_for("editor_sign_in"), code=303)
            if request.path.startswith("/api/"):
                return jsonify(success=False, error="Recipe Box needs sign-in configured for this feature."), 503
            abort(503, "Configure RECIPE_BOX_PASSWORD and SECRET_KEY to enable writes.")
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
        if request.path.startswith("/api/"):
            return jsonify(success=False, error="Refresh the page and try again."), 400
        abort(400, "The form expired. Refresh the page and try again.")
    return None


def storage_key(filename):
    return S3_PREFIX + filename


def image_url(filename, thumbnail=False):
    return url_for("recipe_image", filename=filename, size="thumb" if thumbnail else None)


def thumbnail_name(filename):
    return f"thumbs/{filename}.webp"


@lru_cache(maxsize=1)
def stylesheet_revision(stylesheet, modified_ns):
    return hashlib.sha256(stylesheet.read_bytes()).hexdigest()[:16]


def current_stylesheet_revision():
    stylesheet = Path(app.static_folder) / "style.css"
    return stylesheet_revision(stylesheet, stylesheet.stat().st_mtime_ns)


@app.get("/static/release/<revision>/style.css")
def site_styles(revision):
    if revision != current_stylesheet_revision():
        abort(404)
    response = send_from_directory(app.static_folder, "style.css", max_age=31_536_000)
    response.cache_control.immutable = True
    return response


@app.context_processor
def template_helpers():
    return {"image_url": image_url, "csrf_token": csrf_token,
            "site_styles_url": lambda: url_for("site_styles", revision=current_stylesheet_revision()),
            "editor_available": bool(editor_password()), "editor_access": editor_signed_in()}


@app.get("/photos/<filename>")
def recipe_image(filename):
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in IMAGE_TYPES or "\\" in filename or Path(filename).name != filename:
        abort(404)

    owner = g.get("recipe_user_id")
    if owner and recipe_query().filter_by(image_filename=filename).first() is None:
        abort(404)
    for directory in (LOCAL_UPLOADS, Path(app.static_folder) / "uploads"):
        if (directory / filename).is_file():
            response = send_from_directory(directory, filename, mimetype=IMAGE_TYPES[extension])
            if owner:
                response.cache_control.private = True
            return response

    if not (S3_ENDPOINT or IMAGE_BASE_URL):
        abort(404)
    if not owner and recipe_query().filter_by(image_filename=filename).first() is None:
        abort(404)
    db.session.rollback()

    if S3_ENDPOINT:
        try:
            candidates = (thumbnail_name(filename), filename) if request.args.get("size") == "thumb" else (filename,)
            if owner and os.getenv("RECIPE_SIGNED_PHOTOS") == "1":
                for candidate in candidates:
                    signed = signed_photo_url(candidate)
                    if signed:
                        return redirect(signed)
            photo = next((found for candidate in candidates if (found := read_stored_photo(candidate))), None)
        except (BotoCoreError, ClientError, Boto3Error) as error:
            app.logger.warning("Recipe photo lookup failed (%s)", type(error).__name__)
            if owner or not IMAGE_BASE_URL:
                abort(503)
        else:
            if photo is not None:
                content_type = image_type(photo[:12])
                if len(photo) > MAX_FILE_SIZE or not content_type:
                    abort(404)
                response = Response(photo, mimetype=content_type)
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.cache_control.private = True
                response.cache_control.max_age = 600
                return response

    if IMAGE_BASE_URL and not owner:
        return redirect(f"{IMAGE_BASE_URL}/{quote(storage_key(filename), safe='/')}")
    abort(404)


def stored_photo(filename, operation):
    client = storage_client()
    keys = dict.fromkeys((storage_key(filename), filename))
    for key in keys:
        try:
            result = getattr(client, operation)(Bucket=S3_BUCKET, Key=key)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status != 404 and error.response.get("Error", {}).get("Code") not in {"NoSuchKey", "404"}:
                raise
            continue
        return key, result
    return None, None


def read_stored_photo(filename):
    _, result = stored_photo(filename, "get_object")
    if result is None:
        return None
    with closing(result["Body"]) as body:
        return body.read(MAX_FILE_SIZE + 1)


def signed_photo_url(filename):
    key, _ = stored_photo(filename, "head_object")
    if key is None:
        return None
    return storage_client().generate_presigned_url(
        "get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=120,
    )


def image_type(header):
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def save_uploaded_image(file):
    if not file or not file.filename:
        return None

    extension = Path(file.filename).suffix.lower().lstrip(".")
    content_type = IMAGE_TYPES.get(extension)
    if not content_type or image_type(file.stream.read(12)) != content_type:
        raise ValueError("Choose a PNG, JPEG, GIF, or WebP image that matches its file extension.")
    file.stream.seek(0, os.SEEK_END)
    if file.stream.tell() > MAX_FILE_SIZE:
        raise ValueError("Photos must be 5 MB or smaller.")
    file.stream.seek(0)

    filename = f"{secrets.token_hex(16)}.{extension}"
    if S3_ENDPOINT:
        try:
            storage_client().upload_fileobj(
                file, S3_BUCKET, storage_key(filename),
                ExtraArgs={"ContentType": content_type},
            )
        except (BotoCoreError, ClientError, Boto3Error):
            delete_image_file(filename)
            raise
    elif ON_RENDER or IMAGE_BASE_URL:
        raise ValueError("Hosted photo uploads require S3_ENDPOINT and storage credentials.")
    else:
        LOCAL_UPLOADS.mkdir(parents=True, exist_ok=True)
        try:
            file.save(LOCAL_UPLOADS / filename)
        except OSError:
            delete_image_file(filename)
            raise
    return filename


def delete_image_file(filename):
    if not filename:
        return
    try:
        if S3_ENDPOINT:
            storage_client().delete_object(Bucket=S3_BUCKET, Key=storage_key(filename))
            if os.getenv("CELERY_BROKER_URL"):
                storage_client().delete_object(Bucket=S3_BUCKET, Key=storage_key(thumbnail_name(filename)))
        elif not ON_RENDER:
            (LOCAL_UPLOADS / Path(filename).name).unlink(missing_ok=True)
    except (BotoCoreError, ClientError, Boto3Error, OSError):
        app.logger.exception("Failed to clean up recipe photo %s", filename)


def read_recipe_form(recipe):
    ingredient_lines = [
        SimpleNamespace(amount=amount or "", unit=unit or "", name=name or "")
        for amount, unit, name in zip_longest(
            request.form.getlist("ing_amount"),
            request.form.getlist("ing_unit"),
            request.form.getlist("ing_name"),
        )
    ]
    return SimpleNamespace(
        title=request.form.get("title", "").strip(),
        instructions=request.form.get("instructions", "").strip(),
        servings=request.form.get("servings", "").strip(),
        tags=request.form.get("tags", ""),
        ingredient_lines=ingredient_lines,
        image_filename=recipe.image_filename if recipe else None,
    )


def validate_recipe_form(form):
    if not form.title or len(form.title) > 120 or not form.instructions:
        raise ValueError("Enter a title of 120 characters or fewer and add cooking instructions.")
    try:
        servings = int(form.servings or "4")
    except ValueError:
        servings = 0
    if not 1 <= servings <= 2_147_483_647:
        raise ValueError("Enter a valid whole number of servings, at least 1.")

    names = list(dict.fromkeys(name for part in form.tags.split(",") if (name := part.strip())))
    if any(len(name) > 50 for name in names):
        raise ValueError("Keep each tag to 50 characters or fewer.")

    ingredients = []
    for row in form.ingredient_lines:
        name = row.name.strip()
        unit = row.unit.strip()
        if not name:
            if row.amount.strip() or unit:
                raise ValueError("Enter a name for each ingredient with an amount or unit.")
            continue
        try:
            amount = float(row.amount.strip() or "0")
        except ValueError:
            raise ValueError("Each ingredient amount must be a number.") from None
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Each ingredient amount must be a finite, non-negative number.")
        if len(name) > 120 or len(unit) > 20:
            raise ValueError("Keep ingredient names to 120 characters and units to 20 characters.")
        ingredients.append(RecipeIngredient(name=name, unit=unit, amount=amount))
    return servings, names, ingredients


def get_or_create_tags(names):
    if not names:
        return []
    insert = postgres_insert if db.engine.dialect.name == "postgresql" else sqlite_insert
    db.session.execute(
        insert(Tag).values([{"name": name} for name in sorted(names)])
        .on_conflict_do_nothing(index_elements=[Tag.name])
    )
    tags = {tag.name: tag for tag in Tag.query.filter(Tag.name.in_(names))}
    return [tags[name] for name in names]


def save_recipe(recipe=None, *, api=False):
    form = read_recipe_form(recipe)
    try:
        servings, names, ingredients = validate_recipe_form(form)
    except ValueError as error:
        if api:
            return jsonify(success=False, error=str(error)), 400
        flash(str(error), "error")
        return render_template("add.html", recipe=recipe, form=form), 400

    new_image = old_image = None
    try:
        new_image = save_uploaded_image(request.files.get("image"))
        if recipe is not None and db.engine.dialect.name == "postgresql":
            # Serialize edits so each replacement cleans up the photo it actually replaced.
            db.session.refresh(recipe, with_for_update=True)
        tags = get_or_create_tags(names)
        if recipe is None:
            saved = Recipe(owner_id=g.get("recipe_user_id"))
            db.session.add(saved)
            saved.ingredient_lines = ingredients
        else:
            saved = recipe
            old_image = saved.image_filename
            if saved.title != form.title:
                saved.origin = None
            old_ingredients = [(row.amount, row.unit or "", row.name) for row in saved.ingredient_lines]
            new_ingredients = [(row.amount, row.unit, row.name) for row in ingredients]
            if old_ingredients != new_ingredients:
                saved.ingredient_lines = ingredients
            if old_ingredients != new_ingredients or saved.servings != servings:
                saved.calories = saved.protein_g = saved.carbs_g = saved.fat_g = None
        saved.title = form.title
        saved.instructions = form.instructions
        saved.servings = servings
        saved.tags = tags
        if new_image:
            saved.image_filename = new_image
        db.session.flush()
        audit(saved, "update" if recipe is not None else "create")
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        delete_image_file(new_image)
        if api:
            return jsonify(success=False, error=str(error)), 400
        flash(str(error), "error")
        return render_template("add.html", recipe=recipe, form=form), 400
    except (SQLAlchemyError, BotoCoreError, ClientError, Boto3Error, OSError):
        db.session.rollback()
        delete_image_file(new_image)
        app.logger.exception("Failed to save recipe")
        if api:
            return jsonify(success=False, error="Could not save the recipe. Please try again."), 503
        flash("Could not save the recipe. Please try again.", "error")
        return render_template("add.html", recipe=recipe, form=form), 503

    if new_image:
        delete_image_file(old_image)
        if S3_ENDPOINT and os.getenv("CELERY_BROKER_URL"):
            from kombu.exceptions import OperationalError
            from tasks import photo_thumbnail
            try:
                photo_thumbnail.apply_async(args=[saved.id, new_image, saved.owner_id], retry=False, expires=3600)
            except OperationalError:
                app.logger.warning("Thumbnail queue unavailable. Original stays available.")
    if api:
        return jsonify(success=True, id=saved.id), 200 if recipe else 201
    flash(f'"{saved.title}" was {"updated" if recipe else "added"}!', "success")
    if recipe:
        return redirect(url_for("view_recipe", recipe_id=saved.id))
    return redirect(url_for("home"))


# --- Routes ----------------------------------------------------------------

@app.get("/healthz")
def health():
    return "", 200


@app.get("/readyz")
def ready():
    try:
        db.session.execute(select(1)).scalar_one()
    except SQLAlchemyError:
        return "", 503
    return "", 200


@app.after_request
def protect_private_responses(response):
    if request.path.startswith(("/api/", "/auth/", "/photos/")) or (
        request.endpoint not in {"static", "site_styles"} and (g.get("recipe_user_id") or editor_signed_in())
    ):
        response.cache_control.private = True
        response.cache_control.no_store = True
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


def rate_limit_ai(*, public_chef=False):
    try:
        allowed = allow_ai_request(g.get("recipe_user_id") or session["csrf_token"])
        if allowed and public_chef:
            allowed = allow_guest_request("chef", limit=60)
    except CacheUnavailable:
        return jsonify(success=False, error="Please try again shortly."), 503
    if not allowed:
        return jsonify(success=False, error="Too many AI requests. Try again in a minute."), 429
    return None


@app.route("/")
def home():
    pagination, search, tag, favorites_only = recipe_collection()
    return render_template(
        "index.html", recipes=pagination.items, pagination=pagination,
        search=search, tag=tag, favorites_only=favorites_only,
    )


def recipe_collection():
    search = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    favorites_only = request.args.get("favorites") == "1"
    page = min(max(request.args.get("page", 1, type=int), 1), 2_147_483_647 // RECIPES_PER_PAGE)

    query = recipe_query()

    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Recipe.title.ilike(pattern),
            Recipe.instructions.ilike(pattern),
            Recipe.tags.any(Tag.name.ilike(pattern)),
            Recipe.ingredient_lines.any(RecipeIngredient.name.ilike(pattern)),
        ))
    if tag:
        query = query.filter(Recipe.tags.any(Tag.name == tag))

    if favorites_only:
        query = query.filter(Recipe.is_favorite == True)

    pagination = query.order_by(Recipe.id.desc()).paginate(
        page=page, per_page=RECIPES_PER_PAGE, error_out=False
    )

    return pagination, search, tag, favorites_only


def recipe_payload(recipe, *, detail=False):
    data = dict(
        id=recipe.id, title=recipe.title, servings=recipe.servings,
        rating=recipe.rating, favorite=recipe.is_favorite, tags=[tag.name for tag in recipe.tags],
        photo=image_url(recipe.image_filename, thumbnail=not detail) if recipe.image_filename else None,
    )
    if detail:
        data.update(
            instructions=recipe.instructions, origin=recipe.origin,
            ingredients=[dict(amount=row.amount, unit=row.unit, name=row.name) for row in recipe.ingredient_lines],
            nutrition=dict(calories=recipe.calories, protein_g=recipe.protein_g, carbs_g=recipe.carbs_g, fat_g=recipe.fat_g),
        )
    return data


@app.get("/api/session")
def api_session():
    return jsonify(csrf_token=csrf_token(), signed_in=bool(g.get("recipe_user_id")),
                   editor_available=bool(editor_password()), editor_signed_in=editor_signed_in())


@app.route("/auth/editor", methods=["GET", "POST"])
def editor_sign_in():
    password = editor_password()
    if not password:
        abort(404)
    if request.method == "GET":
        if editor_signed_in():
            return redirect(url_for("home"))
        return render_template("editor_sign_in.html")
    try:
        if not allow_guest_request("editor-sign-in", limit=12):
            return render_template("editor_sign_in.html", error="Try signing in again in a minute."), 429
    except CacheUnavailable:
        return render_template("editor_sign_in.html", error="Sign-in is temporarily unavailable."), 503
    supplied = request.form.get("password", "")
    if len(supplied) > 1024 or not hmac.compare_digest(supplied.encode(), password.encode()):
        return render_template("editor_sign_in.html", error="The editor password is incorrect."), 401
    session.clear()
    session.update(editor_proof=editor_proof(password), editor_until=int(time.time()) + 8 * 60 * 60)
    return redirect(url_for("home"), code=303)


@app.post("/auth/editor/sign-out")
def editor_sign_out():
    session.clear()
    return redirect(url_for("home"), code=303)


@app.route("/api/recipes", methods=["GET", "POST"])
def api_recipes():
    if request.method == "POST":
        return save_recipe(api=True)
    pagination, _, _, _ = recipe_collection()
    return jsonify(recipes=[recipe_payload(recipe) for recipe in pagination.items],
                   page=pagination.page, pages=pagination.pages, total=pagination.total)


@app.route("/api/recipes/<int:recipe_id>", methods=["GET", "PATCH"])
def api_recipe(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first()
    if recipe is None:
        return jsonify(success=False, error="Recipe not found."), 404
    if request.method == "PATCH":
        return save_recipe(recipe, api=True)
    return jsonify(recipe_payload(recipe, detail=True))


@app.route("/recipe/<int:recipe_id>")
def view_recipe(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()
    return render_template("recipe.html", recipe=recipe)


@app.get("/shopping-list")
def shopping_list():
    return render_template("shopping_list.html")


@app.route("/add", methods=["GET", "POST"])
def add_recipe():
    if request.method == "POST":
        return save_recipe()
    return render_template("add.html", recipe=None)


@app.post("/api/chef-chat")
def chef_chat():
    payload = request.get_json(silent=True)
    question = payload.get("question") if isinstance(payload, dict) else None
    question = question.strip() if isinstance(question, str) else ""
    if not 1 <= len(question) <= 400:
        return jsonify(success=False, error="Enter a question of 400 characters or fewer."), 400

    public_chef = g.get("public_chef", False)
    limited = rate_limit_ai(public_chef=public_chef)
    if limited is not None:
        return limited
    key = cache_key(session["csrf_token"])
    memory_available = True
    try:
        memory = load_memory(key)
    except (SQLAlchemyError, CacheUnavailable):
        db.session.rollback()
        app.logger.warning("Chef session cache unavailable.")
        memory, memory_available = [], False

    page_recipe_id = payload.get("recipe_id")
    if type(page_recipe_id) is not int or not 1 <= page_recipe_id <= 2_147_483_647:
        page_recipe_id = None
    recipe_answer = answer_recipe_question(question, memory, page_recipe_id)
    if recipe_answer is None:
        db.session.rollback()
        use_gemini = not public_chef and os.getenv("CHEF_RAG_PROVIDER", "local").lower() == "gemini"
        answer, _, turn = answer_question(question, memory, use_gemini=use_gemini)
    else:
        answer, turn = recipe_answer
    if turn and memory_available:
        try:
            remember(key, turn)
        except (SQLAlchemyError, CacheUnavailable):
            db.session.rollback()
            memory_available = False
            app.logger.warning("Could not update chef session cache.")
    return jsonify(success=True, answer=answer, memory_available=memory_available)


@app.post("/api/recipe/photo")
def api_recipe_photo():
    payload = request.get_json(silent=True)
    title = payload.get("title") if isinstance(payload, dict) else None
    title = title.strip() if isinstance(title, str) else ""
    if not title or len(title) > 120:
        return jsonify(success=False, error="Enter a recipe title of 120 characters or fewer."), 400

    limited = rate_limit_ai()
    if limited is not None:
        return limited
    try:
        photo, has_reference = generate_recipe_photo(title)
    except AIUnavailable as error:
        return ai_error(error)

    content_type = image_type(photo[:12])
    if not content_type or len(photo) > MAX_FILE_SIZE:
        return ai_error(AIUnavailable("Gemini returned an unsupported photo. Try again or upload one."))
    return Response(photo, mimetype=content_type, headers={
        "X-Recipe-Photo-Reference": "commons" if has_reference else "none",
    })


@app.route("/api/recipe/suggest", methods=["POST"])
def api_recipe_suggest():
    payload = request.get_json(silent=True)
    title = payload.get("title") if isinstance(payload, dict) else None
    title = title.strip() if isinstance(title, str) else ""

    if not title or len(title) > 120:
        return jsonify({"success": False, "error": "Enter a recipe title of 120 characters or fewer."}), 400

    existing = recipe_query().filter(
        db.func.lower(Recipe.title) == title.lower()
    ).first()

    if existing is not None:
        return jsonify({
            "success": False,
            "already_exists": True,
            "title": existing.title,
            "message": f'"{existing.title}" is already in your box.',
        }), 409

    limited = rate_limit_ai()
    if limited is not None:
        return limited
    try:
        result = get_recipe_suggestion(title)
    except AIUnavailable as error:
        return ai_error(error)

    if result is None:
        return jsonify({"success": False, "error": "Couldn't fetch a recipe right now. Try again later."}), 500

    return jsonify({"success": True, "recipe": result})


@app.route("/edit/<int:recipe_id>", methods=["GET", "POST"])
def edit_recipe(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()

    if request.method == "POST":
        return save_recipe(recipe)
    return render_template("add.html", recipe=recipe)


@app.route("/delete/<int:recipe_id>", methods=["POST"])
def delete_recipe(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()
    title = recipe.title
    image_filename = recipe.image_filename
    audit(recipe, "delete")
    db.session.delete(recipe)
    db.session.commit()
    delete_image_file(image_filename)
    flash(f'"{title}" was deleted.', "info")
    return redirect(url_for("home"))


@app.route("/api/delete/<int:recipe_id>", methods=["POST"])
def api_delete_recipe(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()
    image_filename = recipe.image_filename
    audit(recipe, "delete")
    db.session.delete(recipe)
    db.session.commit()
    delete_image_file(image_filename)
    return jsonify({"success": True, "id": recipe_id})


@app.post("/api/recipes/<int:recipe_id>/favorite")
@app.route("/favorite/<int:recipe_id>", methods=["POST"])
def toggle_favorite(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()
    recipe.is_favorite = not recipe.is_favorite
    audit(recipe, "favorite")
    db.session.commit()
    if request.path.startswith("/api/"):
        return jsonify(success=True, favorite=recipe.is_favorite)
    flash(
        f'"{recipe.title}" {"added to" if recipe.is_favorite else "removed from"} favorites.',
        "success"
    )
    return redirect(url_for("view_recipe", recipe_id=recipe.id))


@app.post("/api/recipes/<int:recipe_id>/rating")
@app.route("/rate/<int:recipe_id>", methods=["POST"])
def rate_recipe(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()

    rating = request.form.get("rating", type=int)

    if rating is None or not (1 <= rating <= 5):
        if request.path.startswith("/api/"):
            return jsonify(success=False, error="Rating must be between 1 and 5."), 400
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("view_recipe", recipe_id=recipe.id))

    recipe.rating = rating
    audit(recipe, "rate")
    db.session.commit()
    if request.path.startswith("/api/"):
        return jsonify(success=True, rating=recipe.rating)
    flash(f'Rated "{recipe.title}" {rating} stars.', "success")
    return redirect(url_for("view_recipe", recipe_id=recipe.id))


@app.route("/api/origin/<int:recipe_id>", methods=["POST"])
def api_recipe_origin(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()

    if recipe.origin and recipe.origin != "Unknown origin.":
        return jsonify({"success": True, "origin": recipe.origin})

    limited = rate_limit_ai()
    if limited is not None:
        return limited
    try:
        origin_text = get_recipe_origin(recipe.title)
    except AIUnavailable as error:
        return ai_error(error)
    recipe.origin = origin_text
    db.session.commit()
    return jsonify(success=True, origin=origin_text)


def ai_error(error):
    app.logger.info("Recipe AI unavailable: %s", error)
    return jsonify(success=False, error=str(error)), 503


@app.route("/api/nutrition/<int:recipe_id>", methods=["POST"])
def api_nutrition(recipe_id):
    recipe = recipe_query().filter_by(id=recipe_id).first_or_404()

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

    limited = rate_limit_ai()
    if limited is not None:
        return limited
    try:
        result = get_nutrition_estimate(recipe.ingredient_lines, recipe.servings)
    except AIUnavailable as error:
        return ai_error(error)
    recipe.calories = result["calories"]
    recipe.protein_g = result["protein_g"]
    recipe.carbs_g = result["carbs_g"]
    recipe.fat_g = result["fat_g"]
    db.session.commit()

    return jsonify({
        "success": True,
        "calories": recipe.calories,
        "protein_g": recipe.protein_g,
        "carbs_g": recipe.carbs_g,
        "fat_g": recipe.fat_g,
    })


if launch_args is not None:
    migrations = str(Path(__file__).resolve().parent / "migrations")
    with app.app_context():
        if db.engine.dialect.name == "sqlite":
            upgrade(directory=migrations)
        else:
            try:
                with db.engine.connect() as connection:
                    current = set(MigrationContext.configure(connection).get_current_heads())
            except SQLAlchemyError:
                raise SystemExit("Could not connect to the configured database. Check DATABASE_URL or run python app.py for local development.") from None
            if current != set(ScriptDirectory(migrations).get_heads()):
                raise SystemExit("The configured database is missing Recipe Box migrations. Run python app.py for local development, or apply the release migrations before starting with configured services.")
    app.run(port=launch_args.port)
