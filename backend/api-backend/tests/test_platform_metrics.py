"""Contrato T022 para los conteos administrativos de citas y clientes.

Requiere TEST_DATABASE_URL hacia PostgreSQL local desechable
``smartbooking_migration_test_*``. El endpoint se implementa en T023.

Definición propuesta para revisión Sol: ``from`` incluido y ``to`` excluido,
ambos instantes ISO-8601 en UTC; cada cita se cuenta por su fila y estado P/C/A/D;
clientes con citas son customer_id distintos dentro del negocio y periodo. No se
fija aquí si citas canceladas cuentan como cliente con cita, ni cómo agrupar
estados desconocidos: esas definiciones siguen pendientes de acuerdo.
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.models import Appointment, Business, Customer, MessageEvent, Owner, PlatformAdmin, Service
from app.services.message_costs import record_reconciled_period_total
from main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]


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
        raise ValueError("Refusing platform metrics tests outside local disposable DB")
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
async def api(test_database_url):
    engine = create_async_engine(
        test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def test_db():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def _admin_headers(client, factory):
    nonce = uuid4().hex
    async with factory() as db, db.begin():
        admin = PlatformAdmin(
            email=f"metrics-admin-{nonce}@example.test",
            hashed_password=get_password_hash("valid-test-admin-password"),
            is_active=True,
        )
        db.add(admin)
        await db.flush()
        admin_id, email = admin.id, admin.email
    login = await client.post(
        "/api/platform/auth/token",
        data={"username": email, "password": "valid-test-admin-password"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, admin_id


async def _seed_metrics(factory):
    nonce = uuid4().hex
    # Evita contaminar el agregado global con filas de otras ejecuciones.
    start = datetime(2040, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=uuid4().int % 100000
    )
    end = start + timedelta(days=1)
    async with factory() as db, db.begin():
        owners = [
            Owner(
                email=f"metrics-owner-{nonce}-{index}@example.test",
                hashed_password=get_password_hash("valid-test-owner-password"),
                email_verified=True,
                is_active=True,
            )
            for index in (1, 2)
        ]
        db.add_all(owners)
        await db.flush()
        businesses = [
            Business(
                name=f"Métrica {nonce} {index}",
                phone_number=f"+1809{nonce[:10]}{index}",
                owner_id=owners[index - 1].id,
                is_active=True,
            )
            for index in (1, 2)
        ]
        db.add_all(businesses)
        await db.flush()
        customers = [
            Customer(
                name=f"Cliente {index}",
                phone_number=f"+1808{nonce[:10]}{index}",
                business_id=businesses[business_index].id,
            )
            for business_index, index in ((0, 1), (0, 2), (1, 3))
        ]
        db.add_all(customers)
        services = [
            Service(
                name=f"Servicio {index}",
                duration_minutes=30,
                price=100,
                business_id=business.id,
            )
            for index, business in enumerate(businesses, start=1)
        ]
        db.add_all(services)
        await db.flush()
        db.add_all(
            [
                Appointment(
                    date=start,
                    status="C",
                    business_id=businesses[0].id,
                    customer_id=customers[0].id,
                    service_id=services[0].id,
                ),
                Appointment(
                    date=start + timedelta(hours=1),
                    status="P",
                    business_id=businesses[0].id,
                    customer_id=customers[0].id,
                    service_id=services[0].id,
                ),
                Appointment(
                    date=start + timedelta(hours=2),
                    status="D",
                    business_id=businesses[0].id,
                    customer_id=customers[1].id,
                    service_id=services[0].id,
                ),
                Appointment(
                    date=start,
                    status="C",
                    business_id=businesses[1].id,
                    customer_id=customers[2].id,
                    service_id=services[1].id,
                ),
                # Delimitador de fin excluido del periodo; no aumenta los totales.
                Appointment(
                    date=end,
                    status="A",
                    business_id=businesses[0].id,
                    customer_id=customers[1].id,
                    service_id=services[0].id,
                ),
            ]
        )
        await db.flush()
        return start, end, [business.id for business in businesses]


@pytest.mark.asyncio
async def test_platform_metrics_requires_platform_admin(api):
    client, _factory = api
    response = await client.get(
        "/api/platform/metrics",
        params={"from": "2026-08-01T00:00:00Z", "to": "2026-08-02T00:00:00Z"},
    )
    assert response.status_code == 401

    _start, _end, business_ids = await _seed_metrics(_factory)
    async with _factory() as db:
        owner_id = await db.scalar(
            select(Business.owner_id).where(Business.id == business_ids[0])
        )
        owner = await db.get(Owner, owner_id)
    owner_token = create_access_token(
        {"sub": str(owner_id), "email": owner.email, "principal_type": "owner"}
    )
    owner_response = await client.get(
        "/api/platform/metrics",
        params={"from": "2026-08-01T00:00:00Z", "to": "2026-08-02T00:00:00Z"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_response.status_code == 401


@pytest.mark.asyncio
async def test_global_and_per_business_counts_match_source_rows_and_half_open_period(api):
    client, factory = api
    start, end, business_ids = await _seed_metrics(factory)
    headers, _admin_id = await _admin_headers(client, factory)
    response = await client.get(
        "/api/platform/metrics",
        params={"from": start.isoformat(), "to": end.isoformat(), "offset": 0, "limit": 100},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "timezone": "UTC",
    }
    assert payload["definitions"]["appointments"]["source"] == "appointments"
    assert payload["definitions"]["appointments"]["formula"]
    assert payload["definitions"]["customers_with_appointments"]["source"] == "appointments"
    assert payload["definitions"]["customers_with_appointments"]["formula"]
    assert payload["global"]["appointments"] == {
        "total": 4, "by_status": {"P": 1, "C": 2, "A": 0, "D": 1},
    }
    assert payload["global"]["customers_with_appointments"] == 3
    assert payload["global"]["messages"] == {"total": 0, "by_status": {}}
    assert payload["global"]["cost"]["status"] == "unavailable"
    assert payload["global"]["cost"]["amount"] is None
    rows = {row["business_id"]: row for row in payload["businesses"]["items"]}
    assert payload["businesses"]["total"] >= 2
    assert rows[business_ids[0]]["appointments"] == {
        "total": 3,
        "by_status": {"P": 1, "C": 1, "A": 0, "D": 1},
    }
    assert rows[business_ids[0]]["customers_with_appointments"] == 2
    assert rows[business_ids[0]]["cost"]["status"] == "unavailable"
    assert rows[business_ids[0]]["cost"]["amount"] is None
    assert rows[business_ids[1]]["appointments"] == {
        "total": 1,
        "by_status": {"P": 0, "C": 1, "A": 0, "D": 0},
    }
    assert rows[business_ids[1]]["customers_with_appointments"] == 1
    assert "phone_number" not in rows[business_ids[0]]
    assert "customers" not in rows[business_ids[0]]


@pytest.mark.asyncio
async def test_message_metrics_use_canonical_status_and_expose_missing_cost_coverage(api):
    client, factory = api
    start, end, business_ids = await _seed_metrics(factory)
    headers, _admin_id = await _admin_headers(client, factory)
    async with factory() as db, db.begin():
        db.add_all([
            MessageEvent(
                business_id=business_ids[0], channel="whatsapp",
                event_key=f"message:{uuid4().hex}", provider_message_id=f"wamid.{uuid4().hex}",
                direction="outbound", status=status, occurred_at=start + timedelta(hours=1),
            )
            for status in ("sent", "delivered", "failed")
        ])
        db.add(MessageEvent(
            business_id=business_ids[0], channel="whatsapp",
            event_key=f"status:{uuid4().hex}", provider_message_id=f"wamid.{uuid4().hex}",
            direction="outbound", status="delivered", occurred_at=start + timedelta(hours=1),
        ))
        db.add(MessageEvent(
            business_id=business_ids[1], channel="whatsapp",
            event_key=f"message:{uuid4().hex}", provider_message_id=f"wamid.{uuid4().hex}",
            direction="outbound", status="read", occurred_at=start + timedelta(hours=1),
        ))
    response = await client.get(
        "/api/platform/metrics",
        params={"from": start.isoformat(), "to": end.isoformat(), "limit": 100},
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["global"]["messages"] == {
        "total": 4, "by_status": {"sent": 1, "delivered": 1, "failed": 1, "read": 1},
    }
    assert payload["global"]["cost"]["status"] == "unavailable"
    assert payload["global"]["cost"]["coverage"] == {"delivered": 2, "priced": 0}
    rows = {row["business_id"]: row for row in payload["businesses"]["items"]}
    assert rows[business_ids[0]]["messages"] == {
        "total": 3, "by_status": {"sent": 1, "delivered": 1, "failed": 1},
    }
    assert rows[business_ids[0]]["cost"]["coverage"] == {"delivered": 1, "priced": 0}
    assert rows[business_ids[1]]["cost"]["coverage"] == {"delivered": 1, "priced": 0}
    assert payload["definitions"]["messages"]["source"] == "message_events"
    assert payload["definitions"]["cost"]["source"] == "message_cost_records"

    async with factory() as db, db.begin():
        await record_reconciled_period_total(
            db, business_ids[0], start, end,
            amount=Decimal("0.012000"), currency="USD",
            evidence_reference="invoice-test-metrics", verified_complete=True,
        )
    after_reconciliation = await client.get(
        "/api/platform/metrics",
        params={"from": start.isoformat(), "to": end.isoformat(), "limit": 100},
        headers=headers,
    )
    assert after_reconciliation.status_code == 200
    reconciled_payload = after_reconciliation.json()
    rows = {row["business_id"]: row for row in reconciled_payload["businesses"]["items"]}
    assert rows[business_ids[0]]["cost"]["status"] == "actual"
    assert rows[business_ids[0]]["cost"]["amount"] == "0.012000"
    assert rows[business_ids[0]]["cost"]["source_reference"] == "invoice-test-metrics"
    assert reconciled_payload["global"]["cost"]["status"] == "unavailable"
    assert reconciled_payload["global"]["cost"]["reason"] == "partial_reconciliation"


@pytest.mark.asyncio
async def test_metrics_validate_period_and_paginate_business_rows(api):
    client, factory = api
    start, end, _business_ids = await _seed_metrics(factory)
    headers, _admin_id = await _admin_headers(client, factory)
    params = {"from": start.isoformat(), "to": end.isoformat(), "offset": 0, "limit": 1}
    response = await client.get("/api/platform/metrics", params=params, headers=headers)
    assert response.status_code == 200
    assert response.json()["businesses"]["limit"] == 1
    assert len(response.json()["businesses"]["items"]) == 1

    invalid = await client.get(
        "/api/platform/metrics",
        params={"from": end.isoformat(), "to": start.isoformat()},
        headers=headers,
    )
    assert invalid.status_code == 422

    naive = await client.get(
        "/api/platform/metrics",
        params={"from": "2026-08-01T00:00:00", "to": "2026-08-02T00:00:00"},
        headers=headers,
    )
    assert naive.status_code == 422

    too_long = await client.get(
        "/api/platform/metrics",
        params={"from": start.isoformat(), "to": (start + timedelta(days=367)).isoformat()},
        headers=headers,
    )
    assert too_long.status_code == 422

    invalid_page = await client.get(
        "/api/platform/metrics",
        params={"from": start.isoformat(), "to": end.isoformat(), "limit": 101},
        headers=headers,
    )
    assert invalid_page.status_code == 422
