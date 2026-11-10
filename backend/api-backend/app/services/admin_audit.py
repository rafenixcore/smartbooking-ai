"""Bitácora mínima de acciones administrativas.

El registro solo acepta campos estructurados y no almacena cuerpos de petición,
correos, teléfonos, contraseñas, tokens ni contenido de mensajes.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAuditEvent


def new_admin_audit_event(
    *, admin_id: int, action: str, entity_type: str, entity_id: int | str, outcome: str
) -> AdminAuditEvent:
    if not (admin_id > 0 and action and entity_type and str(entity_id) and outcome):
        raise ValueError("Los campos de auditoría son obligatorios")
    if len(action) > 64 or len(entity_type) > 64 or len(str(entity_id)) > 64 or len(outcome) > 32:
        raise ValueError("Los campos de auditoría exceden su longitud")
    return AdminAuditEvent(
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        outcome=outcome,
    )


async def list_admin_audit_events(
    db: AsyncSession,
    *,
    offset: int,
    limit: int,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> tuple[list[AdminAuditEvent], int]:
    filters = []
    if entity_type is not None:
        filters.append(AdminAuditEvent.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AdminAuditEvent.entity_id == entity_id)

    total = int(await db.scalar(select(func.count(AdminAuditEvent.id)).where(*filters)) or 0)
    rows = await db.scalars(
        select(AdminAuditEvent)
        .where(*filters)
        .order_by(AdminAuditEvent.created_at.desc(), AdminAuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows.all()), total
