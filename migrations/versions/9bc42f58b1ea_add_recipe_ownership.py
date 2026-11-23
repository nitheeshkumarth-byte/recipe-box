"""Add account-owned recipes and timestamped change history."""

import sqlalchemy as sa
from alembic import op

revision = "9bc42f58b1ea"
down_revision = "620d75325bd1"
branch_labels = None
depends_on = None

ACTOR = "nullif(current_setting('recipe_box.user_id', true), '')"
POLICIES = {
    "recipe": f"owner_id = {ACTOR}",
    "recipe_ingredient": "EXISTS (SELECT 1 FROM recipe WHERE recipe.id = recipe_ingredient.recipe_id)",
    "recipe_tags": "EXISTS (SELECT 1 FROM recipe WHERE recipe.id = recipe_tags.recipe_id)",
    "audit_event": f"owner_id = {ACTOR}",
    "chef_session_cache": f"{ACTOR} IS NOT NULL",
}


def upgrade():
    with op.batch_alter_table("recipe") as batch:
        batch.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
        batch.create_index("ix_recipe_owner_id", ["owner_id"])
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("recipe_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_event_owner_id", "audit_event", ["owner_id"])

    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'recipe_box_runtime') THEN
                CREATE ROLE recipe_box_runtime NOLOGIN;
            ELSIF EXISTS (SELECT FROM pg_roles WHERE rolname = 'recipe_box_runtime'
                          AND (rolcanlogin OR rolbypassrls OR rolsuper)) THEN
                RAISE EXCEPTION 'Unsafe existing recipe_box_runtime role';
            END IF;
            EXECUTE format('GRANT recipe_box_runtime TO %I', current_user);
        END
        $$;
    """)
    op.execute("GRANT USAGE ON SCHEMA public TO recipe_box_runtime")
    for table, predicate in POLICIES.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY recipe_box_access ON {table} TO recipe_box_runtime "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
    op.execute("ALTER TABLE tag ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY recipe_box_access ON tag TO recipe_box_runtime USING (true) WITH CHECK (true)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON recipe, recipe_ingredient, recipe_tags, chef_session_cache TO recipe_box_runtime")
    op.execute("GRANT SELECT, INSERT ON tag, audit_event TO recipe_box_runtime")
    op.execute("GRANT USAGE ON SEQUENCE recipe_id_seq, recipe_ingredient_id_seq, tag_id_seq, audit_event_id_seq TO recipe_box_runtime")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table in (*POLICIES, "tag"):
            op.execute(f"DROP POLICY recipe_box_access ON {table}")
            if table != "chef_session_cache":
                op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON recipe, recipe_ingredient, recipe_tags, chef_session_cache, tag, audit_event FROM recipe_box_runtime")
        op.execute("REVOKE USAGE ON SEQUENCE recipe_id_seq, recipe_ingredient_id_seq, tag_id_seq, audit_event_id_seq FROM recipe_box_runtime")
    op.drop_index("ix_audit_event_owner_id", table_name="audit_event")
    op.drop_table("audit_event")
    with op.batch_alter_table("recipe") as batch:
        batch.drop_index("ix_recipe_owner_id")
        batch.drop_column("owner_id")
