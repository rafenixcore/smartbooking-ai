"""T018: contrato de autorización, estado de negocio y auditoría de plataforma.

Requiere TEST_DATABASE_URL hacia PostgreSQL local desechable
``smartbooking_migration_test_*``. Estos casos preceden a la implementación T019.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.models import AdminAuditEvent, Business, Owner, PlatformAdmin
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
        raise ValueError("Refusing platform business tests outside local disposable DB")
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


async def seed_business_and_principals(factory):
    nonce = uuid4().hex
    async with factory() as db, db.begin():
        owner = Owner(
            name="Dueño de prueba",
            email=f"owner-{nonce}@example.test",
            hashed_password=get_password_hash("a-valid-owner-password"),
            email_verified=True,
            is_active=True,
        )
        admin = PlatformAdmin(
            email=f"admin-{nonce}@example.test",
            hashed_password=get_password_hash("a-valid-admin-password"),
            is_active=True,
        )
        db.add_all([owner, admin])
        await db.flush()
        business = Business(
            name=f"Negocio {nonce}",
            phone_number=nonce[:16],
            owner_id=owner.id,
            is_active=True,
            onboarding_completed_at=datetime.now(timezone.utc),
        )
        db.add(business)
        await db.flush()
        business_id, owner_id, owner_email, admin_id = (
            business.id,
            owner.id,
            owner.email,
            admin.id,
        )

    owner_token = create_access_token(
        {"sub": str(owner_id), "email": owner_email, "principal_type": "owner"}
    )
    return business_id, {"Authorization": f"Bearer {owner_token}"}, admin_id


async def platform_headers(client, factory, admin_id):
    async with factory() as db:
        admin = await db.get(PlatformAdmin, admin_id)
        email = admin.email
    login = await client.post(
        "/api/platform/auth/token",
        data={"username": email, "password": "a-valid-admin-password"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_platform_business_routes_reject_public_and_owner(api):
    client, factory = api
    business_id, owner_headers, admin_id = await seed_business_and_principals(factory)
    path = "/api/platform/businesses"

    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers=owner_headers)).status_code == 401
    assert (await client.post(f"{path}/{business_id}/suspend")).status_code == 401
    assert (
        await client.post(f"{path}/{business_id}/reactivate", headers=owner_headers)
    ).status_code == 401
    assert await platform_headers(client, factory, admin_id)


@pytest.mark.asyncio
async def test_admin_list_is_paginated_and_limited_to_business_identity(api):
    client, factory = api
    first_id, first_owner_headers, admin_id = await seed_business_and_principals(factory)
    second_id, _, _ = await seed_business_and_principals(factory)
    headers = await platform_headers(client, factory, admin_id)

    listed = await client.get(
        "/api/platform/businesses", params={"offset": 0, "limit": 100}, headers=headers
    )
    assert listed.status_code == 200
    data = listed.json()
    assert data["total"] >= 2
    assert data["offset"] == 0
    assert data["limit"] == 100
    rows = {row["id"]: row for row in data["items"]}
    assert first_id in rows and second_id in rows
    for business_id in (first_id, second_id):
        assert rows[business_id]["name"].startswith("Negocio ")
        assert rows[business_id]["is_active"] is True
        assert "phone_number" not in rows[business_id]
        assert "customers" not in rows[business_id]

    detail = await client.get(f"/api/platform/businesses/{first_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == first_id
    assert detail.json()["owner_email"].startswith("owner-")
    assert "phone_number" not in detail.json()
    assert (
        await client.get(f"/api/platform/businesses/{first_id}")
    ).status_code == 401
    assert (
        await client.get(f"/api/platform/businesses/{first_id}", headers=first_owner_headers)
    ).status_code == 401

    page = await client.get(
        "/api/platform/businesses", params={"offset": 0, "limit": 1}, headers=headers
    )
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert (
        await client.get(
            "/api/platform/businesses", params={"status": "unknown"}, headers=headers
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_admin_suspend_and_reactivate_preserve_business_and_audit(api):
    client, factory = api
    business_id, owner_headers, admin_id = await seed_business_and_principals(factory)
    admin_headers = await platform_headers(client, factory, admin_id)
    path = f"/api/platform/businesses/{business_id}"

    suspended = await client.post(f"{path}/suspend", headers=admin_headers)
    assert suspended.status_code == 200
    async with factory() as db:
        business = await db.get(Business, business_id)
        assert business.is_active is False
        owner = await db.get(Owner, business.owner_id)
        assert owner.is_active is True
    operational = await client.get(
        f"/api/businesses/{business_id}/services", headers=owner_headers
    )
    assert operational.status_code == 403
    suspended_list = await client.get(
        "/api/platform/businesses", params={"status": "suspended"}, headers=admin_headers
    )
    assert suspended_list.status_code == 200
    assert business_id in {row["id"] for row in suspended_list.json()["items"]}

    reactivated = await client.post(f"{path}/reactivate", headers=admin_headers)
    assert reactivated.status_code == 200
    assert (
        await client.get(f"/api/businesses/{business_id}/services", headers=owner_headers)
    ).status_code == 200

    async with factory() as db:
        business = await db.get(Business, business_id)
        events = list(
            (
                await db.scalars(
                    select(AdminAuditEvent)
                    .where(
                        AdminAuditEvent.admin_id == admin_id,
                        AdminAuditEvent.entity_type == "business",
                        AdminAuditEvent.entity_id == str(business_id),
                    )
                    .order_by(AdminAuditEvent.id)
                )
            ).all()
        )
        assert business.name.startswith("Negocio ")
        assert len(events) == 2
        assert all(event.action and event.outcome for event in events)

    audit_path = "/api/platform/audit"
    assert (await client.get(audit_path)).status_code == 401
    assert (await client.get(audit_path, headers=owner_headers)).status_code == 401
    audit = await client.get(
        audit_path,
        params={"entity_type": "business", "entity_id": str(business_id)},
        headers=admin_headers,
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 2
    for event in audit.json()["items"]:
        assert event["admin_id"] == admin_id
        assert event["entity_type"] == "business"
        assert event["entity_id"] == str(business_id)
        assert event["outcome"] == "success"
        assert "details" not in event
        assert "token" not in event


@pytest.mark.asyncio
async def test_admin_cannot_change_missing_business(api):
    client, factory = api
    _, _, admin_id = await seed_business_and_principals(factory)
    headers = await platform_headers(client, factory, admin_id)
    assert (
        await client.post("/api/platform/businesses/2147483647/suspend", headers=headers)
    ).status_code == 404
    async with factory() as db:
        event = await db.scalar(
            select(AdminAuditEvent).where(
                AdminAuditEvent.admin_id == admin_id,
                AdminAuditEvent.entity_type == "business",
                AdminAuditEvent.entity_id == "2147483647",
            )
        )
        assert event is not None
        assert event.outcome == "not_found"


@pytest.mark.asyncio
async def test_repeated_suspend_is_idempotent_and_audited(api):
    client, factory = api
    business_id, _, admin_id = await seed_business_and_principals(factory)
    headers = await platform_headers(client, factory, admin_id)
    path = f"/api/platform/businesses/{business_id}/suspend"
    assert (await client.post(path, headers=headers)).status_code == 200
    assert (await client.post(path, headers=headers)).status_code == 200
    async with factory() as db:
        business = await db.get(Business, business_id)
        events = (
            await db.scalars(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.entity_type == "business",
                    AdminAuditEvent.entity_id == str(business_id),
                    AdminAuditEvent.admin_id == admin_id,
                )
                .order_by(AdminAuditEvent.id)
            )
        ).all()
        assert business.is_active is False
        assert [event.outcome for event in events] == ["success", "unchanged"]
