"""Persistent sequential cursors for dataset-backed camera simulation.

Revision ID: b421dc54ea90
Revises: 94e907c533d0
"""
from alembic import op
import sqlalchemy as sa

revision = "b421dc54ea90"
down_revision = "94e907c533d0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "camera_simulation_cursors",
        sa.Column("scope", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("camera_simulation_cursors")
