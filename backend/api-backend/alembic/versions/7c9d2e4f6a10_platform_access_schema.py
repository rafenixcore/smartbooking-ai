"""Add platform access, invitations, recovery, audit, and message ledger schema.

Revision ID: 7c9d2e4f6a10
Revises: f5b6ae5f0595
Create Date: 2026-11-09

This is an expand migration. It preserves existing owners and businesses and
backfills their owner membership and onboarding state. The downgrade refuses to
discard live platform data or silently reactivate a suspended owner.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c9d2e4f6a10"
down_revision: Union[str, None] = "f5b6ae5f0595"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # An invited owner supplies only a password. Their name is collected during
    # onboarding, so the existing NOT NULL constraint must be relaxed first.
    op.alter_column("owners", "name", existing_type=sa.String(), nullable=True)
    op.add_column(
        "owners",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "businesses",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """UPDATE businesses
               SET onboarding_completed_at = COALESCE(created_at, now())
               WHERE btrim(name) <> '' AND btrim(phone_number) <> ''"""
        )
    )

    op.create_table(
        "platform_admins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_platform_admins_email_ci", "platform_admins", [sa.text("lower(email)")], unique=True
    )

    op.create_table(
        "platform_admin_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["admin_id"], ["platform_admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_platform_admin_sessions_token_hash"),
    )
    op.create_index("ix_platform_admin_sessions_admin_id", "platform_admin_sessions", ["admin_id"])

    op.create_table(
        "business_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("role IN ('owner', 'member')", name="ck_business_memberships_role"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["owners.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "user_id", name="uq_business_memberships_pair"),
    )
    op.create_index("ix_business_memberships_user_id", "business_memberships", ["user_id"])
    op.create_index(
        "uq_business_memberships_active_owner",
        "business_memberships",
        ["business_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND is_active"),
    )
    op.execute(
        sa.text(
            """INSERT INTO business_memberships (business_id, user_id, role, is_active)
               SELECT id, owner_id, 'owner', true FROM businesses
               WHERE owner_id IS NOT NULL"""
        )
    )

    op.create_table(
        "owner_invitations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column(
            "delivery_status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("invited_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="ck_owner_invitations_status",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'failed')",
            name="ck_owner_invitations_delivery_status",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_admin_id"], ["platform_admins.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_owner_invitations_token_hash"),
    )
    op.create_index(
        "uq_owner_invitations_pending_email_ci",
        "owner_invitations",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_owner_invitations_expires_at", "owner_invitations", ["expires_at"])

    op.create_table(
        "password_resets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("platform_admin_id", sa.Integer(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "(owner_id IS NOT NULL) <> (platform_admin_id IS NOT NULL)",
            name="ck_password_resets_one_principal",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["platform_admin_id"], ["platform_admins.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_resets_token_hash"),
    )
    op.create_index(
        "ix_password_resets_owner_created", "password_resets", ["owner_id", "created_at"]
    )
    op.create_index(
        "ix_password_resets_admin_created", "password_resets", ["platform_admin_id", "created_at"]
    )

    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["admin_id"], ["platform_admins.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_events_created_at", "admin_audit_events", ["created_at"])
    op.create_index(
        "ix_admin_audit_events_entity", "admin_audit_events", ["entity_type", "entity_id"]
    )

    op.create_table(
        "message_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("event_key", sa.String(length=128), nullable=False),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column("provider_event_id", sa.String(), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=8), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound')", name="ck_message_events_direction"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "channel", "event_key", name="uq_message_events_identity"
        ),
    )
    op.create_index(
        "ix_message_events_business_time", "message_events", ["business_id", "occurred_at"]
    )
    op.create_index(
        "ix_message_events_provider_message", "message_events", ["channel", "provider_message_id"]
    )

    op.create_table(
        "message_cost_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("message_event_id", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("rate_version", sa.String(length=64), nullable=True),
        sa.Column("evidence_reference", sa.String(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("amount >= 0", name="ck_message_cost_records_nonnegative"),
        sa.CheckConstraint(
            "source IN ('estimated', 'reconciled')", name="ck_message_cost_records_source"
        ),
        sa.CheckConstraint(
            "(period_start IS NULL AND period_end IS NULL) OR "
            "(period_start IS NOT NULL AND period_end IS NOT NULL AND period_end > period_start)",
            name="ck_message_cost_records_period",
        ),
        sa.CheckConstraint(
            "source <> 'reconciled' OR "
            "(reconciled_at IS NOT NULL AND evidence_reference IS NOT NULL "
            "AND period_start IS NOT NULL)",
            name="ck_message_cost_records_reconciled_evidence",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["message_event_id"], ["message_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id", "idempotency_key", name="uq_message_cost_records_identity"
        ),
    )
    op.create_index(
        "ix_message_cost_records_business_created",
        "message_cost_records",
        ["business_id", "created_at"],
    )
    op.create_index(
        "ix_message_cost_records_business_period",
        "message_cost_records",
        ["business_id", "period_start"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "message_cost_records",
        "message_events",
        "admin_audit_events",
        "password_resets",
        "owner_invitations",
        "platform_admin_sessions",
        "platform_admins",
    ):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError(f"Cannot downgrade: {table} contains platform data")
    if connection.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM owners WHERE name IS NULL OR NOT is_active)")
    ).scalar():
        raise RuntimeError("Cannot downgrade: an owner is incomplete or suspended")
    if connection.execute(
        sa.text(
            """SELECT EXISTS (
                 SELECT 1 FROM business_memberships AS membership
                 LEFT JOIN businesses AS business ON business.id = membership.business_id
                 WHERE business.id IS NULL
                    OR membership.user_id IS DISTINCT FROM business.owner_id
                    OR membership.role <> 'owner'
                    OR NOT membership.is_active
               )"""
        )
    ).scalar():
        raise RuntimeError("Cannot downgrade: business memberships have changed")

    op.drop_table("message_cost_records")
    op.drop_table("message_events")
    op.drop_table("admin_audit_events")
    op.drop_table("password_resets")
    op.drop_table("owner_invitations")
    op.drop_table("business_memberships")
    op.drop_table("platform_admin_sessions")
    op.drop_table("platform_admins")
    op.drop_column("businesses", "onboarding_completed_at")
    op.drop_column("owners", "is_active")
    op.alter_column("owners", "name", existing_type=sa.String(), nullable=False)
