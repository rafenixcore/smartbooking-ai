from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import ALGORITHM, SECRET_KEY
from app.models import Business, Owner, PasswordReset, PlatformAdmin, PlatformAdminSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")
platform_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/platform/auth/token")


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_owner(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_kind") != "access":
            raise _invalid_credentials()
        if payload.get("principal_type") not in (None, "owner"):
            raise _invalid_credentials()
        email = payload.get("email")
        if not isinstance(email, str) or not email:
            raise _invalid_credentials()
    except jwt.PyJWTError:
        raise _invalid_credentials() from None

    result = await db.execute(select(Owner).where(Owner.email == email))
    owner = result.scalars().first()
    if owner is None or not owner.is_active:
        raise _invalid_credentials()
    if owner.access_revoked_at is not None:
        issued_at_ns = payload.get("iat_ns")
        revoked_at_ns = int(owner.access_revoked_at.timestamp() * 1_000_000_000)
        if not isinstance(issued_at_ns, int) or issued_at_ns <= revoked_at_ns:
            raise _invalid_credentials()
    latest_reset = await db.scalar(
        select(func.max(PasswordReset.used_at)).where(
            PasswordReset.owner_id == owner.id
        )
    )
    if latest_reset is not None:
        issued_at_ns = payload.get("iat_ns")
        reset_at_ns = int(latest_reset.timestamp() * 1_000_000_000)
        if not isinstance(issued_at_ns, int) or issued_at_ns <= reset_at_ns:
            raise _invalid_credentials()
    return owner


async def require_owned_operational_business(
    business_id: int,
    current_owner: Owner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Comprueba propiedad y estado vigente antes de cualquier operación de negocio."""
    result = await db.execute(
        select(Business).where(
            Business.id == business_id,
            Business.owner_id == current_owner.id,
        )
    )
    business = result.scalars().first()
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    if not business.is_active:
        raise HTTPException(status_code=403, detail="El negocio está suspendido")
    if business.onboarding_completed_at is None:
        raise HTTPException(status_code=403, detail="Completa el alta del negocio antes de operar")
    return business


async def get_current_platform_admin(
    token: str = Depends(platform_oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_kind") != "access":
            raise _invalid_credentials()
        if payload.get("principal_type") != "platform_admin":
            raise _invalid_credentials()
        subject, session_ref, email = (
            payload.get("sub"),
            payload.get("sid"),
            payload.get("email"),
        )
        if not isinstance(subject, str) or not subject.isdecimal():
            raise _invalid_credentials()
        if not isinstance(session_ref, str) or not session_ref.isdecimal():
            raise _invalid_credentials()
        if not isinstance(email, str) or not email:
            raise _invalid_credentials()
        admin_id, session_id = int(subject), int(session_ref)
        if admin_id < 1 or session_id < 1:
            raise _invalid_credentials()
    except jwt.PyJWTError:
        raise _invalid_credentials() from None

    session_result = await db.execute(
        select(PlatformAdminSession).where(
            PlatformAdminSession.id == session_id,
            PlatformAdminSession.admin_id == admin_id,
        )
    )
    session = session_result.scalars().first()
    now = datetime.now(timezone.utc)
    if (
        session is None
        or session.id != session_id
        or session.admin_id != admin_id
        or session.revoked_at is not None
        or session.expires_at <= now
    ):
        raise _invalid_credentials()

    admin_result = await db.execute(select(PlatformAdmin).where(PlatformAdmin.id == admin_id))
    admin = admin_result.scalars().first()
    if (
        admin is None
        or admin.id != admin_id
        or not admin.is_active
        or admin.email.casefold() != email.casefold()
    ):
        raise _invalid_credentials()
    return admin
