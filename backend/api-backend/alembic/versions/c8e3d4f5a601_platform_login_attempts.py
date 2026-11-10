"""Persist failed platform administrator login attempts.

Revision ID: c8e3d4f5a601
Revises: b7c2f3e4d590
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e3d4f5a601"
down_revision: Union[str, None] = "b7c2f3e4d590"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_login_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_platform_login_attempts_email_time", "platform_login_attempts", ["email_hash", "created_at"]
    )
    op.create_index(
        "ix_platform_login_attempts_ip_time", "platform_login_attempts", ["ip_hash", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_platform_login_attempts_ip_time", table_name="platform_login_attempts")
    op.drop_index("ix_platform_login_attempts_email_time", table_name="platform_login_attempts")
    op.drop_table("platform_login_attempts")
