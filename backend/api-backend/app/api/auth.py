import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.core.database import get_db
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    verify_password,
)
from app.core.dependencies import get_current_owner
from app.models import Owner, RefreshToken
from app.schemas import (
    OwnerInvitationAccept,
    OwnerInvitationPreviewRequest,
    OwnerInvitationPreviewOut,
    RefreshTokenBody,
    RefreshTokenResponse,
    ResendVerificationBody,
    Token,
    VerifyEmailBody,
)
from app.services.email_service import send_verification_email
from app.services.rate_limit_async import allow_resend_verification
from app.services.refresh_token_service import (
    consume_and_rotate_refresh,
    issue_refresh_token,
    revoke_all_refresh_tokens,
)
from app.services.owner_invitations import (
    InvitationError,
    accept_invitation,
    get_invitation_preview,
)

router = APIRouter()


@router.post("/invitations/accept")
async def accept_owner_invitation(
    body: OwnerInvitationAccept,
    db: AsyncSession = Depends(get_db),
):
    try:
        await accept_invitation(db, body.token, body.password)
    except InvitationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La invitación no es válida o ha vencido. Solicita una nueva.",
        ) from None
    return {"ok": True}


@router.post("/invitations/preview", response_model=OwnerInvitationPreviewOut)
async def preview_owner_invitation(
    body: OwnerInvitationPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_invitation_preview(db, body.token)
    except InvitationError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La invitación no es válida o ha vencido. Solicita una nueva.",
        ) from None


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # El lock serializa login y reset: una contraseña anterior no puede emitir
    # un refresh después de que se haya confirmado una nueva contraseña.
    result = await db.execute(
        select(Owner).filter(Owner.email == form_data.username).with_for_update()
    )
    owner = result.scalars().first()

    if not owner or not owner.is_active or not verify_password(form_data.password, owner.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if config.REQUIRE_EMAIL_VERIFICATION and not owner.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Correo no verificado. Revisá tu bandeja o pedí un nuevo enlace.",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"email": owner.email, "sub": str(owner.id), "principal_type": "owner"},
        expires_delta=access_token_expires,
        token_kind="access",
    )

    refresh_plain = await issue_refresh_token(owner.id, db=db)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh": refresh_plain,
        "token_type": "bearer",
        "user": owner,
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(body: RefreshTokenBody):
    owner, new_refresh = await consume_and_rotate_refresh(body.refresh)
    if not owner or not new_refresh or not owner.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )
    if config.REQUIRE_EMAIL_VERIFICATION and not owner.email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado",
        )

    access_token = create_access_token(
        data={"email": owner.email, "sub": str(owner.id), "principal_type": "owner"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_kind="access",
    )
    return RefreshTokenResponse(access_token=access_token, refresh=new_refresh)


@router.post("/logout")
async def logout(
    current_owner: Owner = Depends(get_current_owner),
    db: AsyncSession = Depends(get_db),
):
    owner = (await db.execute(
        select(Owner).where(Owner.id == current_owner.id).with_for_update()
    )).scalar_one()
    owner.access_revoked_at = datetime.now(timezone.utc)
    await db.execute(delete(RefreshToken).where(RefreshToken.owner_id == owner.id))
    await db.commit()
    return {"ok": True}


@router.post("/resend-verification")
async def resend_verification(
    request: Request,
    body: ResendVerificationBody,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if not await allow_resend_verification(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Probá más tarde.",
        )

    result = await db.execute(select(Owner).filter(Owner.email == body.email))
    owner = result.scalars().first()
    if owner and not owner.email_verified:
        owner.verification_token = secrets.token_urlsafe(24)
        owner.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
        await db.commit()
        await db.refresh(owner)
        await send_verification_email(owner.email, owner.verification_token, owner.name)

    return {
        "ok": True,
        "message": "Si el correo existe y falta verificarlo, enviamos nuevas instrucciones.",
    }


@router.post("/verify-email")
async def verify_email(body: VerifyEmailBody, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Owner).filter(
            and_(
                Owner.verification_token == body.token.strip(),
                Owner.verification_token_expires_at.isnot(None),
                Owner.verification_token_expires_at > now,
            )
        )
    )
    owner = result.scalars().first()
    if not owner:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    owner.email_verified = True
    owner.verification_token = None
    owner.verification_token_expires_at = None
    await db.commit()
    await revoke_all_refresh_tokens(owner.id)
    return {"ok": True, "message": "Correo verificado. Ya podés iniciar sesión."}
