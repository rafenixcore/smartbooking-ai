"""Allow multiple tenants to share the Meta WhatsApp account id.

Revision ID: d9f0a1b2c3d4
Revises: c8e3d4f5a601
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d9f0a1b2c3d4"
down_revision: Union[str, None] = "c8e3d4f5a601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_businesses_waba_id", "businesses", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT 1 FROM businesses WHERE waba_id IS NOT NULL "
            "GROUP BY waba_id HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates:
        raise RuntimeError(
            "Cannot restore unique WABA ID constraint while multiple businesses share an account"
        )
    op.create_unique_constraint("uq_businesses_waba_id", "businesses", ["waba_id"])
