"""Verificación del origen de los webhooks entrantes.

Telegram firma cada entrega con la cabecera `X-Telegram-Bot-Api-Secret-Token`,
que es el valor que se registra al llamar a `setWebhook`. Si el valor no
coincide, la petición no viene de Telegram y no debe procesarse.

El secreto es opcional por diseño: si no está configurado, la comprobación no
aplica y el bot sigue funcionando como antes. Eso permite desplegar el código
antes de configurar la variable, sin dejar el bot caído.
"""

import secrets


def telegram_secret_is_valid(received: str | None, expected: str | None) -> bool:
    """True si la petición puede procesarse.

    - Sin secreto configurado: se acepta (comportamiento anterior).
    - Con secreto configurado: la cabecera debe existir y coincidir.

    La comparación es en tiempo constante para no filtrar el secreto por el
    tiempo de respuesta.
    """
    if not expected:
        return True
    return secrets.compare_digest(received or "", expected)
