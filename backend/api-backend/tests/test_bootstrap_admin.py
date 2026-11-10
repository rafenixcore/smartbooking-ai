"""T007: bootstrap del primer administrador sobre PostgreSQL local desechable."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import verify_password
from app.models import PlatformAdmin


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
        raise ValueError("Refusing to test bootstrap outside local disposable DB")
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
async def session_factory(test_database_url):
    async_url = test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(async_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db, db.begin():
            await db.execute(delete(PlatformAdmin))
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_first_admin_is_idempotent_and_does_not_change_password(session_factory):
    from scripts.bootstrap_admin import bootstrap_admin

    email = "First.Admin@Example.Test"
    first_password = "first-long-password-123"
    assert await bootstrap_admin(email, first_password, session_factory) == "created"

    async with session_factory() as db:
        first = (await db.execute(select(PlatformAdmin))).scalar_one()
        first_hash = first.hashed_password
        assert first.email == "first.admin@example.test"
        assert verify_password(first_password, first_hash)

    assert await bootstrap_admin(" first.ADMIN@example.test ", "another-password-123", session_factory) == "exists"
    async with session_factory() as db:
        rows = (await db.execute(select(PlatformAdmin))).scalars().all()
        assert len(rows) == 1
        assert rows[0].hashed_password == first_hash
        assert not verify_password("another-password-123", first_hash)


@pytest.mark.asyncio
async def test_another_email_cannot_create_second_admin(session_factory):
    from scripts.bootstrap_admin import bootstrap_admin

    await bootstrap_admin("first.admin@example.test", "first-long-password-123", session_factory)
    with pytest.raises(RuntimeError, match="primer administrador"):
        await bootstrap_admin("second.admin@example.test", "another-password-123", session_factory)
    async with session_factory() as db:
        assert len((await db.execute(select(PlatformAdmin))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_inactive_admin_is_not_reactivated(session_factory):
    from scripts.bootstrap_admin import bootstrap_admin

    await bootstrap_admin("first.admin@example.test", "first-long-password-123", session_factory)
    async with session_factory() as db, db.begin():
        admin = (await db.execute(select(PlatformAdmin))).scalar_one()
        admin.is_active = False

    with pytest.raises(RuntimeError, match="inactiva"):
        await bootstrap_admin("first.admin@example.test", "another-password-123", session_factory)
    async with session_factory() as db:
        admin = (await db.execute(select(PlatformAdmin))).scalar_one()
        assert admin.is_active is False


@pytest.mark.asyncio
async def test_concurrent_bootstraps_create_only_one_admin(session_factory):
    from scripts.bootstrap_admin import bootstrap_admin

    results = await asyncio.gather(
        bootstrap_admin("one@example.test", "first-long-password-123", session_factory),
        bootstrap_admin("two@example.test", "second-long-password-123", session_factory),
        return_exceptions=True,
    )
    assert sorted(type(result).__name__ for result in results) == ["RuntimeError", "str"]
    async with session_factory() as db:
        assert len((await db.execute(select(PlatformAdmin))).scalars().all()) == 1


@pytest.mark.parametrize("password", ["short", "é" * 37])
@pytest.mark.asyncio
async def test_invalid_password_is_rejected_without_new_account(session_factory, password):
    from scripts.bootstrap_admin import bootstrap_admin

    with pytest.raises(ValueError, match="contraseña"):
        await bootstrap_admin("third@example.test", password, session_factory)
    async with session_factory() as db:
        assert len((await db.execute(select(PlatformAdmin))).scalars().all()) == 0


def test_cli_asks_for_hidden_password_and_never_prints_it(monkeypatch, capsys):
    from scripts import bootstrap_admin as command

    secret = "never-print-this-password"
    monkeypatch.setattr(command.getpass, "getpass", lambda _: secret)

    async def fake_bootstrap(email, password):
        assert email == "first@example.test"
        assert password == secret
        return "created"

    monkeypatch.setattr(command, "bootstrap_admin", fake_bootstrap)
    assert command.main(["--email", "first@example.test"]) == 0
    captured = capsys.readouterr()
    assert secret not in captured.out + captured.err
    assert "creado" in captured.out.lower()
