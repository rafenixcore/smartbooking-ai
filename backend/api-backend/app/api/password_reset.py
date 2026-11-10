"""Solicitud pública neutral y confirmación de recuperación de contraseña."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import email_service
from app.services.password_reset_service import (
    InvalidResetToken,
    allow_reset_request,
    confirm_reset,
    issue_reset_tokens,
)


router = APIRouter()
logger = logging.getLogger(__name__)


class ResetRequestBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class ResetConfirmBody(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=12, max_length=72)


async def _deliver_reset_emails(deliveries: list[tuple[str, str, str]]) -> None:
    for email, token, account_type in deliveries:
        try:
            await email_service.send_password_reset_email(email, token, account_type)
        except Exception as exc:
            # La respuesta pública ya se envió; no registrar correo, enlace ni token.
            logger.warning("No se pudo entregar recuperación (%s)", type(exc).__name__)


@router.post("/password-reset/request")
async def request_password_reset(
    body: ResetRequestBody,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"
    if not await allow_reset_request(db, ip, body.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Inténtalo más tarde.",
        )

    deliveries = await issue_reset_tokens(db, body.email)
    if deliveries:
        background_tasks.add_task(_deliver_reset_emails, deliveries)
    return {
        "ok": True,
        "message": "Si el correo corresponde a una cuenta, enviaremos instrucciones para recuperar el acceso.",
    }


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    body: ResetConfirmBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        await confirm_reset(db, body.token, body.password)
    except InvalidResetToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace no es válido o ha vencido. Solicita uno nuevo.",
        ) from None
    return {"ok": True}
