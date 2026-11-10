"""T025: un estimado exige tarifa trazable; gasto real exige conciliación."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import get_password_hash
from app.models import Business, MessageCostRecord, MessageEvent, Owner
from app.services.message_costs import (
    VersionedRate,
    estimate_message_cost,
    record_reconciled_period_total,
    summarize_costs,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PERIOD_START = datetime(2026, 11, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 12, 1, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def test_database_url():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    parsed = urlparse(url)
    if (
        parsed.hostname is not None
        or parse_qs(parsed.query).get("host") != ["/tmp"]
        or parse_qs(parsed.query).get("port") != ["55432"]
        or not parsed.path.lstrip("/").startswith("smartbooking_migration_test_")
    ):
        raise ValueError("Refusing cost tests outside local disposable DB")
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return url


@pytest.fixture
async def factory(test_database_url):
    engine = create_async_engine(
        test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_delivered(factory, *, category="utility", country="DO"):
    nonce = uuid4().hex
    async with factory() as db, db.begin():
        owner = Owner(
            email=f"cost-{nonce}@example.test",
            hashed_password=get_password_hash("valid-test-password"),
            email_verified=True,
            is_active=True,
        )
        db.add(owner)
        await db.flush()
        business = Business(
            name=f"Costo {nonce}",
            phone_number=f"+1809{nonce[:11]}",
            owner_id=owner.id,
            is_active=True,
        )
        db.add(business)
        await db.flush()
        event = MessageEvent(
            business_id=business.id,
            channel="whatsapp",
            event_key=f"message:{nonce}",
            provider_message_id=f"wamid.{nonce}",
            direction="outbound",
            status="delivered",
            category=category,
            country=country,
            occurred_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
        db.add(event)
        await db.flush()
        return business.id, event.provider_message_id, event.id


def _test_rate(*, version="test-v1", amount="0.015000"):
    return VersionedRate(
        category="utility",
        country="DO",
        currency="USD",
        amount_per_delivery=Decimal(amount),
        version=version,
        source_reference="https://example.test/meta-rate-snapshot",
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_missing_rate_or_category_never_creates_a_cost(factory):
    business_id, wamid, _event_id = await _seed_delivered(factory)
    missing_business_id, missing_wamid, _ = await _seed_delivered(factory, country=None)
    async with factory() as db:
        without_rate = await estimate_message_cost(db, business_id, wamid, rate=None)
        without_country = await estimate_message_cost(
            db, missing_business_id, missing_wamid, rate=_test_rate()
        )
        await db.commit()
        count = await db.scalar(
            select(func.count(MessageCostRecord.id)).where(
                MessageCostRecord.business_id.in_([business_id, missing_business_id])
            )
        )
    assert without_rate.status == "unavailable"
    assert without_rate.amount is None
    assert without_country.status == "unavailable"
    assert without_country.amount is None
    assert count == 0


@pytest.mark.asyncio
async def test_verified_rate_creates_one_versioned_estimate_and_not_actual(factory):
    business_id, wamid, event_id = await _seed_delivered(factory)
    async with factory() as db:
        first = await estimate_message_cost(db, business_id, wamid, rate=_test_rate())
        repeated = await estimate_message_cost(db, business_id, wamid, rate=_test_rate())
        await db.commit()
        records = (
            await db.execute(select(MessageCostRecord).where(MessageCostRecord.business_id == business_id))
        ).scalars().all()
        summary = await summarize_costs(db, business_id, PERIOD_START, PERIOD_END)
    assert first.status == repeated.status == "estimated"
    assert first.amount == Decimal("0.015000")
    assert len(records) == 1
    assert records[0].source == "estimated"
    assert records[0].message_event_id == event_id
    assert records[0].rate_version == "test-v1"
    assert records[0].evidence_reference == "https://example.test/meta-rate-snapshot"
    assert summary.status == "estimated"
    assert summary.amount == Decimal("0.015000")
    assert summary.coverage == {"delivered": 1, "priced": 1}


@pytest.mark.asyncio
async def test_rate_revision_replaces_estimate_without_double_counting(factory):
    business_id, wamid, _event_id = await _seed_delivered(factory)
    async with factory() as db:
        await estimate_message_cost(db, business_id, wamid, rate=_test_rate())
        revised = await estimate_message_cost(
            db, business_id, wamid, rate=_test_rate(version="test-v2", amount="0.020000")
        )
        await db.commit()
        records = (
            await db.execute(select(MessageCostRecord).where(MessageCostRecord.business_id == business_id))
        ).scalars().all()
    assert revised.status == "estimated"
    assert len(records) == 1
    assert records[0].amount == Decimal("0.020000")
    assert records[0].rate_version == "test-v2"


@pytest.mark.asyncio
async def test_incomplete_coverage_is_unavailable_even_when_one_message_is_priced(factory):
    business_id, wamid, _event_id = await _seed_delivered(factory)
    async with factory() as db:
        another = MessageEvent(
            business_id=business_id,
            channel="whatsapp",
            event_key=f"message:{uuid4().hex}",
            provider_message_id=f"wamid.{uuid4().hex}",
            direction="outbound",
            status="read",
            occurred_at=datetime(2026, 11, 16, tzinfo=timezone.utc),
        )
        db.add(another)
        await db.flush()
        await estimate_message_cost(db, business_id, wamid, rate=_test_rate())
        await db.commit()
        summary = await summarize_costs(db, business_id, PERIOD_START, PERIOD_END)
    assert summary.status == "unavailable"
    assert summary.amount is None
    assert summary.coverage == {"delivered": 2, "priced": 1}


@pytest.mark.asyncio
async def test_real_cost_requires_complete_period_and_evidence(factory):
    business_id, wamid, _event_id = await _seed_delivered(factory)
    async with factory() as db:
        await estimate_message_cost(db, business_id, wamid, rate=_test_rate())
        with pytest.raises(ValueError):
            await record_reconciled_period_total(
                db, business_id, PERIOD_START, PERIOD_END,
                amount=Decimal("0.014000"), currency="USD",
                evidence_reference="invoice-test-001", verified_complete=False,
            )
        with pytest.raises(ValueError):
            await record_reconciled_period_total(
                db, business_id, PERIOD_START, PERIOD_END,
                amount=Decimal("0.014000"), currency="USD",
                evidence_reference="", verified_complete=True,
            )
        actual = await record_reconciled_period_total(
            db, business_id, PERIOD_START, PERIOD_END,
            amount=Decimal("0.014000"), currency="USD",
            evidence_reference="invoice-test-001", verified_complete=True,
        )
        same = await record_reconciled_period_total(
            db, business_id, PERIOD_START, PERIOD_END,
            amount=Decimal("0.014000"), currency="USD",
            evidence_reference="invoice-test-001", verified_complete=True,
        )
        await db.commit()
        summary = await summarize_costs(db, business_id, PERIOD_START, PERIOD_END)
    assert actual.id == same.id
    assert actual.source == "reconciled"
    assert actual.evidence_reference == "invoice-test-001"
    assert summary.status == "actual"
    assert summary.amount == Decimal("0.014000")
    assert summary.source_reference == "invoice-test-001"


def test_rate_source_and_validity_are_required():
    with pytest.raises(ValueError):
        VersionedRate(
            category="utility",
            country="DO",
            currency="USD",
            amount_per_delivery=Decimal("0.015000"),
            version="",
            source_reference="",
            effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
