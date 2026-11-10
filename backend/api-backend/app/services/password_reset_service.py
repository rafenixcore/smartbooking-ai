"""Tokens de recuperación de un uso para dueños y administradores de plataforma."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SECRET_KEY, get_password_hash
from app.models import (
    Owner,
    PasswordReset,
    PasswordResetRequestAttempt,
    PlatformAdmin,
    PlatformAdminSession,
    RefreshToken,
)


RESET_TOKEN_TTL = timedelta(hours=1)
RESET_EMAIL_LIMIT = 5
RESET_IP_LIMIT = 20
RESET_WINDOW = timedelta(hours=1)
_RATE_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"smartbooking:password-reset-rate").digest()[:8],
    "big",
    signed=True,
)


class InvalidResetToken(Exception):
    """El enlace no existe, venció, ya fue usado o pertenece a una cuenta inactiva."""


async def allow_reset_request(db: AsyncSession, ip: str, email: str) -> bool:
    """Cuenta intentos en PostgreSQL antes de consultar si existe la cuenta.

    Un lock transaccional mantiene exactos ambos límites bajo concurrencia. Los
    hashes HMAC evitan guardar correo o IP en claro en la tabla de intentos.
    """
    secret = SECRET_KEY.encode()
    normalized_email = email.strip().casefold()
    email_hash = hmac.new(
        secret, f"email:{normalized_email}".encode(), hashlib.sha256
    ).hexdigest()
    ip_hash = hmac.new(secret, f"ip:{ip}".encode(), hashlib.sha256).hexdigest()
    now = datetime.now(timezone.utc)
    window_start = now - RESET_WINDOW

    async with db.begin():
        await db.execute(select(func.pg_advisory_xact_lock(_RATE_LOCK_KEY)))
        await db.execute(
            delete(PasswordResetRequestAttempt).where(
                PasswordResetRequestAttempt.created_at < window_start
            )
        )
        email_count = await db.scalar(
            select(func.count())
            .select_from(PasswordResetRequestAttempt)
            .where(PasswordResetRequestAttempt.email_hash == email_hash)
        )
        ip_count = await db.scalar(
            select(func.count())
            .select_from(PasswordResetRequestAttempt)
            .where(PasswordResetRequestAttempt.ip_hash == ip_hash)
        )
        if email_count >= RESET_EMAIL_LIMIT or ip_count >= RESET_IP_LIMIT:
            return False
        db.add(
            PasswordResetRequestAttempt(
                email_hash=email_hash,
                ip_hash=ip_hash,
                created_at=now,
            )
        )
    return True


async def issue_reset_tokens(
    db: AsyncSession, email: str
) -> list[tuple[str, str, str]]:
    """Persiste hashes y devuelve los valores planos solo para enviarlos por correo."""
    normalized_email = email.strip().casefold()
    owners = (
        await db.execute(
            select(Owner).where(func.lower(Owner.email) == normalized_email)
        )
    ).scalars().all()
    admin = (
        await db.execute(
            select(PlatformAdmin).where(func.lower(PlatformAdmin.email) == normalized_email)
        )
    ).scalar_one_or_none()

    deliveries: list[tuple[str, str, str]] = []
    now = datetime.now(timezone.utc)
    candidates = [(owner, "owner") for owner in owners]
    candidates.append((admin, "platform_admin"))
    for principal, account_type in candidates:
        if principal is None or not principal.is_active:
            continue
        token = secrets.token_urlsafe(32)
        db.add(
            PasswordReset(
                owner_id=principal.id if account_type == "owner" else None,
                platform_admin_id=(
                    principal.id if account_type == "platform_admin" else None
                ),
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=now + RESET_TOKEN_TTL,
            )
        )
        deliveries.append((principal.email, token, account_type))
    if deliveries:
        await db.commit()
    return deliveries


async def confirm_reset(db: AsyncSession, token: str, password: str) -> None:
    token_hash = hashlib.sha256(token.strip().encode()).hexdigest()
    result = await db.execute(
        select(PasswordReset)
        .where(PasswordReset.token_hash == token_hash)
        .with_for_update()
    )
    reset = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if reset is None or reset.used_at is not None or reset.expires_at <= now:
        raise InvalidResetToken()

    if reset.owner_id is not None:
        owner = (
            await db.execute(
                select(Owner).where(Owner.id == reset.owner_id).with_for_update()
            )
        ).scalar_one_or_none()
        if owner is None or not owner.is_active:
            raise InvalidResetToken()
        owner.hashed_password = get_password_hash(password)
        await db.execute(delete(RefreshToken).where(RefreshToken.owner_id == owner.id))
        await db.execute(
            update(PasswordReset)
            .where(
                PasswordReset.owner_id == owner.id,
                PasswordReset.used_at.is_(None),
            )
            .values(used_at=now)
        )
    else:
        admin = (
            await db.execute(
                select(PlatformAdmin)
                .where(PlatformAdmin.id == reset.platform_admin_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if admin is None or not admin.is_active:
            raise InvalidResetToken()
        admin.hashed_password = get_password_hash(password)
        await db.execute(
            update(PlatformAdminSession)
            .where(
                PlatformAdminSession.admin_id == admin.id,
                PlatformAdminSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.execute(
            update(PasswordReset)
            .where(
                PasswordReset.platform_admin_id == admin.id,
                PasswordReset.used_at.is_(None),
            )
            .values(used_at=now)
        )
    await db.commit()
