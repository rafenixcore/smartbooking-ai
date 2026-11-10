"""Límite persistente de intentos fallidos de acceso administrativo."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SECRET_KEY
from app.models import PlatformLoginAttempt


EMAIL_LIMIT = 5
IP_LIMIT = 20
WINDOW = timedelta(hours=1)
_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"smartbooking:platform-login-rate").digest()[:8],
    "big",
    signed=True,
)


def _hash_identity(kind: str, value: str) -> str:
    return hmac.new(
        SECRET_KEY.encode(), f"{kind}:{value}".encode(), hashlib.sha256
    ).hexdigest()


async def check_login_limit(
    db: AsyncSession, ip: str, email: str
) -> tuple[str, str] | None:
    """Retiene un lock transaccional hasta que el caller registre éxito o fallo."""
    email_hash = _hash_identity("email", email.strip().casefold())
    ip_hash = _hash_identity("ip", ip)
    window_start = datetime.now(timezone.utc) - WINDOW
    await db.execute(select(func.pg_advisory_xact_lock(_LOCK_KEY)))
    await db.execute(delete(PlatformLoginAttempt).where(
        PlatformLoginAttempt.created_at < window_start
    ))
    email_count = await db.scalar(
        select(func.count()).select_from(PlatformLoginAttempt).where(
            PlatformLoginAttempt.email_hash == email_hash,
            PlatformLoginAttempt.created_at >= window_start,
        )
    )
    ip_count = await db.scalar(
        select(func.count()).select_from(PlatformLoginAttempt).where(
            PlatformLoginAttempt.ip_hash == ip_hash,
            PlatformLoginAttempt.created_at >= window_start,
        )
    )
    if email_count >= EMAIL_LIMIT or ip_count >= IP_LIMIT:
        return None
    return email_hash, ip_hash


def record_failed_login(db: AsyncSession, hashes: tuple[str, str]) -> None:
    db.add(PlatformLoginAttempt(
        email_hash=hashes[0],
        ip_hash=hashes[1],
        created_at=datetime.now(timezone.utc),
    ))
