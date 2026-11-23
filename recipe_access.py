from uuid import UUID

import click
from flask import g, has_app_context
from sqlalchemy import event, text, update
from sqlalchemy.orm import Session

from model import AuditEvent, Recipe, db


def recipe_query():
    return Recipe.query.filter_by(owner_id=g.get("recipe_user_id"))


def audit(recipe, action):
    if recipe.owner_id:
        db.session.add(AuditEvent(owner_id=recipe.owner_id, recipe_id=recipe.id, action=action))


@event.listens_for(Session, "after_begin")
def scope_postgres(session, transaction, connection):
    if not has_app_context() or connection.dialect.name != "postgresql":
        return
    user_id = g.get("recipe_user_id")
    if user_id:
        connection.execute(text("SET LOCAL ROLE recipe_box_runtime"))
        connection.execute(text("SELECT set_config('recipe_box.user_id', :value, true)"), {"value": user_id})


def register_access_commands(app):
    @app.cli.command("claim-legacy-recipes")
    @click.argument("user_id")
    @click.option("--apply", is_flag=True, help="Assign the existing unowned recipes.")
    def claim_legacy(user_id, apply):
        """Assign the old single-user collection to a verified Auth user UUID."""
        try:
            owner = str(UUID(user_id))
        except ValueError as error:
            raise click.ClickException("Use the user's Supabase Auth UUID.") from error
        count = Recipe.query.filter_by(owner_id=None).count()
        if not apply:
            click.echo(f"{count} unowned recipes. Re-run with --apply after confirming the account UUID.")
            return
        result = db.session.execute(update(Recipe).where(Recipe.owner_id.is_(None)).values(owner_id=owner))
        db.session.commit()
        click.echo(f"Assigned {result.rowcount} recipes.")
