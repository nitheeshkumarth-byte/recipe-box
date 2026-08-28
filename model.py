from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

recipe_tags = db.Table(
    "recipe_tags",
    db.Column("recipe_id", db.Integer, db.ForeignKey("recipe.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)
    origin = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    servings = db.Column(db.Integer, default=4, nullable=False)
    image_filename = db.Column(db.String(200), nullable=True)   # new

    calories = db.Column(db.Integer, nullable=True)
    protein_g = db.Column(db.Integer, nullable=True)
    carbs_g = db.Column(db.Integer, nullable=True)
    fat_g = db.Column(db.Integer, nullable=True)

    tags = db.relationship("Tag", secondary=recipe_tags, backref="recipes")
    ingredient_lines = db.relationship(
        "RecipeIngredient",
        backref="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.id"
    )


class RecipeIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=True)
    name = db.Column(db.String(120), nullable=False)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return self.name