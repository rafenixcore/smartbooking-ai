"""Persist owner access revocation after logout.

Revision ID: b7c2f3e4d590
Revises: a6e1c9b4d270
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c2f3e4d590"
down_revision: Union[str, None] = "a6e1c9b4d270"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("owners", sa.Column("access_revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("owners", "access_revoked_at")
