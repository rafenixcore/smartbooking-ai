"""Administración de invitaciones de dueños."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_platform_admin
from app.models import OwnerInvitation, PlatformAdmin
from app.schemas import OwnerInvitationCreate, OwnerInvitationListOut, OwnerInvitationOut
from app.services.email_service import EmailDeliveryError, send_invitation_email
from app.services.owner_invitations import (
    InvitationError,
    create_invitation,
    resend_invitation,
    revoke_invitation,
)


router = APIRouter()


async def _send_and_record(db: AsyncSession, invitation: OwnerInvitation, token: str):
    try:
        await send_invitation_email(invitation.email, token)
    except EmailDeliveryError:
        invitation.delivery_status = "failed"
        invitation.sent_at = None
    else:
        invitation.delivery_status = "sent"
        invitation.sent_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invitation)
    return invitation


def _admin_error(exc: InvitationError) -> HTTPException:
    if exc.code == "not_found":
        return HTTPException(status_code=404, detail="No se encontró la invitación")
    if exc.code == "owner_exists":
        return HTTPException(status_code=409, detail="Ya existe una cuenta para ese correo")
    if exc.code == "invitation_pending":
        return HTTPException(status_code=409, detail="Ya existe una invitación pendiente")
    if exc.code == "invalid_email":
        return HTTPException(status_code=422, detail="El correo no es válido")
    if exc.code == "admin_unavailable":
        return HTTPException(status_code=401, detail="Sesión administrativa inválida")
    return HTTPException(status_code=409, detail="La invitación ya no permite esta acción")


@router.get("", response_model=OwnerInvitationListOut)
async def list_invitations(
    status_filter: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
):
    allowed_statuses = {"pending", "accepted", "expired", "revoked"}
    if status_filter is not None and status_filter not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Estado de invitación no válido")

    await db.execute(
        update(OwnerInvitation)
        .where(
            OwnerInvitation.status == "pending",
            OwnerInvitation.expires_at <= datetime.now(timezone.utc),
        )
        .values(status="expired")
    )
    await db.commit()

    query = select(OwnerInvitation)
    count_query = select(func.count(OwnerInvitation.id))
    if status_filter:
        query = query.where(OwnerInvitation.status == status_filter)
        count_query = count_query.where(OwnerInvitation.status == status_filter)
    total = int(await db.scalar(count_query) or 0)
    rows = await db.scalars(
        query.order_by(OwnerInvitation.created_at.desc(), OwnerInvitation.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return OwnerInvitationListOut(
        items=rows.all(), total=total, offset=offset, limit=limit
    )


@router.post("", response_model=OwnerInvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation_endpoint(
    body: OwnerInvitationCreate,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
):
    try:
        invitation, token = await create_invitation(db, str(body.email), admin.id)
    except InvitationError as exc:
        raise _admin_error(exc) from None
    return await _send_and_record(db, invitation, token)


@router.post("/{invitation_id}/resend", response_model=OwnerInvitationOut)
async def resend_invitation_endpoint(
    invitation_id: int,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
):
    try:
        token = await resend_invitation(db, invitation_id, admin.id)
    except InvitationError as exc:
        raise _admin_error(exc) from None
    invitation = await db.get(OwnerInvitation, invitation_id)
    return await _send_and_record(db, invitation, token)


@router.post("/{invitation_id}/revoke", response_model=OwnerInvitationOut)
async def revoke_invitation_endpoint(
    invitation_id: int,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
):
    try:
        return await revoke_invitation(db, invitation_id, admin.id)
    except InvitationError as exc:
        raise _admin_error(exc) from None
