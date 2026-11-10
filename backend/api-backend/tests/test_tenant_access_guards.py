"""T008: permisos de dueño y estado de negocio con sesiones ya emitidas."""

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
from app.models import Business, BusinessMembership, Owner, RefreshToken
from app.services.refresh_token_service import hash_refresh_plain, issue_refresh_token
from main import app


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "valid-owner-password-123"


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
        raise ValueError("Refusing tenant guard tests outside local disposable DB")
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
    engine = create_async_engine(test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1))
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


async def seed_owner(factory, *, business=True, active=True, complete=True):
    nonce = uuid4().hex
    async with factory() as db, db.begin():
        owner = Owner(
            name="Dueño de prueba",
            email=f"owner-{nonce}@example.test",
            hashed_password=get_password_hash(PASSWORD),
            email_verified=True,
            is_active=True,
        )
        db.add(owner)
        await db.flush()
        business_id = None
        if business:
            account = Business(
                name=f"Negocio {nonce}",
                phone_number=nonce[:16],
                owner_id=owner.id,
                is_active=active,
                onboarding_completed_at=datetime.now(timezone.utc) if complete else None,
            )
            db.add(account)
            await db.flush()
            business_id = account.id
        owner_id, email = owner.id, owner.email
    token = create_access_token({"sub": str(owner_id), "email": email, "principal_type": "owner"})
    return owner_id, business_id, {"Authorization": f"Bearer {token}"}, email


@pytest.mark.asyncio
async def test_cross_business_and_anonymous_writes_are_rejected(api):
    client, factory = api
    _, first_business, first_headers, _ = await seed_owner(factory)
    _, second_business, second_headers, _ = await seed_owner(factory)

    assert (await client.get(f"/api/businesses/{first_business}/services", headers=first_headers)).status_code == 200
    assert (await client.get(f"/api/businesses/{second_business}/services", headers=first_headers)).status_code == 404
    assert (await client.post(f"/api/businesses/{first_business}/customers", json={"phone_number": "8095551234"})).status_code == 401
    assert (await client.post(f"/api/businesses/{first_business}/customers", json={"phone_number": "8095551234"}, headers=second_headers)).status_code == 404
    assert (await client.post(f"/api/businesses/{first_business}/customers", json={"phone_number": "8095551234"}, headers=first_headers)).status_code == 201
    assert (await client.post(
        f"/api/businesses/{first_business}/appointments",
        json={"date": "2026-12-01T10:00:00Z", "service_id": 1, "customer_id": 1},
    )).status_code == 401


@pytest.mark.asyncio
async def test_suspending_owner_invalidates_existing_access_and_new_login(api):
    client, factory = api
    owner_id, business_id, headers, email = await seed_owner(factory)
    assert (await client.get("/api/owners/me", headers=headers)).status_code == 200
    async with factory() as db, db.begin():
        owner = await db.get(Owner, owner_id)
        owner.is_active = False
    assert (await client.get("/api/owners/me", headers=headers)).status_code == 401
    assert (await client.get(f"/api/businesses/{business_id}/services", headers=headers)).status_code == 401
    login = await client.post("/api/auth/token", data={"username": email, "password": PASSWORD})
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_suspended_owner_cannot_rotate_previous_refresh_token(api):
    client, factory = api
    owner_id, _, _, _ = await seed_owner(factory)
    refresh = await issue_refresh_token(owner_id)
    async with factory() as db, db.begin():
        owner = await db.get(Owner, owner_id)
        owner.is_active = False
    response = await client.post("/api/auth/refresh", json={"refresh": refresh})
    assert response.status_code == 401
    async with factory() as db:
        rows = (await db.execute(select(RefreshToken).where(RefreshToken.owner_id == owner_id))).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_incomplete_business_can_finish_onboarding_then_operate(api):
    client, factory = api
    _, business_id, headers, _ = await seed_owner(factory, complete=False)
    assert (await client.get(f"/api/businesses/{business_id}", headers=headers)).status_code == 200
    assert (await client.get(f"/api/businesses/{business_id}/services", headers=headers)).status_code == 403
    assert (await client.post(f"/api/businesses/{business_id}/customers", json={"phone_number": "8095551234"}, headers=headers)).status_code == 403
    updated = await client.patch(
        f"/api/businesses/{business_id}",
        json={"name": "Negocio completo", "phone_number": uuid4().hex[:16]},
        headers=headers,
    )
    assert updated.status_code == 200
    async with factory() as db:
        business = await db.get(Business, business_id)
        assert business.onboarding_completed_at is not None
    assert (await client.get(f"/api/businesses/{business_id}/services", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_suspended_business_cannot_operate_or_self_reactivate(api):
    client, factory = api
    _, business_id, headers, _ = await seed_owner(factory)
    async with factory() as db, db.begin():
        business = await db.get(Business, business_id)
        business.is_active = False
    assert (await client.get(f"/api/businesses/{business_id}/services", headers=headers)).status_code == 403
    assert (await client.post(f"/api/businesses/{business_id}/customers", json={"phone_number": "8095551234"}, headers=headers)).status_code == 403
    assert (await client.patch(f"/api/businesses/{business_id}", json={"is_active": True}, headers=headers)).status_code == 403
    assert (await client.get("/api/dashboard/metrics/", params={"business_id": business_id}, headers=headers)).status_code == 403
    assert (await client.get("/api/schedule-rules/", params={"business_id": business_id}, headers=headers)).status_code == 403
    assert (await client.get(f"/api/businesses/{business_id}/telegram", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_business_creation_completes_onboarding_and_preserves_single_business_rule(api):
    client, factory = api
    owner_id, _, headers, _ = await seed_owner(factory, business=False)
    assert (await client.get("/api/businesses/", headers=headers)).json() == []
    created = await client.post(
        "/api/businesses/", json={"name": "Mi negocio", "phone_number": uuid4().hex[:16]}, headers=headers
    )
    assert created.status_code == 201
    business_id = created.json()["id"]
    async with factory() as db:
        business = await db.get(Business, business_id)
        assert business.onboarding_completed_at is not None
        memberships = (await db.execute(select(BusinessMembership).where(
            BusinessMembership.business_id == business_id
        ))).scalars().all()
        assert len(memberships) == 1
        assert memberships[0].user_id == owner_id
        assert memberships[0].role == "owner"
        assert memberships[0].is_active is True
    assert (await client.get(f"/api/businesses/{business_id}/services", headers=headers)).status_code == 200
    assert (await client.post(
        "/api/businesses/", json={"name": "Otro", "phone_number": uuid4().hex[:16]}, headers=headers
    )).status_code == 409


@pytest.mark.asyncio
async def test_owner_logout_revokes_previously_issued_access_token(api):
    client, factory = api
    _, _, _, email = await seed_owner(factory, business=False)
    login = await client.post("/api/auth/token", data={"username": email, "password": PASSWORD})
    assert login.status_code == 200
    access = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}
    assert (await client.get("/api/owners/me", headers=headers)).status_code == 200
    assert (await client.post("/api/auth/logout", headers=headers)).status_code == 200
    assert (await client.get("/api/owners/me", headers=headers)).status_code == 401
    async with factory() as db:
        assert (await db.execute(select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_plain(login.json()["refresh"])
        ))).scalars().all() == []
    relogin = await client.post("/api/auth/token", data={"username": email, "password": PASSWORD})
    assert relogin.status_code == 200
    new_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}
    assert (await client.get("/api/owners/me", headers=new_headers)).status_code == 200


@pytest.mark.asyncio
async def test_invalid_business_profile_does_not_finish_onboarding(api):
    client, factory = api
    owner_id, _, headers, _ = await seed_owner(factory, business=False)
    response = await client.post(
        "/api/businesses/", json={"name": "   ", "phone_number": "   "}, headers=headers
    )
    assert response.status_code == 422
    async with factory() as db:
        rows = (await db.execute(select(Business).where(Business.owner_id == owner_id))).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_simultaneous_business_creation_keeps_one_business_per_owner(api):
    import asyncio

    client, factory = api
    owner_id, _, headers, _ = await seed_owner(factory, business=False)
    responses = await asyncio.gather(
        client.post("/api/businesses/", json={"name": "Uno", "phone_number": uuid4().hex[:16]}, headers=headers),
        client.post("/api/businesses/", json={"name": "Dos", "phone_number": uuid4().hex[:16]}, headers=headers),
    )
    assert sorted(response.status_code for response in responses) == [201, 409]
    async with factory() as db:
        rows = (await db.execute(select(Business).where(Business.owner_id == owner_id))).scalars().all()
        assert len(rows) == 1
