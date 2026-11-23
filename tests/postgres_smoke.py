"""Exercise ownership and row-level security against a disposable PostgreSQL database."""

import os
import time
from urllib.parse import urlsplit

from flask_migrate import check, upgrade
from sqlalchemy import text

database = os.environ["RECIPE_TEST_POSTGRES_URL"]
target = urlsplit(database)
assert target.hostname in {"127.0.0.1", "localhost"} and target.path == "/recipe_box_ci"
os.environ["DATABASE_URL"] = database
os.environ.pop("REDIS_URL", None)

from app import app
from model import db, Recipe

OWNER = "3fcfe498-5ad4-45ad-88c3-bd92c224fa71"
OTHER = "8d2f4b3d-43c2-4f15-8021-17af3315f223"

with app.app_context():
    upgrade()
    check()
    db.session.add(Recipe(title="Other user's recipe", instructions="Read", owner_id=OTHER))
    db.session.commit()
    other_id = Recipe.query.filter_by(owner_id=OTHER).one().id

app.config.update(ACCOUNT_AUTH=True, TESTING=True)
client = app.test_client()
with client.session_transaction() as session:
    session.update(recipe_account_id=OWNER, recipe_account_exp=time.time() + 300, csrf_token="test")
assert client.post("/add", data={
    "csrf_token": "test", "title": "Owner's rice", "instructions": "Cook.",
    "tags": "quick", "ing_name": "Rice", "ing_amount": "1", "ing_unit": "cup",
}).status_code == 302
assert client.get(f"/recipe/{other_id}").status_code == 404
assert client.get("/?q=Rice&tag=quick").status_code == 200

with app.app_context(), db.engine.begin() as connection:
    connection.execute(text("SET LOCAL ROLE recipe_box_runtime"))
    connection.execute(text("SELECT set_config('recipe_box.user_id', :owner, true)"), {"owner": OWNER})
    assert connection.execute(text("SELECT count(*) FROM recipe")).scalar_one() == 1
    assert connection.execute(text("SELECT count(*) FROM recipe WHERE id=:id"), {"id": other_id}).scalar_one() == 0
    assert connection.execute(text("SELECT count(*) FROM recipe_ingredient")).scalar_one() == 1
    assert connection.execute(text("SELECT count(*) FROM audit_event")).scalar_one() == 1
print("PostgreSQL migrations, account boundary, SQL row policies, tags and audit writes passed.")
