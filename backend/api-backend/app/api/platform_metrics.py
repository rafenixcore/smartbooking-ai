"""Conteos administrativos a partir de citas persistidas."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_platform_admin
from app.models import Appointment, Business, MessageEvent, PlatformAdmin
from app.services.message_costs import CostSummary, summarize_costs, summarize_global_costs

router = APIRouter()

_KNOWN_STATUSES = ("P", "C", "A", "D")
_MAX_PERIOD = timedelta(days=366)


def _status_counts(rows: list[tuple[str | None, int]]) -> dict[str, int]:
    counts = {status: 0 for status in _KNOWN_STATUSES}
    for status, count in rows:
        key = status if status else "unknown"
        counts[key] = counts.get(key, 0) + int(count)
    return counts


def _summary(rows: list[tuple[str | None, int]], customers: int) -> dict:
    counts = _status_counts(rows)
    return {
        "appointments": {"total": sum(counts.values()), "by_status": counts},
        "customers_with_appointments": int(customers),
    }


def _cost_payload(summary: CostSummary) -> dict:
    return {
        "status": summary.status,
        "amount": str(summary.amount) if summary.amount is not None else None,
        "currency": summary.currency,
        "reason": summary.reason,
        "source_reference": summary.source_reference,
        "rate_versions": list(summary.rate_versions),
        "coverage": summary.coverage,
    }


def _message_summary(rows: list[tuple[str, int]]) -> dict:
    counts = {status: int(count) for status, count in rows}
    return {"total": sum(counts.values()), "by_status": counts}


@router.get("")
async def get_platform_metrics(
    start: datetime = Query(alias="from"),
    end: datetime = Query(alias="to"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> dict:
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail="El periodo requiere zona horaria")
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    if end_utc <= start_utc or end_utc - start_utc > _MAX_PERIOD:
        raise HTTPException(status_code=422, detail="Periodo inválido o mayor a 366 días")

    period_filter = (Appointment.date >= start_utc, Appointment.date < end_utc)
    global_status_rows = (
        await db.execute(
            select(Appointment.status, func.count(Appointment.id))
            .where(*period_filter)
            .group_by(Appointment.status)
        )
    ).all()
    global_customers = await db.scalar(
        select(func.count(func.distinct(Appointment.customer_id))).where(*period_filter)
    )

    businesses_total = int(await db.scalar(select(func.count(Business.id))) or 0)
    page_rows = (
        await db.execute(
            select(Business.id, Business.name)
            .order_by(Business.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    business_ids = [business_id for business_id, _name in page_rows]
    grouped_statuses: dict[int, list[tuple[str | None, int]]] = {}
    grouped_customers: dict[int, int] = {}
    message_filter = (
        MessageEvent.channel == "whatsapp",
        MessageEvent.direction == "outbound",
        MessageEvent.event_key.like("message:%"),
        MessageEvent.occurred_at >= start_utc,
        MessageEvent.occurred_at < end_utc,
    )
    global_message_rows = (
        await db.execute(
            select(MessageEvent.status, func.count(MessageEvent.id))
            .where(*message_filter).group_by(MessageEvent.status)
        )
    ).all()
    global_cost = await summarize_global_costs(db, start_utc, end_utc)
    grouped_messages: dict[int, list[tuple[str, int]]] = {}
    if business_ids:
        status_rows = (
            await db.execute(
                select(Appointment.business_id, Appointment.status, func.count(Appointment.id))
                .where(Appointment.business_id.in_(business_ids), *period_filter)
                .group_by(Appointment.business_id, Appointment.status)
            )
        ).all()
        for business_id, status, count in status_rows:
            grouped_statuses.setdefault(business_id, []).append((status, count))

        customer_rows = (
            await db.execute(
                select(
                    Appointment.business_id,
                    func.count(func.distinct(Appointment.customer_id)),
                )
                .where(Appointment.business_id.in_(business_ids), *period_filter)
                .group_by(Appointment.business_id)
            )
        ).all()
        grouped_customers = {business_id: int(count) for business_id, count in customer_rows}

        message_rows = (
            await db.execute(
                select(MessageEvent.business_id, MessageEvent.status, func.count(MessageEvent.id))
                .where(MessageEvent.business_id.in_(business_ids), *message_filter)
                .group_by(MessageEvent.business_id, MessageEvent.status)
            )
        ).all()
        for business_id, status, count in message_rows:
            grouped_messages.setdefault(business_id, []).append((status, count))

    items = []
    for business_id, name in page_rows:
        items.append({
            "business_id": business_id,
            "business_name": name,
            **_summary(
                grouped_statuses.get(business_id, []),
                grouped_customers.get(business_id, 0),
            ),
            "messages": _message_summary(grouped_messages.get(business_id, [])),
            "cost": _cost_payload(await summarize_costs(db, business_id, start_utc, end_utc)),
        })
    return {
        "period": {
            "start": start_utc.isoformat(),
            "end": end_utc.isoformat(),
            "timezone": "UTC",
        },
        "definitions": {
            "appointments": {
                "source": "appointments",
                "formula": "Filas por appointments.date en [from, to), agrupadas por status; total incluye todos los estados.",
            },
            "customers_with_appointments": {
                "source": "appointments",
                "formula": "COUNT(DISTINCT customer_id) no nulo entre citas del periodo; incluye todos los estados.",
            },
            "messages": {
                "source": "message_events",
                "formula": "Una fila canónica message:* por ID saliente de WhatsApp; último estado conocido cuya fecha de estado cae en [from, to). No suma eventos status:* repetidos.",
            },
            "cost": {
                "source": "message_cost_records",
                "formula": "actual solo con conciliación completa del periodo; estimated solo si todos los entregados tienen tarifa versionada y misma moneda; en otros casos unavailable. amount es texto decimal.",
            },
        },
        "global": {
            **_summary(global_status_rows, int(global_customers or 0)),
            "messages": _message_summary(global_message_rows),
            "cost": _cost_payload(global_cost),
        },
        "businesses": {
            "items": items,
            "total": businesses_total,
            "offset": offset,
            "limit": limit,
        },
    }
