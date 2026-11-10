"""El token heredado de verificación no debe aparecer en logs."""

import logging

import pytest

from app.services import email_service


@pytest.mark.asyncio
async def test_missing_smtp_does_not_log_verification_token(monkeypatch, caplog):
    monkeypatch.setattr(email_service.config, "SMTP_HOST", "")
    with caplog.at_level(logging.WARNING):
        await email_service.send_verification_email(
            "owner@example.test", "private-verification-token", "Dueño"
        )
    assert "private-verification-token" not in caplog.text
    assert "verify-email?token=" not in caplog.text
