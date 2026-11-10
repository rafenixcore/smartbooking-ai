"""Estimaciones trazables y contrato de conciliación de mensajería.

No incluye ninguna tarifa por defecto. El importe real solo se devuelve cuando
un importador de facturación confirma cobertura completa y aporta evidencia
para el periodo exacto.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, MessageCostRecord, MessageEvent


@dataclass(frozen=True)
class VersionedRate:
    category: str
    country: str
    currency: str
    amount_per_delivery: Decimal
    version: str
    source_reference: str
    effective_from: datetime
    effective_to: datetime | None = None

    def __post_init__(self) -> None:
        if (
            not self.category
            or not self.country
            or len(self.currency) != 3
            or not self.version
            or not self.source_reference
            or self.amount_per_delivery < 0
            or self.effective_from.tzinfo is None
            or (self.effective_to is not None and (
                self.effective_to.tzinfo is None
                or self.effective_to <= self.effective_from
            ))
        ):
            raise ValueError("La tarifa requiere fuente, versión, importe y vigencia válidos")


@dataclass(frozen=True)
class CostResult:
    status: str
    amount: Decimal | None = None
    currency: str | None = None
    reason: str | None = None
    source_reference: str | None = None
    rate_version: str | None = None


@dataclass(frozen=True)
class CostSummary:
    status: str
    amount: Decimal | None
    currency: str | None
    reason: str | None
    source_reference: str | None
    rate_versions: tuple[str, ...]
    coverage: dict[str, int]


async def estimate_message_cost(
    db: AsyncSession,
    business_id: int,
    provider_message_id: str,
    *,
    rate: VersionedRate | None,
) -> CostResult:
    """Calcula y guarda una estimación por mensaje entregado, si hay tarifa aplicable."""
    if rate is None:
        return CostResult(status="unavailable", reason="no_verified_rate")
    event = await db.scalar(
        select(MessageEvent).where(
            MessageEvent.business_id == business_id,
            MessageEvent.channel == "whatsapp",
            MessageEvent.provider_message_id == provider_message_id,
            MessageEvent.event_key.like("message:%"),
        )
    )
    if event is None or event.status not in ("delivered", "read"):
        return CostResult(status="unavailable", reason="message_not_delivered")
    if not event.category or not event.country:
        return CostResult(status="unavailable", reason="missing_category_or_country")
    if event.category != rate.category or event.country != rate.country:
        return CostResult(status="unavailable", reason="rate_mismatch")
    occurred_at = event.occurred_at.astimezone(timezone.utc)
    if occurred_at < rate.effective_from.astimezone(timezone.utc) or (
        rate.effective_to is not None
        and occurred_at >= rate.effective_to.astimezone(timezone.utc)
    ):
        return CostResult(status="unavailable", reason="rate_outside_validity")

    identity = f"estimate:{sha256(provider_message_id.encode('utf-8')).hexdigest()}"
    statement = insert(MessageCostRecord).values(
        business_id=business_id,
        message_event_id=event.id,
        idempotency_key=identity,
        amount=rate.amount_per_delivery,
        currency=rate.currency.upper(),
        source="estimated",
        rate_version=rate.version,
        evidence_reference=rate.source_reference,
    )
    await db.execute(
        statement.on_conflict_do_update(
            constraint="uq_message_cost_records_identity",
            set_={
                "message_event_id": event.id,
                "amount": rate.amount_per_delivery,
                "currency": rate.currency.upper(),
                "rate_version": rate.version,
                "evidence_reference": rate.source_reference,
            },
        )
    )
    return CostResult(
        status="estimated",
        amount=rate.amount_per_delivery,
        currency=rate.currency.upper(),
        source_reference=rate.source_reference,
        rate_version=rate.version,
    )


async def record_reconciled_period_total(
    db: AsyncSession,
    business_id: int,
    start: datetime,
    end: datetime,
    *,
    amount: Decimal,
    currency: str,
    evidence_reference: str,
    verified_complete: bool,
) -> MessageCostRecord:
    """Registra un total de factura verificado para todo el periodo del negocio.

    Solo debe llamarse desde un importador administrativo de evidencia de
    facturación. Una segunda cifra para el mismo periodo requiere conciliación
    explícita; no se sobreescribe silenciosamente.
    """
    if not verified_complete or not evidence_reference.strip():
        raise ValueError("Falta evidencia o cobertura completa de facturación")
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or end <= start
        or amount < 0
        or len(currency) != 3
    ):
        raise ValueError("Periodo, importe o moneda inválidos")
    if await db.scalar(select(Business.id).where(Business.id == business_id)) is None:
        raise ValueError("Negocio inexistente")
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    key = "reconciled-period:" + sha256(
        f"{start_utc.isoformat()}|{end_utc.isoformat()}".encode("utf-8")
    ).hexdigest()
    statement = (
        insert(MessageCostRecord)
        .values(
            business_id=business_id,
            idempotency_key=key,
            amount=amount,
            currency=currency.upper(),
            source="reconciled",
            evidence_reference=evidence_reference.strip(),
            period_start=start_utc,
            period_end=end_utc,
            reconciled_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(constraint="uq_message_cost_records_identity")
        .returning(MessageCostRecord.id)
    )
    new_id = (await db.execute(statement)).scalar_one_or_none()
    record = await db.get(MessageCostRecord, new_id) if new_id is not None else await db.scalar(
        select(MessageCostRecord).where(
            MessageCostRecord.business_id == business_id,
            MessageCostRecord.idempotency_key == key,
        )
    )
    if record is None or (
        record.source != "reconciled"
        or record.amount != amount
        or record.currency != currency.upper()
        or record.evidence_reference != evidence_reference.strip()
    ):
        raise ValueError("Ya existe una conciliación diferente para este periodo")
    return record


async def summarize_costs(
    db: AsyncSession, business_id: int, start: datetime, end: datetime
) -> CostSummary:
    """Devuelve real, estimado o no disponible con cobertura explícita."""
    reconciled = (
        await db.execute(
            select(MessageCostRecord).where(
                MessageCostRecord.business_id == business_id,
                MessageCostRecord.source == "reconciled",
                MessageCostRecord.period_start == start,
                MessageCostRecord.period_end == end,
                MessageCostRecord.evidence_reference.is_not(None),
            )
        )
    ).scalars().all()

    delivered = (
        await db.execute(
            select(MessageEvent).where(
                MessageEvent.business_id == business_id,
                MessageEvent.channel == "whatsapp",
                MessageEvent.event_key.like("message:%"),
                MessageEvent.status.in_(("delivered", "read")),
                MessageEvent.occurred_at >= start,
                MessageEvent.occurred_at < end,
            )
        )
    ).scalars().all()
    event_ids = [event.id for event in delivered]
    estimates = (
        await db.execute(
            select(MessageCostRecord).where(
                MessageCostRecord.business_id == business_id,
                MessageCostRecord.source == "estimated",
                MessageCostRecord.message_event_id.in_(event_ids),
            )
        )
    ).scalars().all() if event_ids else []
    coverage = {"delivered": len(delivered), "priced": len(estimates)}

    if len(reconciled) == 1:
        record = reconciled[0]
        return CostSummary(
            status="actual", amount=record.amount, currency=record.currency,
            reason=None, source_reference=record.evidence_reference,
            rate_versions=(), coverage=coverage,
        )
    if len(reconciled) > 1:
        return CostSummary(
            status="unavailable", amount=None, currency=None,
            reason="ambiguous_reconciliation", source_reference=None,
            rate_versions=(), coverage=coverage,
        )
    if not delivered:
        return CostSummary(
            status="unavailable", amount=None, currency=None,
            reason="no_delivered_messages", source_reference=None,
            rate_versions=(), coverage=coverage,
        )
    currencies = {record.currency for record in estimates}
    if len(estimates) != len(delivered) or len(currencies) != 1 or any(
        not record.rate_version or not record.evidence_reference for record in estimates
    ):
        return CostSummary(
            status="unavailable", amount=None, currency=None,
            reason="incomplete_coverage", source_reference=None,
            rate_versions=(), coverage=coverage,
        )
    references = {record.evidence_reference for record in estimates}
    return CostSummary(
        status="estimated",
        amount=sum((record.amount for record in estimates), Decimal("0")),
        currency=next(iter(currencies)), reason=None,
        source_reference=next(iter(references)) if len(references) == 1 else None,
        rate_versions=tuple(sorted({record.rate_version for record in estimates})),
        coverage=coverage,
    )


async def summarize_global_costs(
    db: AsyncSession, start: datetime, end: datetime
) -> CostSummary:
    """Agrega importes solo cuando todos los negocios tienen cobertura homogénea."""
    business_count = int(await db.scalar(select(func.count(Business.id))) or 0)
    if not business_count:
        return CostSummary("unavailable", None, None, "no_businesses", None, (), {"delivered": 0, "priced": 0})
    reconciled = (
        await db.execute(select(MessageCostRecord).where(
            MessageCostRecord.source == "reconciled",
            MessageCostRecord.period_start == start,
            MessageCostRecord.period_end == end,
            MessageCostRecord.evidence_reference.is_not(None),
        ))
    ).scalars().all()
    delivered_filter = (
        MessageEvent.channel == "whatsapp",
        MessageEvent.direction == "outbound",
        MessageEvent.event_key.like("message:%"),
        MessageEvent.status.in_(("delivered", "read")),
        MessageEvent.occurred_at >= start,
        MessageEvent.occurred_at < end,
    )
    delivered_count, priced_count, evidenced_count, estimated_amount, currency_count = (
        await db.execute(
            select(
                func.count(func.distinct(MessageEvent.id)),
                func.count(MessageCostRecord.id),
                func.count(MessageCostRecord.id).filter(
                    MessageCostRecord.rate_version.is_not(None),
                    MessageCostRecord.evidence_reference.is_not(None),
                ),
                func.sum(MessageCostRecord.amount),
                func.count(func.distinct(MessageCostRecord.currency)),
            )
            .outerjoin(MessageCostRecord, and_(
                MessageCostRecord.message_event_id == MessageEvent.id,
                MessageCostRecord.source == "estimated",
            ))
            .where(*delivered_filter)
        )
    ).one()
    coverage = {
        "delivered": int(delivered_count),
        "priced": int(priced_count),
    }
    if (
        len(reconciled) == business_count
        and len({item.business_id for item in reconciled}) == business_count
        and len({item.currency for item in reconciled}) == 1
    ):
        return CostSummary(
            "actual", sum((item.amount for item in reconciled), Decimal("0")),
            reconciled[0].currency, None, "conciliaciones por negocio del periodo", (), coverage,
        )
    if reconciled:
        return CostSummary("unavailable", None, None, "partial_reconciliation", None, (), coverage)
    if delivered_count and priced_count == delivered_count == evidenced_count and currency_count == 1:
        sources = (
            await db.execute(
                select(MessageCostRecord.rate_version, MessageCostRecord.evidence_reference, MessageCostRecord.currency)
                .join(MessageEvent, MessageCostRecord.message_event_id == MessageEvent.id)
                .where(MessageCostRecord.source == "estimated", *delivered_filter)
                .distinct()
            )
        ).all()
        return CostSummary(
            "estimated", estimated_amount,
            sources[0].currency, None,
            sources[0].evidence_reference if len({item.evidence_reference for item in sources}) == 1 else None,
            tuple(sorted({item.rate_version for item in sources})), coverage,
        )
    return CostSummary("unavailable", None, None, "incomplete_coverage", None, (), coverage)
