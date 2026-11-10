"""Persist password reset request limits across workers and restarts.

Revision ID: a6e1c9b4d270
Revises: 7c9d2e4f6a10
Create Date: 2026-11-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6e1c9b4d270"
down_revision: Union[str, None] = "7c9d2e4f6a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_request_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_password_reset_attempts_email_time",
        "password_reset_request_attempts",
        ["email_hash", "created_at"],
    )
    op.create_index(
        "ix_password_reset_attempts_ip_time",
        "password_reset_request_attempts",
        ["ip_hash", "created_at"],
    )
    op.create_index(
        "ix_password_reset_attempts_created_at",
        "password_reset_request_attempts",
        ["created_at"],
    )


def downgrade() -> None:
    # Solo contiene contadores operativos de la última hora, sin credenciales.
    op.drop_index(
        "ix_password_reset_attempts_created_at", table_name="password_reset_request_attempts"
    )
    op.drop_index(
        "ix_password_reset_attempts_ip_time", table_name="password_reset_request_attempts"
    )
    op.drop_index(
        "ix_password_reset_attempts_email_time", table_name="password_reset_request_attempts"
    )
    op.drop_table("password_reset_request_attempts")
