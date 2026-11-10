from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    JSON,
    Time,
    Float,
    Date,
    UniqueConstraint,
    CheckConstraint,
    Index,
    Numeric,
    func,
    text,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base

class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    access_revoked_at = Column(DateTime(timezone=True), nullable=True)
    verification_token = Column(String, nullable=True)
    verification_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    businesses = relationship("Business", back_populates="owner", cascade="all, delete")
    refresh_tokens = relationship(
        "RefreshToken", back_populates="owner", cascade="all, delete-orphan"
    )
    memberships = relationship("BusinessMembership", back_populates="user")
    password_resets = relationship("PasswordReset", back_populates="owner")
    deleted_schedule_exceptions = relationship(
        "ScheduleException",
        back_populates="deleted_by_owner",
        foreign_keys="ScheduleException.deleted_by",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner = relationship("Owner", back_populates="refresh_tokens")


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)  # Business Contact Number
    whatsapp_phone_number_id = Column(String, unique=True, nullable=True)  # Meta Phone Number ID
    waba_id = Column(String, unique=True, nullable=True)  # Meta WhatsApp Business Account ID
    config_json = Column(JSON, nullable=True)  # Config per-tenant (plantilla, políticas, etc.)
    category = Column(String, nullable=True, default="barbershop") # barbershop, medical, spa, etc.
    description = Column(Text, nullable=True)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    daily_notification_enabled = Column(Boolean, default=True)
    timezone = Column(String, nullable=True, default="America/Santo_Domingo")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    telegram_invite_token = Column(String, unique=True, nullable=True, index=True)
    telegram_first_contact_at = Column(DateTime(timezone=True), nullable=True)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)

    owner_id = Column(Integer, ForeignKey("owners.id"))
    owner = relationship("Owner", back_populates="businesses")

    services = relationship("Service", back_populates="business", cascade="all, delete")
    customers = relationship("Customer", back_populates="business", cascade="all, delete")
    appointments = relationship("Appointment", back_populates="business", cascade="all, delete")
    waitlist_entries = relationship("WaitlistEntry", back_populates="business", cascade="all, delete")
    conversation_states = relationship("ConversationState", back_populates="business", cascade="all, delete")
    schedule_rules = relationship("ScheduleRule", back_populates="business", cascade="all, delete")
    time_blocks = relationship("TimeBlock", back_populates="business", cascade="all, delete")
    schedule_exceptions = relationship("ScheduleException", back_populates="business", cascade="all, delete")
    processed_channel_events = relationship(
        "ProcessedChannelEvent", back_populates="business", cascade="all, delete"
    )
    owner_channel_bindings = relationship(
        "OwnerChannelBinding", back_populates="business", cascade="all, delete"
    )
    telegram_user_bindings = relationship(
        "TelegramUserBinding", back_populates="business", cascade="all, delete"
    )
    memberships = relationship("BusinessMembership", back_populates="business")
    message_events = relationship("MessageEvent", back_populates="business")
    message_cost_records = relationship("MessageCostRecord", back_populates="business")


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        Index("uq_platform_admins_email_ci", func.lower(email), unique=True),
    )

    sessions = relationship("PlatformAdminSession", back_populates="admin")
    invitations = relationship("OwnerInvitation", back_populates="invited_by_admin")
    password_resets = relationship("PasswordReset", back_populates="platform_admin")
    audit_events = relationship("AdminAuditEvent", back_populates="admin")


class PlatformAdminSession(Base):
    __tablename__ = "platform_admin_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_platform_admin_sessions_token_hash"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id = Column(
        Integer, ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    admin = relationship("PlatformAdmin", back_populates="sessions")


class PlatformLoginAttempt(Base):
    __tablename__ = "platform_login_attempts"
    __table_args__ = (
        Index("ix_platform_login_attempts_email_time", "email_hash", "created_at"),
        Index("ix_platform_login_attempts_ip_time", "ip_hash", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email_hash = Column(String(64), nullable=False)
    ip_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BusinessMembership(Base):
    __tablename__ = "business_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member')", name="ck_business_memberships_role"),
        UniqueConstraint("business_id", "user_id", name="uq_business_memberships_pair"),
        Index(
            "uq_business_memberships_active_owner",
            "business_id",
            unique=True,
            postgresql_where=text("role = 'owner' AND is_active"),
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    business_id = Column(
        Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("owners.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role = Column(String(32), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    business = relationship("Business", back_populates="memberships")
    user = relationship("Owner", back_populates="memberships")


class OwnerInvitation(Base):
    __tablename__ = "owner_invitations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False)
    token_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, server_default="pending")
    delivery_status = Column(String(20), nullable=False, server_default="pending")
    invited_by_admin_id = Column(
        Integer, ForeignKey("platform_admins.id", ondelete="RESTRICT"), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="ck_owner_invitations_status",
        ),
        CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'failed')",
            name="ck_owner_invitations_delivery_status",
        ),
        UniqueConstraint("token_hash", name="uq_owner_invitations_token_hash"),
        Index(
            "uq_owner_invitations_pending_email_ci",
            func.lower(email),
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    invited_by_admin = relationship("PlatformAdmin", back_populates="invitations")


class PasswordReset(Base):
    __tablename__ = "password_resets"
    __table_args__ = (
        CheckConstraint(
            "(owner_id IS NOT NULL) <> (platform_admin_id IS NOT NULL)",
            name="ck_password_resets_one_principal",
        ),
        UniqueConstraint("token_hash", name="uq_password_resets_token_hash"),
        Index("ix_password_resets_owner_created", "owner_id", "created_at"),
        Index("ix_password_resets_admin_created", "platform_admin_id", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=True)
    platform_admin_id = Column(
        Integer, ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=True
    )
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    owner = relationship("Owner", back_populates="password_resets")
    platform_admin = relationship("PlatformAdmin", back_populates="password_resets")


class PasswordResetRequestAttempt(Base):
    __tablename__ = "password_reset_request_attempts"
    __table_args__ = (
        Index("ix_password_reset_attempts_email_time", "email_hash", "created_at"),
        Index("ix_password_reset_attempts_ip_time", "ip_hash", "created_at"),
        Index("ix_password_reset_attempts_created_at", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email_hash = Column(String(64), nullable=False)
    ip_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"
    __table_args__ = (
        Index("ix_admin_audit_events_entity", "entity_type", "entity_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id = Column(
        Integer, ForeignKey("platform_admins.id", ondelete="RESTRICT"), nullable=False
    )
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    outcome = Column(String(32), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    admin = relationship("PlatformAdmin", back_populates="audit_events")


class MessageEvent(Base):
    __tablename__ = "message_events"
    __table_args__ = (
        CheckConstraint("direction IN ('inbound', 'outbound')", name="ck_message_events_direction"),
        UniqueConstraint("business_id", "channel", "event_key", name="uq_message_events_identity"),
        Index("ix_message_events_business_time", "business_id", "occurred_at"),
        Index("ix_message_events_provider_message", "channel", "provider_message_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False)
    channel = Column(String(32), nullable=False)
    event_key = Column(String(128), nullable=False)
    provider_message_id = Column(String, nullable=True)
    provider_event_id = Column(String, nullable=True)
    direction = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False)
    category = Column(String(32), nullable=True)
    country = Column(String(8), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    business = relationship("Business", back_populates="message_events")
    cost_records = relationship("MessageCostRecord", back_populates="message_event")


class MessageCostRecord(Base):
    __tablename__ = "message_cost_records"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_message_cost_records_nonnegative"),
        CheckConstraint(
            "source IN ('estimated', 'reconciled')", name="ck_message_cost_records_source"
        ),
        CheckConstraint(
            "(period_start IS NULL AND period_end IS NULL) OR "
            "(period_start IS NOT NULL AND period_end IS NOT NULL AND period_end > period_start)",
            name="ck_message_cost_records_period",
        ),
        CheckConstraint(
            "source <> 'reconciled' OR "
            "(reconciled_at IS NOT NULL AND evidence_reference IS NOT NULL "
            "AND period_start IS NOT NULL)",
            name="ck_message_cost_records_reconciled_evidence",
        ),
        UniqueConstraint("business_id", "idempotency_key", name="uq_message_cost_records_identity"),
        Index("ix_message_cost_records_business_created", "business_id", "created_at"),
        Index("ix_message_cost_records_business_period", "business_id", "period_start"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False)
    message_event_id = Column(
        BigInteger, ForeignKey("message_events.id", ondelete="RESTRICT"), nullable=True
    )
    idempotency_key = Column(String(128), nullable=False)
    amount = Column(Numeric(14, 6), nullable=False)
    currency = Column(String(3), nullable=False)
    source = Column(String(16), nullable=False)
    rate_version = Column(String(64), nullable=True)
    evidence_reference = Column(String, nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    business = relationship("Business", back_populates="message_cost_records")
    message_event = relationship("MessageEvent", back_populates="cost_records")


class TelegramUserBinding(Base):
    __tablename__ = "telegram_user_bindings"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(String, unique=True, index=True, nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    business = relationship("Business", back_populates="telegram_user_bindings")


class OwnerChannelBinding(Base):
    __tablename__ = "owner_channel_bindings"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "channel_user_id",
            name="uq_owner_channel_bindings_channel_user",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(32), nullable=False, index=True)
    channel_user_id = Column(String, nullable=True, index=True)
    role = Column(String(32), nullable=False, default="owner")
    is_active = Column(Boolean, default=False, nullable=False)
    activation_token = Column(String(64), unique=True, nullable=True, index=True)
    activation_expires_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    business = relationship("Business", back_populates="owner_channel_bindings")
    owner = relationship("Owner")


class ScheduleRule(Base):
    __tablename__ = "schedule_rules"

    id = Column(Integer, primary_key=True, index=True)
    day_of_week = Column(Integer, nullable=False) # 0: Monday, 6: Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_available = Column(Boolean, default=True)

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="schedule_rules")

class TimeBlock(Base):
    __tablename__ = "time_blocks"

    id = Column(Integer, primary_key=True, index=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String, nullable=True)

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="time_blocks")


class ScheduleException(Base):
    __tablename__ = "schedule_exceptions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    type = Column(String, nullable=False)  # block | open
    all_day = Column(Boolean, default=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc),
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    business = relationship("Business", back_populates="schedule_exceptions")

    deleted_by = Column(Integer, ForeignKey("owners.id"), nullable=True)
    deleted_by_owner = relationship(
        "Owner", back_populates="deleted_schedule_exceptions", foreign_keys=[deleted_by]
    )

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    buffer_minutes = Column(Integer, nullable=False, default=0)
    price = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, default=True)

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="services")

    appointments = relationship("Appointment", back_populates="service")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True) # Sometimes we just have the phone
    phone_number = Column(String, index=True, nullable=False)
    
    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="customers")

    appointments = relationship("Appointment", back_populates="customer", cascade="all, delete")
    waitlist_entries = relationship("WaitlistEntry", back_populates="customer", cascade="all, delete")

class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("service_id", "date", name="uq_appointment_service_datetime"),
    )

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="P") # P: Pending, C: Confirmed, A: Canceled, D: Done
    reminder_24h_sent = Column(Boolean, default=False)
    reminder_2h_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="appointments")

    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer = relationship("Customer", back_populates="appointments")

    service_id = Column(Integer, ForeignKey("services.id"))
    service = relationship("Service", back_populates="appointments")

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="waiting") # waiting, notified, expired, booked

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="waitlist_entries")

    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer = relationship("Customer", back_populates="waitlist_entries")

class ConversationState(Base):
    __tablename__ = "conversation_states"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, index=True, nullable=False)
    context_data = Column(JSON, default=dict)
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc), default=lambda: datetime.now(timezone.utc))

    business_id = Column(Integer, ForeignKey("businesses.id"))
    business = relationship("Business", back_populates="conversation_states")


class ProcessedChannelEvent(Base):
    __tablename__ = "processed_channel_events"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "business_id",
            "user_key",
            "event_id",
            name="uq_processed_channel_events_identity",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(32), nullable=False, index=True)
    user_key = Column(String, nullable=False, index=True)
    event_id = Column(String, nullable=False)
    processed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    business = relationship("Business", back_populates="processed_channel_events")
