"""Add register number to users

Revision ID: c7f4a2d91e30
Revises: a1b2c3d4e5f6
Create Date: 2026-07-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c7f4a2d91e30"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("register_number", sa.String(length=12), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_users_register_number", ["register_number"]
        )


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_register_number", type_="unique")
        batch_op.drop_column("register_number")
