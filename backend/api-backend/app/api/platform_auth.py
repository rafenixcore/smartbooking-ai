"""Separate platform administrator authentication and revocable sessions."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_platform_admin, platform_oauth2_scheme
from app.core.security import create_access_token, decode_token, verify_password
from app.models import PlatformAdmin, PlatformAdminSession
from app.services.platform_login_limits import check_login_limit, record_failed_login

router = APIRouter()

PLATFORM_ACCESS_MINUTES = 15
PLATFORM_REFRESH_DAYS = 7


class PlatformAdminOut(BaseModel):
    id: int
    email: str


class PlatformLoginResponse(BaseModel):
    access_token: str
    refresh: str
    token_type: Literal["bearer"] = "bearer"
    admin: PlatformAdminOut


class PlatformRefreshRequest(BaseModel):
    refresh: str = Field(min_length=1, max_length=512)


class PlatformRefreshResponse(BaseModel):
    access_token: str
    refresh: str
    token_type: Literal["bearer"] = "bearer"


def _refresh_hash(plain: str) -> str:
    return hashlib.sha256(plain.strip().encode("utf-8")).hexdigest()


def _invalid_login() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Correo o contraseña incorrectos",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _invalid_refresh() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _access_token(admin: PlatformAdmin, session: PlatformAdminSession) -> str:
    return create_access_token(
        data={
            "sub": str(admin.id),
            "email": admin.email,
            "principal_type": "platform_admin",
            "sid": str(session.id),
        },
        expires_delta=timedelta(minutes=PLATFORM_ACCESS_MINUTES),
        token_kind="access",
    )


@router.post("/token", response_model=PlatformLoginResponse)
async def login_platform_admin(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    email = form_data.username.strip()
    client_ip = request.client.host if request.client else "unknown"
    attempt_hashes = await check_login_limit(db, client_ip, email)
    if attempt_hashes is None:
        await db.rollback()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Intenta más tarde.")
    result = await db.execute(
        select(PlatformAdmin)
        .where(func.lower(PlatformAdmin.email) == email.lower())
        .with_for_update()
    )
    admin = result.scalars().first()
    if not admin or not admin.is_active or not verify_password(
        form_data.password, admin.hashed_password
    ):
        record_failed_login(db, attempt_hashes)
        await db.commit()
        raise _invalid_login()

    plain_refresh = secrets.token_urlsafe(48)
    session = PlatformAdminSession(
        admin_id=admin.id,
        token_hash=_refresh_hash(plain_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=PLATFORM_REFRESH_DAYS),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return PlatformLoginResponse(
        access_token=_access_token(admin, session),
        refresh=plain_refresh,
        admin=PlatformAdminOut(id=admin.id, email=admin.email),
    )


@router.post("/refresh", response_model=PlatformRefreshResponse)
async def refresh_platform_admin(
    body: PlatformRefreshRequest, db: AsyncSession = Depends(get_db)
):
    token_hash = _refresh_hash(body.refresh)
    result = await db.execute(
        select(PlatformAdminSession)
        .where(PlatformAdminSession.token_hash == token_hash)
        .with_for_update()
    )
    session = result.scalars().first()
    now = datetime.now(timezone.utc)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise _invalid_refresh()

    admin_result = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.id == session.admin_id)
    )
    admin = admin_result.scalars().first()
    if admin is None or not admin.is_active:
        raise _invalid_refresh()

    new_plain = secrets.token_urlsafe(48)
    session.token_hash = _refresh_hash(new_plain)
    session.expires_at = now + timedelta(days=PLATFORM_REFRESH_DAYS)
    await db.commit()
    return PlatformRefreshResponse(
        access_token=_access_token(admin, session), refresh=new_plain
    )


@router.post("/logout")
async def logout_platform_admin(
    admin: PlatformAdmin = Depends(get_current_platform_admin),
    token: str = Depends(platform_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    session_id = int(decode_token(token)["sid"])
    result = await db.execute(
        select(PlatformAdminSession)
        .where(
            PlatformAdminSession.id == session_id,
            PlatformAdminSession.admin_id == admin.id,
        )
        .with_for_update()
    )
    session = result.scalars().first()
    if session is None or session.revoked_at is not None:
        raise _invalid_refresh()
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.get("/me", response_model=PlatformAdminOut)
async def read_current_platform_admin(
    admin: PlatformAdmin = Depends(get_current_platform_admin),
):
    return PlatformAdminOut(id=admin.id, email=admin.email)
