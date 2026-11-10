"""Refresh tokens opacos en BD: rotación en cada /auth/refresh y revocación en logout."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.models import Owner, PasswordReset, RefreshToken

REFRESH_DAYS = 7
_PLAIN_BYTES = 48


def hash_refresh_plain(plain: str) -> str:
    return hashlib.sha256(plain.strip().encode("utf-8")).hexdigest()


async def _issue_in_session(db, owner_id: int) -> str:
    plain = secrets.token_urlsafe(_PLAIN_BYTES)
    h = hash_refresh_plain(plain)
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS)
    await db.execute(delete(RefreshToken).where(RefreshToken.owner_id == owner_id))
    db.add(RefreshToken(owner_id=owner_id, token_hash=h, expires_at=exp))
    await db.flush()
    return plain


async def issue_refresh_token(owner_id: int, db=None) -> str:
    """Emite refresh bajo el lock de Owner cuando se comparte la sesión del login."""
    if db is not None:
        return await _issue_in_session(db, owner_id)
    async with AsyncSessionLocal() as own_db, own_db.begin():
        owner = (
            await own_db.execute(
                select(Owner).where(Owner.id == owner_id).with_for_update()
            )
        ).scalar_one_or_none()
        if owner is None or not owner.is_active:
            raise ValueError("Owner no disponible")
        return await _issue_in_session(own_db, owner_id)


async def revoke_all_refresh_tokens(owner_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RefreshToken).where(RefreshToken.owner_id == owner_id))
        await db.commit()


async def consume_and_rotate_refresh(plain: str):
    if not plain or not plain.strip():
        return None, None
    h = hash_refresh_plain(plain)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db, db.begin():
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == h))
        row = result.scalars().first()
        if not row:
            return None, None
        owner_result = await db.execute(
            select(Owner).where(Owner.id == row.owner_id).with_for_update()
        )
        owner = owner_result.scalars().first()
        if owner is None:
            return None, None
        locked_row = (
            await db.execute(
                select(RefreshToken)
                .where(RefreshToken.id == row.id, RefreshToken.token_hash == h)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if locked_row is None:
            return None, None
        if not owner.is_active or locked_row.expires_at <= now:
            await db.delete(locked_row)
            return None, None
        latest_reset = await db.scalar(
            select(func.max(PasswordReset.used_at)).where(
                PasswordReset.owner_id == owner.id
            )
        )
        if latest_reset is not None and locked_row.created_at <= latest_reset:
            await db.delete(locked_row)
            return None, None
        new_plain = secrets.token_urlsafe(_PLAIN_BYTES)
        locked_row.token_hash = hash_refresh_plain(new_plain)
        locked_row.expires_at = now + timedelta(days=REFRESH_DAYS)
        await db.flush()
        return owner, new_plain
