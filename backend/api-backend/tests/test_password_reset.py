"""T015: contrato HTTP para recuperación de contraseña de dueño y plataforma.

Ejecutar solo contra PostgreSQL local desechable ``smartbooking_migration_test_*``.
La vigencia se prepara en pasado en la base para no fijar una duración de enlace
que todavía no fue aprobada como regla de producto.
"""

import asyncio
import hashlib
from ipaddress import IPv6Address
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import jwt
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models import (
    Owner,
    PasswordReset,
    PasswordResetRequestAttempt,
    PlatformAdmin,
    PlatformAdminSession,
    RefreshToken,
)
from main import app
from app.services import email_service


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
        raise ValueError("Refusing password reset tests outside local disposable DB")

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
async def api(test_database_url, monkeypatch):
    engine = create_async_engine(
        test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def test_db():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    async def no_email(_to_email, _token, _account_type):
        pass

    monkeypatch.setattr(email_service, "send_password_reset_email", no_email, raising=False)
    try:
        transport = httpx.ASGITransport(
            app=app, client=(str(IPv6Address(uuid4().int)), 12345)
        )
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def create_owner(factory, email=None):
    email = email or f"owner-{uuid4().hex}@example.test"
    async with factory() as db, db.begin():
        owner = Owner(
            name="Dueño de prueba",
            email=email,
            hashed_password=get_password_hash("current-owner-password"),
            email_verified=True,
        )
        db.add(owner)
        await db.flush()
        return owner.id, email


async def create_admin(factory, email=None):
    email = email or f"admin-{uuid4().hex}@example.test"
    async with factory() as db, db.begin():
        admin = PlatformAdmin(
            email=email,
            hashed_password=get_password_hash("current-admin-password"),
        )
        db.add(admin)
        await db.flush()
        return admin.id, email


async def seed_reset(factory, *, owner_id=None, admin_id=None, expired=False):
    assert (owner_id is None) != (admin_id is None)
    token = f"reset-{uuid4().hex}"
    expires_at = datetime.now(timezone.utc) - timedelta(seconds=1) if expired else (
        datetime.now(timezone.utc) + timedelta(hours=1)
    )
    async with factory() as db, db.begin():
        reset = PasswordReset(
            owner_id=owner_id,
            platform_admin_id=admin_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=expires_at,
        )
        db.add(reset)
        await db.flush()
        reset_id = reset.id
    return token, reset_id


@pytest.mark.asyncio
async def test_request_response_does_not_reveal_account_existence(api):
    client, factory = api
    _, owner_email = await create_owner(factory)
    _, admin_email = await create_admin(factory)
    unknown_email = f"unknown-{uuid4().hex}@example.test"

    responses = [
        await client.post("/api/auth/password-reset/request", json={"email": email})
        for email in (owner_email, admin_email, unknown_email)
    ]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert responses[0].json() == responses[1].json() == responses[2].json()
    public_body = str(responses[0].json()).lower()
    assert owner_email.lower() not in public_body
    assert admin_email.lower() not in public_body
    assert unknown_email.lower() not in public_body


@pytest.mark.asyncio
async def test_email_provider_failure_keeps_public_response_neutral(api, monkeypatch):
    client, factory = api
    _, owner_email = await create_owner(factory)
    unknown_email = f"unknown-provider-{uuid4().hex}@example.test"

    async def failed_delivery(_to_email, _token, _account_type):
        raise email_service.EmailDeliveryError("provider unavailable")

    monkeypatch.setattr(email_service, "send_password_reset_email", failed_delivery)
    known = await client.post(
        "/api/auth/password-reset/request", json={"email": owner_email}
    )
    unknown = await client.post(
        "/api/auth/password-reset/request", json={"email": unknown_email}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


@pytest.mark.asyncio
async def test_request_endpoint_limits_repeated_requests_per_email(api):
    client, factory = api
    email = f"rate-limit-{uuid4().hex}@example.test"
    async with factory() as db:
        before_count = await db.scalar(
            select(func.count()).select_from(PasswordResetRequestAttempt)
        )
    statuses = [
        (
            await client.post(
                "/api/auth/password-reset/request",
                json={"email": email.upper() if attempt % 2 else email},
            )
        ).status_code
        for attempt in range(6)
    ]
    assert statuses == [200, 200, 200, 200, 200, 429]
    async with factory() as db:
        after_count = await db.scalar(
            select(func.count()).select_from(PasswordResetRequestAttempt)
        )
        latest = (
            await db.execute(
                select(PasswordResetRequestAttempt)
                .order_by(PasswordResetRequestAttempt.id.desc())
                .limit(5)
            )
        ).scalars().all()
    assert after_count == before_count + 5
    assert all(len(attempt.email_hash) == len(attempt.ip_hash) == 64 for attempt in latest)
    assert all(email.lower() not in str(attempt.__dict__).lower() for attempt in latest)


@pytest.mark.asyncio
async def test_request_endpoint_limits_repeated_requests_per_ip(api):
    client, _ = api
    statuses = [
        (
            await client.post(
                "/api/auth/password-reset/request",
                json={"email": f"ip-limit-{uuid4().hex}@example.test"},
            )
        ).status_code
        for _ in range(21)
    ]
    assert statuses == [200] * 20 + [429]


@pytest.mark.asyncio
async def test_request_issues_hashed_one_hour_token_for_each_account_type(api, monkeypatch):
    client, factory = api
    owner_id, owner_email = await create_owner(factory)
    admin_id, admin_email = await create_admin(factory)
    sent = []

    async def capture_email(to_email, token, account_type):
        sent.append((to_email, token, account_type))

    monkeypatch.setattr(email_service, "send_password_reset_email", capture_email)
    before = datetime.now(timezone.utc)
    owner_response = await client.post(
        "/api/auth/password-reset/request", json={"email": owner_email}
    )
    admin_response = await client.post(
        "/api/auth/password-reset/request", json={"email": admin_email}
    )
    after = datetime.now(timezone.utc)

    assert owner_response.status_code == admin_response.status_code == 200
    assert len(sent) == 2
    async with factory() as db:
        owner_reset = (
            await db.execute(
                select(PasswordReset).where(PasswordReset.owner_id == owner_id)
            )
        ).scalar_one()
        admin_reset = (
            await db.execute(
                select(PasswordReset).where(PasswordReset.platform_admin_id == admin_id)
            )
        ).scalar_one()
    for email, token, account_type in sent:
        reset = owner_reset if account_type == "owner" else admin_reset
        assert email == (owner_email if account_type == "owner" else admin_email)
        assert reset.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert len(reset.token_hash) == 64
        assert before + timedelta(minutes=59) <= reset.expires_at <= after + timedelta(minutes=61)
        assert token not in str(owner_response.json())
        assert token not in str(admin_response.json())


@pytest.mark.asyncio
async def test_expired_reset_token_is_rejected_without_changing_password(api):
    client, factory = api
    owner_id, _ = await create_owner(factory)
    token, reset_id = await seed_reset(factory, owner_id=owner_id, expired=True)

    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "new-owner-password-123"},
    )

    assert response.status_code == 400
    async with factory() as db:
        owner = await db.get(Owner, owner_id)
        reset = await db.get(PasswordReset, reset_id)
    assert verify_password("current-owner-password", owner.hashed_password)
    assert reset.used_at is None


@pytest.mark.asyncio
async def test_reset_token_is_single_use(api):
    client, factory = api
    owner_id, _ = await create_owner(factory)
    token, reset_id = await seed_reset(factory, owner_id=owner_id)
    body = {"token": token, "password": "new-owner-password-123"}

    accepted = await client.post("/api/auth/password-reset/confirm", json=body)
    replay = await client.post("/api/auth/password-reset/confirm", json=body)

    assert accepted.status_code == 200
    assert replay.status_code == 400
    async with factory() as db:
        owner = await db.get(Owner, owner_id)
        reset = await db.get(PasswordReset, reset_id)
    assert verify_password("new-owner-password-123", owner.hashed_password)
    assert reset.used_at is not None


@pytest.mark.asyncio
async def test_concurrent_confirmation_and_other_pending_links_cannot_reuse_reset(api):
    client, factory = api
    owner_id, _ = await create_owner(factory)
    first_token, _ = await seed_reset(factory, owner_id=owner_id)
    second_token, _ = await seed_reset(factory, owner_id=owner_id)
    body = {"token": first_token, "password": "new-owner-password-123"}

    first, second = await asyncio.gather(
        client.post("/api/auth/password-reset/confirm", json=body),
        client.post("/api/auth/password-reset/confirm", json=body),
    )
    stale = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": second_token, "password": "another-password-123"},
    )

    assert sorted((first.status_code, second.status_code)) == [200, 400]
    assert stale.status_code == 400
    async with factory() as db:
        owner = await db.get(Owner, owner_id)
    assert verify_password("new-owner-password-123", owner.hashed_password)


@pytest.mark.asyncio
async def test_owner_reset_revokes_existing_refresh_sessions(api):
    client, factory = api
    owner_id, _ = await create_owner(factory)
    token, _ = await seed_reset(factory, owner_id=owner_id)
    async with factory() as db, db.begin():
        db.add(
            RefreshToken(
                owner_id=owner_id,
                token_hash=hashlib.sha256(f"refresh-{uuid4().hex}".encode()).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
        )

    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "new-owner-password-123"},
    )

    assert response.status_code == 200
    async with factory() as db:
        refresh_rows = (
            await db.execute(select(RefreshToken).where(RefreshToken.owner_id == owner_id))
        ).scalars().all()
    assert refresh_rows == []


@pytest.mark.asyncio
async def test_owner_reset_rejects_old_access_and_accepts_new_login(api, monkeypatch):
    from app.api import auth

    client, factory = api
    owner_id, email = await create_owner(factory)
    token, _ = await seed_reset(factory, owner_id=owner_id)
    old_access = create_access_token(
        {"sub": str(owner_id), "email": email, "principal_type": "owner"}
    )
    old_headers = {"Authorization": f"Bearer {old_access}"}
    legacy_access = jwt.encode(
        {
            "sub": str(owner_id),
            "email": email,
            "token_kind": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    legacy_headers = {"Authorization": f"Bearer {legacy_access}"}
    assert (await client.get("/api/owners/me", headers=old_headers)).status_code == 200
    assert (await client.get("/api/owners/me", headers=legacy_headers)).status_code == 200

    async def issue_refresh_in_test(_owner_id, db=None):
        return "test-refresh-token"

    monkeypatch.setattr(auth, "issue_refresh_token", issue_refresh_in_test)
    confirmed = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "new-owner-password-123"},
    )
    assert confirmed.status_code == 200
    assert (await client.get("/api/owners/me", headers=old_headers)).status_code == 401
    assert (await client.get("/api/owners/me", headers=legacy_headers)).status_code == 401

    login = await client.post(
        "/api/auth/token",
        data={"username": email, "password": "new-owner-password-123"},
    )
    assert login.status_code == 200
    new_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get("/api/owners/me", headers=new_headers)).status_code == 200


@pytest.mark.asyncio
async def test_platform_admin_reset_revokes_existing_sessions(api):
    client, factory = api
    admin_id, admin_email = await create_admin(factory)
    token, _ = await seed_reset(factory, admin_id=admin_id)
    async with factory() as db, db.begin():
        session = PlatformAdminSession(
                admin_id=admin_id,
                token_hash=hashlib.sha256(f"admin-session-{uuid4().hex}".encode()).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
        db.add(session)
        await db.flush()
        session_id = session.id

    old_access = create_access_token(
        {
            "sub": str(admin_id),
            "email": admin_email,
            "principal_type": "platform_admin",
            "sid": str(session_id),
        }
    )
    old_headers = {"Authorization": f"Bearer {old_access}"}
    assert (await client.get("/api/platform/auth/me", headers=old_headers)).status_code == 200

    response = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "new-admin-password-123"},
    )

    assert response.status_code == 200
    async with factory() as db:
        sessions = (
            await db.execute(
                select(PlatformAdminSession).where(
                    PlatformAdminSession.admin_id == admin_id
                )
            )
        ).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is not None
    assert (await client.get("/api/platform/auth/me", headers=old_headers)).status_code == 401
