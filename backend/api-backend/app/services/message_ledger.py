"""Evidencia mínima de mensajes WhatsApp salientes y sus estados de entrega.

Los eventos únicos se deduplican en PostgreSQL; la fila ``message:*`` mantiene
el estado más fuerte conocido de cada ID de Meta. No se guarda destinatario,
texto, teléfono de cliente ni conversación.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, MessageEvent

_STATUS_RANK = {"created": 0, "sent": 1, "failed": 2, "delivered": 3, "read": 4}


@dataclass(frozen=True)
class StatusIngestResult:
    recorded: int = 0
    duplicates: int = 0
    unresolved: int = 0
    ignored: int = 0


def _event_key(prefix: str, *parts: str) -> str:
    digest = sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


async def _lock_meta_message(db: AsyncSession, message_id: str) -> None:
    # El mismo ID debe serializarse entre negocios antes de consultar su dueño.
    # El lock vive hasta el commit del llamador, también entre workers distintos.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:message_key, 0))"),
        {"message_key": f"whatsapp:{message_id}"},
    )


async def _insert_event(db: AsyncSession, **values: Any) -> bool:
    statement = (
        insert(MessageEvent)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=["business_id", "channel", "event_key"]
        )
        .returning(MessageEvent.id)
    )
    return (await db.execute(statement)).scalar_one_or_none() is not None


async def _ensure_current_message(
    db: AsyncSession,
    *,
    business_id: int,
    message_id: str,
    status: str,
    occurred_at: datetime,
    category: str | None = None,
    country: str | None = None,
) -> bool:
    event_key = _event_key("message", message_id)
    created = await _insert_event(
        db,
        business_id=business_id,
        channel="whatsapp",
        event_key=event_key,
        provider_message_id=message_id,
        direction="outbound",
        status=status,
        category=category,
        country=country,
        occurred_at=occurred_at,
    )
    current = await db.scalar(
        select(MessageEvent)
        .where(
            MessageEvent.business_id == business_id,
            MessageEvent.channel == "whatsapp",
            MessageEvent.event_key == event_key,
        )
        .with_for_update()
    )
    if current is None:
        raise RuntimeError("No se pudo recuperar el mensaje saliente")
    if _STATUS_RANK.get(status, 0) > _STATUS_RANK.get(current.status, 0):
        current.status = status
        current.occurred_at = occurred_at
    if category and not current.category:
        current.category = category
    if country and not current.country:
        current.country = country
    return created


async def record_outbound_response(
    db: AsyncSession,
    business_id: int,
    response: Mapping[str, Any] | None,
    *,
    occurred_at: datetime | None = None,
) -> bool:
    """Registra el ID de Meta una vez tras un envío aceptado por su API.

    Retorna ``False`` si la respuesta no trae un ID o ya existe evidencia para
    ese mensaje. El llamador conserva el control de la transacción.
    """
    if not isinstance(response, Mapping):
        return False
    messages = response.get("messages")
    if not isinstance(messages, list) or not messages:
        return False
    first = messages[0]
    message_id = first.get("id") if isinstance(first, Mapping) else None
    if not isinstance(message_id, str) or not message_id:
        return False
    if await db.scalar(select(Business.id).where(Business.id == business_id)) is None:
        return False
    await _lock_meta_message(db, message_id)
    existing_other_business = await db.scalar(
        select(MessageEvent.business_id).where(
            MessageEvent.channel == "whatsapp",
            MessageEvent.event_key == _event_key("message", message_id),
            MessageEvent.business_id != business_id,
        )
    )
    if existing_other_business is not None:
        return False
    return await _ensure_current_message(
        db,
        business_id=business_id,
        message_id=message_id,
        status="sent",
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )


def _occurred_at(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return datetime.now(timezone.utc)


def _safe_short(value: Any, length: int) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= length else None


async def record_whatsapp_status_payload(
    db: AsyncSession, payload: Mapping[str, Any]
) -> StatusIngestResult:
    """Guarda todos los estados presentes en un callback válido de Meta.

    Un ``phone_number_id`` sin negocio se reporta como no resuelto y no se
    atribuye. El historial conserva transiciones únicas aunque lleguen tarde.
    """
    recorded = duplicates = unresolved = ignored = 0
    entries = payload.get("entry", []) if isinstance(payload, Mapping) else []
    if not isinstance(entries, list):
        return StatusIngestResult(ignored=1)
    # Un callback puede traer varios mensajes. Tomar todos los locks en el mismo
    # orden evita interbloqueos si dos callbacks los reciben en orden inverso.
    message_ids = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            value = change.get("value", {}) if isinstance(change, Mapping) else {}
            statuses = value.get("statuses", []) if isinstance(value, Mapping) else []
            if not isinstance(statuses, list):
                continue
            for item in statuses:
                if isinstance(item, Mapping):
                    message_id = item.get("id")
                    if isinstance(message_id, str) and message_id:
                        message_ids.add(message_id)
    for message_id in sorted(message_ids):
        await _lock_meta_message(db, message_id)
    for entry in entries:
        if not isinstance(entry, Mapping):
            ignored += 1
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            ignored += 1
            continue
        for change in changes:
            value = change.get("value", {}) if isinstance(change, Mapping) else {}
            if not isinstance(value, Mapping):
                ignored += 1
                continue
            statuses = value.get("statuses", [])
            if not isinstance(statuses, list):
                ignored += 1
                continue
            metadata = value.get("metadata", {})
            phone_id = metadata.get("phone_number_id") if isinstance(metadata, Mapping) else None
            business_id = (
                await db.scalar(
                    select(Business.id).where(Business.whatsapp_phone_number_id == phone_id)
                )
                if isinstance(phone_id, str) and phone_id
                else None
            ) if statuses else None
            for item in statuses:
                if not isinstance(item, Mapping):
                    ignored += 1
                    continue
                message_id = item.get("id")
                status = item.get("status")
                if not isinstance(message_id, str) or not message_id or not isinstance(status, str) or not status:
                    ignored += 1
                    continue
                if business_id is None:
                    unresolved += 1
                    continue
                existing_other_business = await db.scalar(
                    select(MessageEvent.business_id).where(
                        MessageEvent.channel == "whatsapp",
                        MessageEvent.event_key == _event_key("message", message_id),
                        MessageEvent.business_id != business_id,
                    )
                )
                if existing_other_business is not None:
                    unresolved += 1
                    continue
                timestamp = item.get("timestamp")
                occurred_at = _occurred_at(timestamp)
                pricing = item.get("pricing", {})
                category = _safe_short(
                    pricing.get("category") if isinstance(pricing, Mapping) else None, 32
                )
                country = _safe_short(item.get("country"), 8)
                inserted = await _insert_event(
                    db,
                    business_id=business_id,
                    channel="whatsapp",
                    event_key=_event_key("status", message_id, status, str(timestamp)),
                    provider_message_id=message_id,
                    direction="outbound",
                    status=status,
                    category=category,
                    country=country,
                    occurred_at=occurred_at,
                )
                if inserted:
                    recorded += 1
                else:
                    duplicates += 1
                await _ensure_current_message(
                    db,
                    business_id=business_id,
                    message_id=message_id,
                    status=status,
                    occurred_at=occurred_at,
                    category=category,
                    country=country,
                )
    return StatusIngestResult(
        recorded=recorded,
        duplicates=duplicates,
        unresolved=unresolved,
        ignored=ignored,
    )
