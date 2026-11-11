"""Configuración WhatsApp administrada por la plataforma."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.platform_businesses import PlatformWhatsAppConfigUpdate, update_platform_whatsapp_config


class FakeDb:
    def __init__(self, values):
        self.values = iter(values)
        self.added = []
        self.committed = False

    async def scalar(self, _statement):
        return next(self.values)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.committed = True

    async def refresh(self, _value):
        return None

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_platform_admin_can_bind_same_waba_to_distinct_business_numbers():
    admin = SimpleNamespace(id=9)
    businesses = [
        SimpleNamespace(id=11, whatsapp_phone_number_id=None, waba_id=None),
        SimpleNamespace(id=12, whatsapp_phone_number_id=None, waba_id=None),
    ]

    for business, phone_id in zip(
        businesses, ("1180291398493188", "1180291398493189")
    ):
        db = FakeDb([business, None])
        result = await update_platform_whatsapp_config(
            business.id,
            PlatformWhatsAppConfigUpdate(
                whatsapp_phone_number_id=phone_id,
                waba_id="2183193562429781",
            ),
            db,
            admin,
        )
        assert result.status == "ids_saved"
        assert business.whatsapp_phone_number_id == phone_id
        assert business.waba_id == "2183193562429781"
        assert db.committed is True
        assert db.added[0].action == "business.whatsapp.configure"


@pytest.mark.asyncio
async def test_platform_admin_cannot_assign_a_phone_id_already_used_by_another_business():
    business = SimpleNamespace(id=11, whatsapp_phone_number_id=None, waba_id=None)
    db = FakeDb([business, 12])

    with pytest.raises(HTTPException) as error:
        await update_platform_whatsapp_config(
            11,
            PlatformWhatsAppConfigUpdate(
                whatsapp_phone_number_id="1180291398493188",
                waba_id="2183193562429781",
            ),
            db,
            SimpleNamespace(id=9),
        )

    assert error.value.status_code == 409
    assert business.whatsapp_phone_number_id is None
    assert db.added[0].outcome == "conflict"


def test_phone_number_and_account_ids_must_be_set_or_cleared_together():
    with pytest.raises(ValidationError) as error:
        PlatformWhatsAppConfigUpdate(
            whatsapp_phone_number_id="1180291398493188"
        )
    assert "Completa el Phone Number ID y el WABA ID" in str(error.value)


def test_phone_number_and_account_ids_can_be_cleared_together():
    payload = PlatformWhatsAppConfigUpdate(
        whatsapp_phone_number_id=None,
        waba_id=None,
    )
    assert payload.whatsapp_phone_number_id is None
    assert payload.waba_id is None


def test_phone_number_and_account_ids_reject_non_numeric_values():
    with pytest.raises(ValidationError) as error:
        PlatformWhatsAppConfigUpdate(
            whatsapp_phone_number_id="phone-abc",
            waba_id="2183193562429781",
        )
    assert "El Phone Number ID debe contener solo números." in str(error.value)

    with pytest.raises(ValidationError) as error:
        PlatformWhatsAppConfigUpdate(
            whatsapp_phone_number_id="1180291398493188",
            waba_id="waba-abc",
        )
    assert "El WABA ID debe contener solo números." in str(error.value)


def test_phone_number_and_account_ids_reject_values_outside_length_range():
    with pytest.raises(ValidationError) as error:
        PlatformWhatsAppConfigUpdate(
            whatsapp_phone_number_id="1234",
            waba_id="2183193562429781",
        )
    assert "El Phone Number ID debe tener entre 5 y 64 dígitos." in str(error.value)
