"""Verificación del secret token del webhook de Telegram.

Telegram firma cada entrega con `X-Telegram-Bot-Api-Secret-Token`. Sin esta
comprobación, cualquiera que conozca la URL puede inyectar actualizaciones
falsas y crear o cancelar citas en nombre de un usuario.
"""

import pytest

from app.core.webhook_security import telegram_secret_is_valid


def test_sin_secreto_configurado_se_acepta() -> None:
    """Compatibilidad: la variable es opcional para no tumbar el bot al desplegar."""
    assert telegram_secret_is_valid(None, None) is True
    assert telegram_secret_is_valid("cualquiera", None) is True
    assert telegram_secret_is_valid(None, "") is True


def test_con_secreto_configurado_solo_pasa_el_valor_exacto() -> None:
    assert telegram_secret_is_valid("s3cr3t", "s3cr3t") is True


def test_sin_cabecera_se_rechaza() -> None:
    assert telegram_secret_is_valid(None, "s3cr3t") is False
    assert telegram_secret_is_valid("", "s3cr3t") is False


@pytest.mark.parametrize(
    "recibido",
    ["s3cr3", "s3cr3to", "S3CR3T", " s3cr3t", "s3cr3t ", "otro"],
)
def test_valores_distintos_se_rechazan(recibido: str) -> None:
    assert telegram_secret_is_valid(recibido, "s3cr3t") is False
