"""add chef session cache

Revision ID: 620d75325bd1
Revises: 2ce78e599d64
"""

import sqlalchemy as sa
from alembic import op

revision = "620d75325bd1"
down_revision = "2ce78e599d64"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chef_session_cache",
        sa.Column("session_key", sa.String(64), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_chef_session_cache_expires_at", "chef_session_cache", ["expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE chef_session_cache ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_index("ix_chef_session_cache_expires_at", table_name="chef_session_cache")
    op.drop_table("chef_session_cache")
