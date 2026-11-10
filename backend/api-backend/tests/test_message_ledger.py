"""T024: evidencia durable e idempotente de mensajes WhatsApp salientes."""

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import main
from app.core.security import get_password_hash
from app.models import Appointment, Business, Customer, MessageEvent, Owner, Service
from app.services import background_tasks
from app.services.message_ledger import (
    record_outbound_response,
    record_whatsapp_status_payload,
)

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
        raise ValueError("Refusing message ledger tests outside local disposable DB")
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


async def _seed_business(factory):
    nonce = uuid4().hex
    async with factory() as db, db.begin():
        owner = Owner(
            email=f"ledger-{nonce}@example.test",
            hashed_password=get_password_hash("valid-test-password"),
            email_verified=True,
            is_active=True,
        )
        db.add(owner)
        await db.flush()
        business = Business(
            name=f"Ledger {nonce}",
            phone_number=f"+1809{nonce[:11]}",
            whatsapp_phone_number_id=f"phone-{nonce}",
            owner_id=owner.id,
            is_active=True,
        )
        db.add(business)
        await db.flush()
        return business.id, business.whatsapp_phone_number_id


def _status_payload(phone_id, wamid, status, timestamp="1790000000", category=None):
    item = {"id": wamid, "status": status, "timestamp": timestamp}
    if category:
        item["pricing"] = {"category": category}
    return {
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": phone_id},
            "statuses": [item],
        }}]}]
    }


@pytest.mark.asyncio
async def test_outbound_response_is_recorded_once_and_does_not_store_recipient(factory):
    business_id, _phone_id = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"
    response = {"messages": [{"id": wamid}], "contacts": [{"wa_id": "18095551234"}]}
    async with factory() as db:
        assert await record_outbound_response(db, business_id, response) is True
        assert await record_outbound_response(db, business_id, response) is False
        await db.commit()

    async with factory() as db:
        rows = (
            await db.execute(select(MessageEvent).where(MessageEvent.provider_message_id == wamid))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].business_id == business_id
    assert rows[0].direction == "outbound"
    assert rows[0].status == "sent"
    assert "18095551234" not in str(rows[0].__dict__)


@pytest.mark.asyncio
async def test_duplicate_and_out_of_order_statuses_do_not_regress_current_state(factory):
    business_id, phone_id = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"
    async with factory() as db:
        assert await record_outbound_response(db, business_id, {"messages": [{"id": wamid}]})
        delivered = _status_payload(phone_id, wamid, "delivered", "1790000002", "utility")
        sent = _status_payload(phone_id, wamid, "sent", "1790000001")
        first = await record_whatsapp_status_payload(db, delivered)
        duplicate = await record_whatsapp_status_payload(db, delivered)
        late = await record_whatsapp_status_payload(db, sent)
        await db.commit()

    assert (first.recorded, duplicate.recorded, late.recorded) == (1, 0, 1)
    async with factory() as db:
        rows = (
            await db.execute(select(MessageEvent).where(MessageEvent.provider_message_id == wamid))
        ).scalars().all()
    assert len(rows) == 3  # estado actual + dos transiciones únicas
    current = next(row for row in rows if row.event_key.startswith("message:"))
    assert current.status == "delivered"
    assert current.category == "utility"
    assert current.occurred_at == datetime.fromtimestamp(1790000002, tz=timezone.utc)
    assert sum(row.status == "delivered" for row in rows) == 2


@pytest.mark.asyncio
async def test_status_before_outbound_response_preserves_stronger_evidence(factory):
    business_id, phone_id = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"
    async with factory() as db:
        first = await record_whatsapp_status_payload(
            db, _status_payload(phone_id, wamid, "read", "1790000003")
        )
        assert first.recorded == 1
        assert await record_outbound_response(db, business_id, {"messages": [{"id": wamid}]}) is False
        await db.commit()
    async with factory() as db:
        current = await db.scalar(
            select(MessageEvent).where(
                MessageEvent.business_id == business_id,
                MessageEvent.provider_message_id == wamid,
                MessageEvent.event_key.startswith("message:"),
            )
        )
    assert current.status == "read"


@pytest.mark.asyncio
async def test_status_for_unknown_business_is_not_attributed(factory):
    wamid = f"wamid.{uuid4().hex}"
    async with factory() as db:
        result = await record_whatsapp_status_payload(
            db, _status_payload("unknown-phone-id", wamid, "delivered")
        )
        await db.commit()
    assert result.unresolved == 1
    async with factory() as db:
        rows = (
            await db.execute(select(MessageEvent).where(MessageEvent.provider_message_id == wamid))
        ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_status_with_conflicting_business_phone_cannot_reassign_message(factory):
    first_business_id, _first_phone = await _seed_business(factory)
    second_business_id, second_phone = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"
    async with factory() as db:
        assert await record_outbound_response(
            db, first_business_id, {"messages": [{"id": wamid}]}
        )
        await db.commit()
        result = await record_whatsapp_status_payload(
            db, _status_payload(second_phone, wamid, "delivered")
        )
        await db.commit()

    assert result.unresolved == 1
    async with factory() as db:
        rows = (
            await db.execute(select(MessageEvent).where(MessageEvent.provider_message_id == wamid))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].business_id == first_business_id
    assert rows[0].status == "sent"
    assert all(row.business_id != second_business_id for row in rows)


@pytest.mark.asyncio
async def test_concurrent_businesses_cannot_claim_same_meta_message(factory):
    first_id, _ = await _seed_business(factory)
    second_id, _ = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"
    response = {"messages": [{"id": wamid}]}
    async with factory() as first_db, factory() as second_db:
        assert await record_outbound_response(first_db, first_id, response) is True
        second = asyncio.create_task(record_outbound_response(second_db, second_id, response))
        try:
            await asyncio.sleep(0.1)
            assert not second.done(), "El segundo negocio no esperó la atribución en curso"
            await first_db.commit()
            assert await second is False
            await second_db.commit()
        finally:
            if not second.done():
                second.cancel()
                await asyncio.gather(second, return_exceptions=True)
    async with factory() as db:
        rows = (await db.execute(select(MessageEvent).where(
            MessageEvent.provider_message_id == wamid
        ))).scalars().all()
    assert {row.business_id for row in rows} == {first_id}


@pytest.mark.asyncio
async def test_concurrent_status_cannot_reassign_uncommitted_outbound_message(factory):
    first_id, _ = await _seed_business(factory)
    second_id, second_phone = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"
    async with factory() as first_db, factory() as second_db:
        assert await record_outbound_response(first_db, first_id, {"messages": [{"id": wamid}]})
        second = asyncio.create_task(record_whatsapp_status_payload(
            second_db, _status_payload(second_phone, wamid, "delivered")
        ))
        try:
            await asyncio.sleep(0.1)
            assert not second.done(), "El estado no esperó la atribución en curso"
            await first_db.commit()
            assert (await second).unresolved == 1
            await second_db.commit()
        finally:
            if not second.done():
                second.cancel()
                await asyncio.gather(second, return_exceptions=True)
    async with factory() as db:
        rows = (await db.execute(select(MessageEvent).where(
            MessageEvent.provider_message_id == wamid
        ))).scalars().all()
    assert {row.business_id for row in rows} == {first_id}


@pytest.mark.asyncio
async def test_reversed_multi_message_callbacks_do_not_deadlock(factory, monkeypatch):
    from app.services import message_ledger

    _business_id, phone_id = await _seed_business(factory)
    first_id, second_id = f"wamid.{uuid4().hex}", f"wamid.{uuid4().hex}"
    first = _status_payload(phone_id, first_id, "sent")
    second = _status_payload(phone_id, second_id, "sent")
    first["entry"][0]["changes"][0]["value"]["statuses"].append(
        second["entry"][0]["changes"][0]["value"]["statuses"][0]
    )
    reversed_payload = _status_payload(phone_id, second_id, "sent")
    reversed_payload["entry"][0]["changes"][0]["value"]["statuses"].append(
        first["entry"][0]["changes"][0]["value"]["statuses"][0]
    )
    original_insert = message_ledger._insert_event
    reached = 0
    both_reached = asyncio.Event()

    async def pause_after_first_insert(db, **values):
        nonlocal reached
        inserted = await original_insert(db, **values)
        if values["event_key"].startswith("status:"):
            count = db.info.get("status_insert_count", 0) + 1
            db.info["status_insert_count"] = count
            if count == 1:
                reached += 1
                if reached == 2:
                    both_reached.set()
                try:
                    await asyncio.wait_for(both_reached.wait(), 0.2)
                except asyncio.TimeoutError:
                    pass
        return inserted

    monkeypatch.setattr(message_ledger, "_insert_event", pause_after_first_insert)

    async def ingest(payload):
        async with factory() as db:
            result = await record_whatsapp_status_payload(db, payload)
            await db.commit()
            return result

    results = await asyncio.wait_for(
        asyncio.gather(ingest(first), ingest(reversed_payload)), 3.0
    )
    assert sum(item.recorded for item in results) == 2


@pytest.mark.asyncio
async def test_webhook_persists_each_status_and_repeated_callback_is_idempotent(factory, monkeypatch):
    business_id, phone_id = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"
    payload = _status_payload(phone_id, wamid, "sent", "1790000010")
    payload["entry"][0]["changes"][0]["value"]["statuses"].append(
        {"id": wamid, "status": "delivered", "timestamp": "1790000011"}
    )

    class Request:
        headers = {"X-Hub-Signature-256": "sha256=test"}

        async def body(self):
            return b"{}"

        async def json(self):
            return payload

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_args: True)
    monkeypatch.setattr(main, "AsyncSessionLocal", factory, raising=False)
    assert (await main.whatsapp_webhook(Request()))["status"] == "ok"
    assert (await main.whatsapp_webhook(Request()))["status"] == "ok"

    async with factory() as db:
        rows = (
            await db.execute(select(MessageEvent).where(MessageEvent.provider_message_id == wamid))
        ).scalars().all()
    assert len(rows) == 3
    current = next(row for row in rows if row.event_key.startswith("message:"))
    assert current.business_id == business_id
    assert current.status == "delivered"


@pytest.mark.asyncio
async def test_webhook_records_meta_id_from_successful_outbound_reply(factory, monkeypatch):
    business_id, phone_id = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"

    class Request:
        headers = {"X-Hub-Signature-256": "sha256=test"}

        async def body(self):
            return b"{}"

        async def json(self):
            return {}

    async def get_business(_phone_id):
        return {"id": business_id}

    async def get_context(_business_id, _phone):
        return {}

    async def allow_event(**_kwargs):
        return True

    async def no_quota(**_kwargs):
        return {"allowed": False, "message": "Límite alcanzado"}

    async def mark_read(*_args):
        return {}

    async def send_text(**_kwargs):
        return {"messages": [{"id": wamid}]}

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_args: True)
    monkeypatch.setattr(main.whatsapp_client, "extract_message_from_webhook", lambda _payload: {
        "message_id": f"wamid.in.{uuid4().hex}",
        "from": "18095551234",
        "text": "Hola",
        "type": "text",
        "business_phone_number_id": phone_id,
    })
    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", mark_read)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", send_text)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", get_business)
    monkeypatch.setattr(main.conversation_manager, "get_context", get_context)
    monkeypatch.setattr(main, "should_process_channel_event", allow_event)
    monkeypatch.setattr(main, "route_guided_message", lambda *_args: SimpleNamespace(uses_ai=False))
    monkeypatch.setattr(main, "consume_daily_quota", no_quota)
    monkeypatch.setattr(main, "AsyncSessionLocal", factory, raising=False)

    assert (await main.whatsapp_webhook(Request()))["status"] == "ok"
    async with factory() as db:
        current = await db.scalar(
            select(MessageEvent).where(
                MessageEvent.business_id == business_id,
                MessageEvent.provider_message_id == wamid,
                MessageEvent.event_key.startswith("message:"),
            )
        )
    assert current is not None
    assert current.status == "sent"


@pytest.mark.asyncio
async def test_status_webhook_returns_retryable_error_when_ledger_fails(factory, monkeypatch):
    _business_id, phone_id = await _seed_business(factory)
    payload = _status_payload(phone_id, f"wamid.{uuid4().hex}", "delivered")

    class Request:
        headers = {"X-Hub-Signature-256": "sha256=test"}

        async def body(self):
            return b"{}"

        async def json(self):
            return payload

    async def fail_ledger(_db, _payload):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_args: True)
    monkeypatch.setattr(main, "AsyncSessionLocal", factory, raising=False)
    monkeypatch.setattr(main, "record_whatsapp_status_payload", fail_ledger, raising=False)
    with pytest.raises(HTTPException) as error:
        await main.whatsapp_webhook(Request())
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_whatsapp_reminder_records_meta_message_id(factory, monkeypatch):
    business_id, _phone_id = await _seed_business(factory)
    wamid = f"wamid.{uuid4().hex}"

    async def send_template(**_kwargs):
        return {"messages": [{"id": wamid}]}

    monkeypatch.setattr(background_tasks.whatsapp_client, "send_template_message", send_template)
    async with factory() as db:
        business = await db.get(Business, business_id)
        customer = Customer(
            name="Cliente",
            phone_number=f"1809{uuid4().hex[:10]}",
            business_id=business_id,
        )
        service = Service(name="Corte", duration_minutes=30, price=200, business_id=business_id)
        db.add_all([customer, service])
        await db.flush()
        appointment = Appointment(
            date=datetime(2040, 8, 1, tzinfo=timezone.utc),
            status="C",
            business_id=business_id,
            customer_id=customer.id,
            service_id=service.id,
        )
        db.add(appointment)
        await db.commit()
        await background_tasks._send_whatsapp_reminder(
            db, appointment, customer, service, business,
            "24h", "reminder_24h_sent", customer.phone_number,
        )

    async with factory() as db:
        current = await db.scalar(
            select(MessageEvent).where(
                MessageEvent.business_id == business_id,
                MessageEvent.provider_message_id == wamid,
                MessageEvent.event_key.startswith("message:"),
            )
        )
    assert current is not None
    assert current.status == "sent"


@pytest.mark.asyncio
async def test_reminder_does_not_retry_successful_send_when_ledger_write_fails(factory, monkeypatch):
    business_id, _phone_id = await _seed_business(factory)
    sends = 0

    async def send_once():
        nonlocal sends
        sends += 1
        return {"messages": [{"id": f"wamid.{uuid4().hex}"}]}

    async def fail_ledger(*_args):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(background_tasks, "record_outbound_response", fail_ledger)
    async with factory() as db:
        customer = Customer(phone_number=f"1809{uuid4().hex[:10]}", business_id=business_id)
        service = Service(name="Servicio", duration_minutes=30, price=100, business_id=business_id)
        db.add_all([customer, service])
        await db.flush()
        appointment = Appointment(
            date=datetime(2041, 1, 1, tzinfo=timezone.utc),
            status="C",
            business_id=business_id,
            customer_id=customer.id,
            service_id=service.id,
        )
        db.add(appointment)
        await db.commit()
        await background_tasks._attempt_send(
            db, appointment, "reminder_24h_sent", "24h", customer.phone_number,
            send_once, ledger_whatsapp=True,
        )
        await db.refresh(appointment)
        assert appointment.reminder_24h_sent is True
    assert sends == 1
