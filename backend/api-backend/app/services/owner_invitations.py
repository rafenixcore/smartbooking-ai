"""Ciclo de vida de invitaciones de dueños; el token plano nunca se persiste."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models import AdminAuditEvent, Owner, OwnerInvitation, PlatformAdmin
from app.services.admin_audit import new_admin_audit_event


INVITATION_TTL = timedelta(hours=72)


class InvitationError(Exception):
    """Error de dominio sin incluir correos, tokens ni otros secretos."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if not normalized or "@" not in normalized or any(character.isspace() for character in normalized):
        raise InvitationError("invalid_email")
    return normalized


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _lock_email(db: AsyncSession, email: str) -> None:
    # El índice único es la última defensa; el advisory lock permite responder
    # con un error de dominio limpio ante dos invitaciones concurrentes.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:email, 0))"),
        {"email": email},
    )


def _audit(admin_id: int, action: str, invitation_id: int) -> AdminAuditEvent:
    return new_admin_audit_event(
        admin_id=admin_id,
        action=f"owner_invitation.{action}",
        entity_type="owner_invitation",
        entity_id=invitation_id,
        outcome="success",
    )


async def create_invitation(
    db: AsyncSession, email: str, invited_by_admin_id: int
) -> tuple[OwnerInvitation, str]:
    normalized_email = _normalize_email(email)
    admin = await db.get(PlatformAdmin, invited_by_admin_id)
    if admin is None or not admin.is_active:
        raise InvitationError("admin_unavailable")

    await _lock_email(db, normalized_email)
    owner = await db.scalar(
        select(Owner.id).where(func.lower(Owner.email) == normalized_email)
    )
    if owner is not None:
        raise InvitationError("owner_exists")
    now = datetime.now(timezone.utc)
    pending_rows = await db.scalars(
        select(OwnerInvitation)
        .where(
            func.lower(OwnerInvitation.email) == normalized_email,
            OwnerInvitation.status == "pending",
        )
        .with_for_update()
    )
    active_pending = False
    for previous in pending_rows:
        if previous.expires_at > now:
            active_pending = True
        else:
            previous.status = "expired"
    if active_pending:
        raise InvitationError("invitation_pending")
    await db.flush()

    token = _new_token()
    invitation = OwnerInvitation(
        email=normalized_email,
        token_hash=_token_hash(token),
        status="pending",
        delivery_status="pending",
        invited_by_admin_id=invited_by_admin_id,
        expires_at=now + INVITATION_TTL,
    )
    db.add(invitation)
    try:
        await db.flush()
        db.add(_audit(invited_by_admin_id, "create", invitation.id))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise InvitationError("invitation_pending") from exc
    await db.refresh(invitation)
    return invitation, token


async def resend_invitation(
    db: AsyncSession, invitation_id: int, admin_id: int
) -> str:
    preview = await db.get(OwnerInvitation, invitation_id)
    if preview is None:
        raise InvitationError("not_found")
    # Mantener el mismo orden de bloqueos que create_invitation para evitar
    # interbloqueos entre creación y reenvío para el mismo correo.
    await _lock_email(db, preview.email.casefold())
    invitation = await db.scalar(
        select(OwnerInvitation)
        .where(OwnerInvitation.id == invitation_id)
        .with_for_update()
    )
    if invitation is None:
        raise InvitationError("not_found")
    if invitation.status in {"accepted", "revoked"}:
        raise InvitationError("invalid_state")
    owner_exists = await db.scalar(
        select(Owner.id).where(func.lower(Owner.email) == invitation.email.casefold())
    )
    if owner_exists is not None:
        raise InvitationError("owner_exists")
    pending_elsewhere = await db.scalar(
        select(OwnerInvitation.id).where(
            func.lower(OwnerInvitation.email) == invitation.email.casefold(),
            OwnerInvitation.status == "pending",
            OwnerInvitation.id != invitation.id,
        )
    )
    if pending_elsewhere is not None:
        raise InvitationError("invitation_pending")

    token = _new_token()
    invitation.token_hash = _token_hash(token)
    invitation.status = "pending"
    invitation.delivery_status = "pending"
    invitation.sent_at = None
    invitation.revoked_at = None
    invitation.expires_at = datetime.now(timezone.utc) + INVITATION_TTL
    db.add(_audit(admin_id, "resend", invitation.id))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise InvitationError("invitation_pending") from exc
    return token


async def revoke_invitation(
    db: AsyncSession, invitation_id: int, admin_id: int
) -> OwnerInvitation:
    invitation = await db.scalar(
        select(OwnerInvitation)
        .where(OwnerInvitation.id == invitation_id)
        .with_for_update()
    )
    if invitation is None:
        raise InvitationError("not_found")
    if invitation.status != "pending":
        raise InvitationError("invalid_state")

    invitation.status = "revoked"
    invitation.revoked_at = datetime.now(timezone.utc)
    db.add(_audit(admin_id, "revoke", invitation.id))
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def accept_invitation(db: AsyncSession, token: str, password: str) -> Owner:
    token = token.strip()
    if not token or not password or len(password) < 12 or len(password.encode("utf-8")) > 72:
        raise InvitationError("invalid_invitation")

    invitation = await db.scalar(
        select(OwnerInvitation)
        .where(OwnerInvitation.token_hash == _token_hash(token))
        .with_for_update()
    )
    if invitation is None or invitation.status != "pending":
        raise InvitationError("invalid_invitation")
    if invitation.expires_at <= datetime.now(timezone.utc):
        invitation.status = "expired"
        await db.commit()
        raise InvitationError("invalid_invitation")

    normalized_email = _normalize_email(invitation.email)
    owner_exists = await db.scalar(
        select(Owner.id).where(func.lower(Owner.email) == normalized_email)
    )
    if owner_exists is not None:
        raise InvitationError("invalid_invitation")

    owner = Owner(
        email=normalized_email,
        hashed_password=get_password_hash(password),
        email_verified=True,
        is_active=True,
    )
    db.add(owner)
    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise InvitationError("invalid_invitation") from exc
    await db.refresh(owner)
    return owner


async def get_invitation_preview(db: AsyncSession, token: str) -> OwnerInvitation:
    """Devuelve el correo fijado solo mientras el token de invitación sea utilizable."""
    if not token or len(token) > 256:
        raise InvitationError("invalid_invitation")
    invitation = await db.scalar(
        select(OwnerInvitation).where(
            OwnerInvitation.token_hash == _token_hash(token)
        )
    )
    if invitation is None or invitation.status != "pending":
        raise InvitationError("invalid_invitation")
    if invitation.expires_at <= datetime.now(timezone.utc):
        invitation.status = "expired"
        await db.commit()
        raise InvitationError("invalid_invitation")
    return invitation
