"""Add difficulty column to Challenges

Revision ID: a1b2c3d4e5f6
Revises: f73a96c97449
Create Date: 2026-02-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "67ebab6de598"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "challenges", sa.Column("difficulty", sa.String(length=20), nullable=True)
    )


def downgrade():
    op.drop_column("challenges", "difficulty")
