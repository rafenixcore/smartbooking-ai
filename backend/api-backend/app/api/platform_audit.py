"""Consulta de la bitácora, exclusiva de administradores de plataforma."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_platform_admin
from app.models import PlatformAdmin
from app.services.admin_audit import list_admin_audit_events

router = APIRouter()


class AdminAuditEventOut(BaseModel):
    id: int
    admin_id: int
    action: str
    entity_type: str
    entity_id: str
    outcome: str
    created_at: datetime


class AdminAuditListOut(BaseModel):
    items: list[AdminAuditEventOut]
    total: int
    offset: int
    limit: int


@router.get("", response_model=AdminAuditListOut)
async def list_admin_audit(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    entity_type: str | None = Query(default=None, min_length=1, max_length=64),
    entity_id: str | None = Query(default=None, min_length=1, max_length=64),
    db: AsyncSession = Depends(get_db),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> AdminAuditListOut:
    rows, total = await list_admin_audit_events(
        db,
        offset=offset,
        limit=limit,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return AdminAuditListOut(
        items=[
            AdminAuditEventOut(
                id=row.id,
                admin_id=row.admin_id,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                outcome=row.outcome,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
