"""T005: owner and platform credentials must never cross authorization guards.

The fake session only supplies account records; JWT parsing and authorization
guards are the real application code. The HTTP flow is covered separately.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core import dependencies
from app.core.security import create_access_token
from app.models import Owner, PlatformAdmin, PlatformAdminSession


EMAIL = "same-person@example.test"
IDENTITY_ID = 7
SESSION_ID = 91


class _Result:
    def __init__(self, row):
        self.row = row

    def scalars(self):
        return self

    def first(self):
        return self.row

    def one_or_none(self):
        return self.row

    def scalar_one_or_none(self):
        return self.row


class _AccountsDb:
    def __init__(self, *, admin_active=True, session_revoked=False, session_expired=False):
        self.owner = Owner(id=IDENTITY_ID, email=EMAIL, hashed_password="hash", is_active=True)
        self.admin = PlatformAdmin(
            id=IDENTITY_ID,
            email=EMAIL,
            hashed_password="hash",
            is_active=admin_active,
        )
        self.session = PlatformAdminSession(
            id=SESSION_ID,
            admin_id=IDENTITY_ID,
            token_hash="a" * 64,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=-1 if session_expired else 30),
            revoked_at=datetime.now(timezone.utc) if session_revoked else None,
        )

    def _row(self, model):
        return {
            Owner: self.owner,
            PlatformAdmin: self.admin,
            PlatformAdminSession: self.session,
        }.get(model)

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        return _Result(self._row(entity))

    async def scalar(self, statement):
        return (await self.execute(statement)).row

    async def get(self, model, identity):
        row = self._row(model)
        return row if row is not None and row.id == identity else None


def _access_token(principal_type=None, *, token_kind="access", sid=None, minutes=5):
    claims = {"sub": str(IDENTITY_ID), "email": EMAIL}
    if principal_type is not None:
        claims["principal_type"] = principal_type
    if sid is not None:
        claims["sid"] = str(sid)
    return create_access_token(
        claims,
        expires_delta=timedelta(minutes=minutes),
        token_kind=token_kind,
    )


async def _platform_guard(token, db):
    guard = getattr(dependencies, "get_current_platform_admin", None)
    assert guard is not None, "T006 must implement get_current_platform_admin"
    return await guard(token=token, db=db)


@pytest.mark.asyncio
async def test_platform_token_cannot_authenticate_as_owner_with_same_email_and_id():
    db = _AccountsDb()
    token = _access_token("platform_admin", sid=SESSION_ID)

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_owner(token=token, db=db)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_owner_token_cannot_authenticate_as_platform_admin_with_same_email_and_id():
    db = _AccountsDb()
    token = _access_token("owner")

    with pytest.raises(HTTPException) as exc:
        await _platform_guard(token, db)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_legacy_owner_access_token_remains_valid_during_transition():
    db = _AccountsDb()
    token = _access_token()

    owner = await dependencies.get_current_owner(token=token, db=db)

    assert owner is db.owner


@pytest.mark.asyncio
async def test_untyped_owner_token_cannot_authenticate_as_platform_admin():
    db = _AccountsDb()

    with pytest.raises(HTTPException) as exc:
        await _platform_guard(_access_token(), db)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_platform_access_token_requires_active_session():
    db = _AccountsDb(session_revoked=True)

    with pytest.raises(HTTPException) as exc:
        await _platform_guard(_access_token("platform_admin", sid=SESSION_ID), db)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_platform_access_token_rejects_expired_session():
    db = _AccountsDb(session_expired=True)

    with pytest.raises(HTTPException) as exc:
        await _platform_guard(_access_token("platform_admin", sid=SESSION_ID), db)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_platform_access_token_rejects_inactive_admin():
    db = _AccountsDb(admin_active=False)

    with pytest.raises(HTTPException) as exc:
        await _platform_guard(_access_token("platform_admin", sid=SESSION_ID), db)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_valid_platform_token_authenticates_only_as_admin():
    db = _AccountsDb()

    admin = await _platform_guard(_access_token("platform_admin", sid=SESSION_ID), db)

    assert admin is db.admin


@pytest.mark.asyncio
async def test_refresh_token_cannot_authenticate_as_platform_admin():
    db = _AccountsDb()

    with pytest.raises(HTTPException) as exc:
        await _platform_guard(
            _access_token("platform_admin", token_kind="refresh", sid=SESSION_ID), db
        )

    assert exc.value.status_code == 401
