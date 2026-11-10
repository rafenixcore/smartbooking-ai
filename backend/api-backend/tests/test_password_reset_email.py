"""Pruebas aisladas de la plantilla y solicitud a Resend para recuperación."""

import asyncio

from app.services import email_service


def test_password_reset_email_builds_safe_resend_message(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, timeout):
            assert timeout == 10.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, headers, json):
            captured.update(url=url, headers=headers, payload=json)
            return Response()

    monkeypatch.setattr(email_service.config, "RESEND_API_KEY", "test-api-key")
    monkeypatch.setattr(email_service.config, "RESEND_FROM_EMAIL", "SmartBooking <test@example.test>")
    monkeypatch.setattr(email_service.config, "FRONTEND_BASE_URL", "https://app.example.test")
    monkeypatch.setattr(email_service.httpx, "AsyncClient", Client)

    asyncio.run(email_service.send_password_reset_email(
        "owner@example.test", "token&secret", "business_owner"
    ))

    payload = captured["payload"]
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer test-api-key"
    assert payload["to"] == ["owner@example.test"]
    assert "reset-password#token=token%26secret" in payload["text"]
    assert "vence en una hora" in payload["text"]
    assert "solo se puede usar una vez" in payload["text"]
    assert "<h1" in payload["html"]
    assert "dueño de negocio" in payload["html"]
