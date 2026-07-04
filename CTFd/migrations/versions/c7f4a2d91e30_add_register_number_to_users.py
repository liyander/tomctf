"""Retain the register-number revision without altering the users table.

Register numbers are stored through CTFd's native user fields so existing
SQLite installations do not require a table alteration.

Revision ID: c7f4a2d91e30
Revises: a1b2c3d4e5f6
Create Date: 2026-07-04 00:00:00.000000
"""

revision = "c7f4a2d91e30"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
