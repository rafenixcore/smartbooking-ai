"""T006: exercise platform login, refresh rotation and revocation over HTTP.

Requires a disposable local PostgreSQL database named
``smartbooking_migration_test_*``. Never uses the application's production URL.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from ipaddress import IPv6Address
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models import PlatformAdmin, PlatformAdminSession, PlatformLoginAttempt
from main import app


BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
async def limited_login_client(test_database_url):
    async_url = test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(async_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def test_db():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    ip = str(IPv6Address(uuid4().int))
    try:
        transport = httpx.ASGITransport(app=app, client=(ip, 12345))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, factory, ip
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.asyncio
async def test_admin_login_failed_attempts_are_limited_by_email_and_ip(limited_login_client):
    client, factory, ip = limited_login_client
    email = f"rate-{uuid4().hex}@example.test"
    async with factory() as db, db.begin():
        db.add(PlatformAdmin(email=email, hashed_password=get_password_hash("valid-long-password")))

    for _ in range(5):
        response = await client.post("/api/platform/auth/token", data={"username": email, "password": "wrong"})
        assert response.status_code == 401
    assert (await client.post("/api/platform/auth/token", data={"username": email, "password": "wrong"})).status_code == 429

    for _ in range(15):
        another = f"unknown-{uuid4().hex}@example.test"
        assert (await client.post("/api/platform/auth/token", data={"username": another, "password": "wrong"})).status_code == 401
    fresh = f"fresh-{uuid4().hex}@example.test"
    assert (await client.post("/api/platform/auth/token", data={"username": fresh, "password": "wrong"})).status_code == 429
    async with factory() as db:
        rows = (await db.execute(select(PlatformLoginAttempt).order_by(PlatformLoginAttempt.id.desc()).limit(20))).scalars().all()
        assert len(rows) == 20
        assert all(len(row.email_hash) == 64 and len(row.ip_hash) == 64 for row in rows)
        assert email not in str([row.__dict__ for row in rows])
        assert ip not in str([row.__dict__ for row in rows])

    other_transport = httpx.ASGITransport(app=app, client=(str(IPv6Address(uuid4().int)), 12345))
    async with httpx.AsyncClient(transport=other_transport, base_url="http://test") as other_client:
        assert (await other_client.post("/api/platform/auth/token", data={"username": fresh, "password": "wrong"})).status_code == 401


@pytest.mark.asyncio
async def test_admin_login_limit_is_exact_under_concurrency(limited_login_client):
    client, _, _ = limited_login_client
    email = f"concurrent-rate-{uuid4().hex}@example.test"
    responses = await asyncio.gather(*[
        client.post("/api/platform/auth/token", data={"username": email, "password": "wrong"})
        for _ in range(6)
    ])
    assert sorted(response.status_code for response in responses) == [401] * 5 + [429]


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
        raise ValueError("Refusing to run platform auth flow outside local disposable DB")

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


@pytest.mark.asyncio
async def test_admin_login_refresh_and_logout_invalidate_session(test_database_url):
    password = "correct-horse-battery-staple"
    email = f"platform-{uuid4().hex}@example.test"
    sync_engine = create_engine(test_database_url)
    with sync_engine.begin() as connection:
        admin_id = connection.execute(
            PlatformAdmin.__table__.insert()
            .values(email=email, hashed_password=get_password_hash(password))
            .returning(PlatformAdmin.id)
        ).scalar_one()
    sync_engine.dispose()

    async_url = test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    async_engine = create_async_engine(async_url)
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def test_db():
        async with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/platform/auth/token",
                data={"username": email.upper(), "password": password},
            )
            assert login.status_code == 200
            first = login.json()
            assert first["admin"] == {"id": admin_id, "email": email}
            assert first["token_type"] == "bearer"
            assert first["refresh"]
            assert first["access_token"]
            assert "hashed_password" not in str(first)

            headers = {"Authorization": f"Bearer {first['access_token']}"}
            own = await client.get("/api/platform/auth/me", headers=headers)
            assert own.status_code == 200
            assert own.json() == {"id": admin_id, "email": email}

            owner_route = await client.get("/api/owners/me", headers=headers)
            assert owner_route.status_code == 401

            rotated = await client.post(
                "/api/platform/auth/refresh", json={"refresh": first["refresh"]}
            )
            assert rotated.status_code == 200
            second = rotated.json()
            assert second["refresh"] != first["refresh"]
            assert second["access_token"]

            replay = await client.post(
                "/api/platform/auth/refresh", json={"refresh": first["refresh"]}
            )
            assert replay.status_code == 401

            second_headers = {"Authorization": f"Bearer {second['access_token']}"}
            logout = await client.post("/api/platform/auth/logout", headers=second_headers)
            assert logout.status_code == 200
            assert logout.json() == {"ok": True}
            assert (
                await client.get("/api/platform/auth/me", headers=second_headers)
            ).status_code == 401
            assert (
                await client.post(
                    "/api/platform/auth/refresh", json={"refresh": second["refresh"]}
                )
            ).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        await async_engine.dispose()


@pytest.mark.asyncio
async def test_expired_admin_session_rejects_access_and_refresh(test_database_url):
    password = "correct-horse-battery-staple"
    email = f"expired-platform-{uuid4().hex}@example.test"
    sync_engine = create_engine(test_database_url)
    with sync_engine.begin() as connection:
        connection.execute(
            PlatformAdmin.__table__.insert().values(
                email=email, hashed_password=get_password_hash(password)
            )
        )

    async_url = test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    async_engine = create_async_engine(async_url)
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def test_db():
        async with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/platform/auth/token", data={"username": email, "password": password}
            )
            assert login.status_code == 200
            tokens = login.json()

            with sync_engine.begin() as connection:
                connection.execute(
                    update(PlatformAdminSession)
                    .where(PlatformAdminSession.admin_id == tokens["admin"]["id"])
                    .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
                )

            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            assert (await client.get("/api/platform/auth/me", headers=headers)).status_code == 401
            assert (
                await client.post(
                    "/api/platform/auth/refresh", json={"refresh": tokens["refresh"]}
                )
            ).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        await async_engine.dispose()
        sync_engine.dispose()
