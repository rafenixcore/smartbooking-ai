"""T009: contrato de seguridad y concurrencia para invitaciones de dueños.

Requiere una base PostgreSQL desechable local ``smartbooking_migration_test_*``.
Las pruebas describen el comportamiento esperado del servicio T010.
"""

import asyncio
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash
from app.models import AdminAuditEvent, Owner, OwnerInvitation, PlatformAdmin
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
        raise ValueError("Refusing invitation tests outside local disposable DB")
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
async def db_factory(test_database_url):
    engine = create_async_engine(
        test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def api_client(db_factory):
    async def test_db():
        async with db_factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


async def seed_admin(db_factory):
    async with db_factory() as db, db.begin():
        admin = PlatformAdmin(
            email=f"admin-{uuid4().hex}@example.test",
            hashed_password=get_password_hash("admin-password-test"),
        )
        db.add(admin)
        await db.flush()
        return admin.id


def _service():
    from app.services import owner_invitations

    return owner_invitations


@pytest.mark.asyncio
async def test_invitation_normalizes_email_and_stores_only_unique_token_hash(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    first_email = f" First.{uuid4().hex}@Example.Test "
    second_email = f"second.{uuid4().hex}@example.test"
    async with db_factory() as db:
        first, first_token = await service.create_invitation(db, first_email, admin_id)
        second, second_token = await service.create_invitation(db, second_email, admin_id)

    assert first.email == first_email.strip().lower()
    assert second.email == second_email.strip().lower()
    assert first_token != second_token
    assert first.token_hash == hashlib.sha256(first_token.encode()).hexdigest()
    assert second.token_hash == hashlib.sha256(second_token.encode()).hexdigest()
    assert first_token not in first.token_hash
    assert second_token not in second.token_hash


@pytest.mark.asyncio
async def test_invitation_expiry_is_72_hours(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    before = datetime.now(timezone.utc)
    async with db_factory() as db:
        invitation, _ = await service.create_invitation(
            db, f"ttl-{uuid4().hex}@example.test", admin_id
        )
    delta = invitation.expires_at - before
    assert timedelta(hours=71, minutes=59) < delta < timedelta(hours=72, minutes=1)


@pytest.mark.asyncio
async def test_duplicate_pending_email_is_rejected_case_insensitively(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"pending-{uuid4().hex}@example.test"
    async with db_factory() as db:
        await service.create_invitation(db, email, admin_id)
        with pytest.raises(service.InvitationError):
            await service.create_invitation(db, email.upper(), admin_id)


@pytest.mark.asyncio
async def test_stale_pending_invitation_expires_and_can_be_reissued(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"stale-{uuid4().hex}@example.test"
    async with db_factory() as db:
        previous, previous_token = await service.create_invitation(db, email, admin_id)
        previous.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
        replacement, replacement_token = await service.create_invitation(db, email, admin_id)
    async with db_factory() as db:
        previous = await db.get(OwnerInvitation, previous.id)
    assert previous.status == "expired"
    assert replacement.status == "pending"
    assert replacement_token != previous_token


@pytest.mark.asyncio
async def test_existing_owner_email_cannot_receive_new_invitation(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"existing-{uuid4().hex}@example.test"
    async with db_factory() as db, db.begin():
        db.add(
            Owner(
                name="Cuenta existente",
                email=email,
                hashed_password=get_password_hash("existing-owner-password"),
                email_verified=True,
                is_active=True,
            )
        )
    async with db_factory() as db:
        with pytest.raises(service.InvitationError):
            await service.create_invitation(db, email.upper(), admin_id)


@pytest.mark.asyncio
async def test_resend_replaces_token_and_invalidates_previous_link(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    async with db_factory() as db:
        invitation, old_token = await service.create_invitation(
            db, f"resend-{uuid4().hex}@example.test", admin_id
        )
        old_expiry = invitation.expires_at
        new_token = await service.resend_invitation(db, invitation.id, admin_id)

    assert new_token != old_token
    async with db_factory() as db:
        invitation = await db.get(OwnerInvitation, invitation.id)
        assert invitation.token_hash == hashlib.sha256(new_token.encode()).hexdigest()
        assert invitation.expires_at > old_expiry
        assert invitation.status == "pending"
        with pytest.raises(service.InvitationError):
            await service.accept_invitation(db, old_token, "long-password-123")


@pytest.mark.asyncio
async def test_resending_expired_invitation_with_new_pending_returns_domain_conflict(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"resend-conflict-{uuid4().hex}@example.test"
    async with db_factory() as db:
        old, _ = await service.create_invitation(db, email, admin_id)
        old.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()
        newer, token = await service.create_invitation(db, email, admin_id)
        with pytest.raises(service.InvitationError) as exc:
            await service.resend_invitation(db, old.id, admin_id)
        assert exc.value.code == "invitation_pending"
    async with db_factory() as db:
        pending = (await db.execute(select(OwnerInvitation).where(
            func.lower(OwnerInvitation.email) == email,
            OwnerInvitation.status == "pending",
        ))).scalars().all()
        assert [row.id for row in pending] == [newer.id]
        assert pending[0].token_hash == hashlib.sha256(token.encode()).hexdigest()


@pytest.mark.asyncio
async def test_resending_expired_invitation_after_account_creation_is_rejected(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"resend-owner-{uuid4().hex}@example.test"
    async with db_factory() as db:
        old, _ = await service.create_invitation(db, email, admin_id)
        old.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()
        _, current_token = await service.create_invitation(db, email, admin_id)
        await service.accept_invitation(db, current_token, "long-password-123")
        with pytest.raises(service.InvitationError) as exc:
            await service.resend_invitation(db, old.id, admin_id)
        assert exc.value.code == "owner_exists"


@pytest.mark.asyncio
async def test_revoke_invalidates_invitation_and_allows_reissue(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"revoke-{uuid4().hex}@example.test"
    async with db_factory() as db:
        invitation, token = await service.create_invitation(db, email, admin_id)
        await service.revoke_invitation(db, invitation.id, admin_id)
        with pytest.raises(service.InvitationError):
            await service.accept_invitation(db, token, "long-password-123")
        replacement, replacement_token = await service.create_invitation(db, email.upper(), admin_id)

    assert replacement.status == "pending"
    assert replacement_token != token
    assert invitation.revoked_at is not None


@pytest.mark.asyncio
async def test_expired_invitation_cannot_create_owner(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    async with db_factory() as db:
        invitation, token = await service.create_invitation(
            db, f"expired-{uuid4().hex}@example.test", admin_id
        )
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
        with pytest.raises(service.InvitationError):
            await service.accept_invitation(db, token, "long-password-123")

    async with db_factory() as db:
        invitation = await db.get(OwnerInvitation, invitation.id)
        owner_count = await db.scalar(select(func.count(Owner.id)).where(Owner.email == invitation.email))
    assert invitation.status == "expired"
    assert owner_count == 0


@pytest.mark.asyncio
async def test_acceptance_is_single_use(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"accept-{uuid4().hex}@example.test"
    async with db_factory() as db:
        invitation, token = await service.create_invitation(db, email, admin_id)
        owner = await service.accept_invitation(db, token, "long-password-123")
        assert owner.email == email
        with pytest.raises(service.InvitationError):
            await service.accept_invitation(db, token, "different-password-123")

    async with db_factory() as db:
        invitation = await db.get(OwnerInvitation, invitation.id)
        owners = await db.scalar(select(func.count(Owner.id)).where(Owner.email == email))
    assert invitation.status == "accepted"
    assert invitation.accepted_at is not None
    assert owners == 1


@pytest.mark.asyncio
async def test_concurrent_acceptance_creates_exactly_one_owner(db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"race-{uuid4().hex}@example.test"
    async with db_factory() as db:
        _, token = await service.create_invitation(db, email, admin_id)

    async def accept(password):
        async with db_factory() as db:
            return await service.accept_invitation(db, token, password)

    results = await asyncio.gather(
        accept("first-password-123"),
        accept("second-password-123"),
        return_exceptions=True,
    )
    assert sum(isinstance(result, Owner) for result in results) == 1
    assert sum(isinstance(result, service.InvitationError) for result in results) == 1
    async with db_factory() as db:
        owners = await db.scalar(select(func.count(Owner.id)).where(Owner.email == email))
    assert owners == 1


@pytest.mark.asyncio
async def test_platform_routes_require_admin_and_audit_create_resend_revoke(api_client, db_factory):
    client = api_client
    email = f"route-admin-{uuid4().hex}@example.test"
    async with db_factory() as db, db.begin():
        admin = PlatformAdmin(email=email, hashed_password=get_password_hash("admin-password-test"))
        db.add(admin)
        await db.flush()
        admin_id = admin.id

    rejected = await client.post(
        "/api/platform/invitations", json={"email": f"owner-{uuid4().hex}@example.test"}
    )
    assert rejected.status_code == 401
    owner_email = f"route-owner-{uuid4().hex}@example.test"
    async with db_factory() as db, db.begin():
        db.add(
            Owner(
                name="Dueño ajeno",
                email=owner_email,
                hashed_password=get_password_hash("owner-password-test"),
                email_verified=True,
                is_active=True,
            )
        )
    owner_token = create_access_token(
        {"sub": "1", "email": owner_email, "principal_type": "owner"}
    )
    owner_rejected = await client.post(
        "/api/platform/invitations",
        json={"email": f"someone-{uuid4().hex}@example.com"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_rejected.status_code == 401
    login = await client.post(
        "/api/platform/auth/token",
        data={"username": email, "password": "admin-password-test"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    invite_email = f"route-owner-{uuid4().hex}@example.com"
    created = await client.post(
        "/api/platform/invitations", json={"email": invite_email}, headers=headers
    )
    assert created.status_code == 201, created.text
    assert created.json()["email"] == invite_email
    assert created.json()["status"] == "pending"
    assert created.json()["delivery_status"] == "failed"
    assert "token" not in created.json()
    invitation_id = created.json()["id"]

    resent = await client.post(
        f"/api/platform/invitations/{invitation_id}/resend", headers=headers
    )
    assert resent.status_code == 200
    revoked = await client.post(
        f"/api/platform/invitations/{invitation_id}/revoke", headers=headers
    )
    assert revoked.status_code == 200
    listed = await client.get("/api/platform/invitations", headers=headers)
    assert listed.status_code == 200

    stale_email = f"stale-list-{uuid4().hex}@example.com"
    stale = await client.post(
        "/api/platform/invitations", json={"email": stale_email}, headers=headers
    )
    assert stale.status_code == 201
    async with db_factory() as db, db.begin():
        invitation = await db.get(OwnerInvitation, stale.json()["id"])
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired_list = await client.get(
        "/api/platform/invitations", params={"status": "expired"}, headers=headers
    )
    assert expired_list.status_code == 200
    assert any(item["id"] == stale.json()["id"] for item in expired_list.json()["items"])

    async with db_factory() as db:
        events = (
            await db.execute(
                select(AdminAuditEvent)
                .where(
                    AdminAuditEvent.admin_id == admin_id,
                    AdminAuditEvent.entity_type == "owner_invitation",
                    AdminAuditEvent.entity_id == str(invitation_id),
                )
                .order_by(AdminAuditEvent.id)
            )
        ).scalars().all()
        assert [event.action for event in events] == [
            "owner_invitation.create",
            "owner_invitation.resend",
            "owner_invitation.revoke",
        ]
        assert all(event.outcome == "success" for event in events)


@pytest.mark.asyncio
async def test_accept_endpoint_creates_owner_that_can_log_in(api_client, db_factory):
    client = api_client
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"accepted-{uuid4().hex}@example.test"
    async with db_factory() as db:
        _, token = await service.create_invitation(db, email, admin_id)

    accepted = await client.post(
        "/api/auth/invitations/accept",
        json={"token": token, "password": "new-owner-password-123"},
    )
    assert accepted.status_code == 200
    assert accepted.json() == {"ok": True}
    login = await client.post(
        "/api/auth/token", data={"username": email, "password": "new-owner-password-123"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email
    assert login.json()["user"]["name"] is None


@pytest.mark.asyncio
async def test_public_registration_is_unavailable_and_existing_owner_can_log_in(
    api_client, db_factory, monkeypatch
):
    from app.api import auth

    async def issue_refresh_in_test(_owner_id, db=None):
        return "test-refresh-token"

    # Evita compartir el pool global de refresh entre event loops de pruebas.
    monkeypatch.setattr(auth, "issue_refresh_token", issue_refresh_in_test)
    email = f"legacy-{uuid4().hex}@example.test"
    password = "existing-owner-password-123"
    async with db_factory() as db, db.begin():
        db.add(
            Owner(
                name="Cuenta existente",
                email=email,
                hashed_password=get_password_hash(password),
                email_verified=True,
            )
        )

    attempted_email = f"public-{uuid4().hex}@example.test"
    registration = await api_client.post(
        "/api/auth/register",
        json={
            "name": "Alta pública",
            "email": attempted_email,
            "password": "public-password-123",
        },
    )
    assert registration.status_code == 404
    async with db_factory() as db:
        result = await db.execute(select(Owner).where(Owner.email == attempted_email))
        assert result.scalar_one_or_none() is None

    login = await api_client.post(
        "/api/auth/token", data={"username": email, "password": password}
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email


@pytest.mark.asyncio
async def test_invitation_endpoint_sends_link_and_reports_provider_acceptance(
    api_client, db_factory, monkeypatch
):
    from app.api import platform_invitations

    admin_email = f"delivery-admin-{uuid4().hex}@example.test"
    async with db_factory() as db, db.begin():
        admin = PlatformAdmin(
            email=admin_email,
            hashed_password=get_password_hash("admin-password-test"),
        )
        db.add(admin)

    login = await api_client.post(
        "/api/platform/auth/token",
        data={"username": admin_email, "password": "admin-password-test"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    sent = []

    async def fake_send(email, token):
        sent.append((email, token))

    monkeypatch.setattr(platform_invitations, "send_invitation_email", fake_send)
    email = f"invited-{uuid4().hex}@example.com"
    created = await api_client.post(
        "/api/platform/invitations", json={"email": email}, headers=headers
    )

    assert created.status_code == 201
    assert created.json()["delivery_status"] == "sent"
    assert "token" not in created.json()
    assert len(sent) == 1
    assert sent[0][0] == email
    async with db_factory() as db:
        invitation = await db.get(OwnerInvitation, created.json()["id"])
    assert invitation.sent_at is not None


@pytest.mark.asyncio
async def test_invitation_delivery_failure_is_visible_and_does_not_expose_token(
    api_client, db_factory, monkeypatch
):
    from app.api import platform_invitations
    from app.services.email_service import EmailDeliveryError

    admin_email = f"failed-admin-{uuid4().hex}@example.test"
    async with db_factory() as db, db.begin():
        admin = PlatformAdmin(
            email=admin_email,
            hashed_password=get_password_hash("admin-password-test"),
        )
        db.add(admin)

    login = await api_client.post(
        "/api/platform/auth/token",
        data={"username": admin_email, "password": "admin-password-test"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    async def fail_send(_email, _token):
        raise EmailDeliveryError("provider unavailable")

    monkeypatch.setattr(platform_invitations, "send_invitation_email", fail_send)
    created = await api_client.post(
        "/api/platform/invitations",
        json={"email": f"failed-{uuid4().hex}@example.com"},
        headers=headers,
    )

    assert created.status_code == 201
    assert created.json()["delivery_status"] == "failed"
    assert "token" not in created.json()
    assert "provider unavailable" not in created.text


@pytest.mark.asyncio
async def test_invitation_preview_returns_fixed_email_for_valid_token(api_client, db_factory):
    service = _service()
    admin_id = await seed_admin(db_factory)
    email = f"preview-{uuid4().hex}@example.test"
    async with db_factory() as db:
        _, token = await service.create_invitation(db, email, admin_id)

    response = await api_client.post(
        "/api/auth/invitations/preview", json={"token": token}
    )

    assert response.status_code == 200
    assert response.json()["email"] == email
    assert "token" not in response.json()


@pytest.mark.asyncio
async def test_invitation_preview_rejects_invalid_or_expired_token(api_client, db_factory):
    response = await api_client.post(
        "/api/auth/invitations/preview", json={"token": "not-a-valid-token"}
    )
    assert response.status_code == 404

    service = _service()
    admin_id = await seed_admin(db_factory)
    async with db_factory() as db:
        invitation, token = await service.create_invitation(
            db, f"expired-preview-{uuid4().hex}@example.test", admin_id
        )
        invitation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()

    expired = await api_client.post(
        "/api/auth/invitations/preview", json={"token": token}
    )
    assert expired.status_code == 404


@pytest.mark.asyncio
async def test_invitation_email_uses_resend_api_and_constructs_private_link(monkeypatch):
    from app.config import config
    from app.services import email_service

    monkeypatch.setattr(config, "RESEND_API_KEY", "test-resend-key", raising=False)
    monkeypatch.setattr(config, "RESEND_FROM_EMAIL", "Invitaciones <invites@rafenixcore.com>", raising=False)
    monkeypatch.setattr(config, "FRONTEND_BASE_URL", "https://app.example.test")
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, json):
            captured.update(url=url, headers=headers, body=json)
            return Response()

    monkeypatch.setattr(email_service.httpx, "AsyncClient", Client)
    await email_service.send_invitation_email("owner@example.test", "secret-token")

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer test-resend-key"
    assert captured["body"]["from"] == "Invitaciones <invites@rafenixcore.com>"
    assert captured["body"]["to"] == ["owner@example.test"]
    assert "https://app.example.test/invitation#token=secret-token" in captured["body"]["text"]
    assert "72 horas" in captured["body"]["text"]


@pytest.mark.asyncio
async def test_invitation_email_fails_closed_without_resend_configuration(monkeypatch, caplog):
    from app.config import config
    from app.services.email_service import EmailDeliveryError, send_invitation_email

    monkeypatch.setattr(config, "RESEND_API_KEY", "", raising=False)
    monkeypatch.setattr(config, "RESEND_FROM_EMAIL", "", raising=False)

    with pytest.raises(EmailDeliveryError):
        await send_invitation_email("owner@example.test", "secret-token")

    assert "secret-token" not in caplog.text
    assert "owner@example.test" not in caplog.text
