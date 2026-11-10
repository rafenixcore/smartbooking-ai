"""Envío de correo transaccional sin exponer enlaces de acceso en logs."""
import asyncio
import html
import logging
import smtplib
from urllib.parse import quote
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import config

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """El proveedor no pudo aceptar un correo transaccional."""


def _send_smtp_sync(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if config.SMTP_USE_TLS:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
        finally:
            server.quit()
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
        try:
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
        finally:
            server.quit()


async def send_verification_email(to_email: str, token: str, recipient_name: str) -> None:
    link = f"{config.FRONTEND_BASE_URL}/verify-email?token={token}"
    subject = "Verificá tu correo — SmartBooking"
    text_body = (
        f"Hola {recipient_name},\n\n"
        f"Para activar tu cuenta abrí este enlace:\n{link}\n\n"
        "Si no creaste la cuenta, ignorá este mensaje.\n"
    )
    html_body = (
        '<div style="font-family:Arial,Helvetica,sans-serif;color:#2563eb;font-weight:bold;'
        'font-size:18px;">SmartBooking <span style="font-size:12px;color:#64748b;font-weight:normal;">'
        'by Rafenixcore</span></div>'
        f"<p>Hola {recipient_name},</p>"
        f'<p>Para activar tu cuenta hacé clic en '
        f'<a href="{link}">verificar correo</a>.</p>'
        "<p>Si no creaste la cuenta, ignorá este mensaje.</p>"
    )

    if not config.SMTP_HOST:
        logger.warning("SMTP_HOST no configurado; no se envió verificación")
        return

    await asyncio.to_thread(_send_smtp_sync, to_email, subject, text_body, html_body)
    logger.info("Correo de verificación enviado a %s", to_email)


async def send_invitation_email(to_email: str, token: str) -> None:
    """Envía invitación por Resend sin escribir el enlace o el destinatario en logs."""
    if not config.RESEND_API_KEY or not config.RESEND_FROM_EMAIL:
        logger.warning("No se pudo enviar invitación: Resend no está configurado")
        raise EmailDeliveryError("El correo de invitación no está configurado")

    link = f"{config.FRONTEND_BASE_URL}/invitation#token={quote(token, safe='')}"
    subject = "Tu acceso a SmartBooking"
    text_body = (
        "Recibiste una invitación para administrar un negocio en SmartBooking.\n\n"
        f"Abre este enlace para definir tu contraseña: {link}\n\n"
        "El enlace vence en 72 horas y solo se puede usar una vez. "
        "Si no esperabas esta invitación, ignora este correo.\n\n"
        "SmartBooking · Rafenixcore\n"
    )
    safe_link = html.escape(link, quote=True)
    html_body = (
        "<!doctype html><html><body style=\"margin:0;background:#f4f6fb;"
        "font-family:Arial,Helvetica,sans-serif;color:#172033;\">"
        "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" "
        "style=\"background:#f4f6fb;padding:24px 12px;\"><tr><td align=\"center\">"
        "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" "
        "style=\"max-width:600px;background:#ffffff;border-radius:12px;\"><tr><td "
        "style=\"padding:32px;font-size:16px;line-height:24px;color:#172033;\">"
        '<p style="margin:0 0 24px;font-size:18px;line-height:24px;font-weight:bold;color:#2563eb;">'
        'SmartBooking <span style="font-size:12px;font-weight:normal;color:#64748b;">· Rafenixcore</span></p>'
        "<h1 style=\"margin:0 0 20px;font-size:24px;line-height:32px;color:#172033;\">"
        "Invitación a SmartBooking</h1>"
        "<p style=\"margin:0 0 20px;font-size:16px;line-height:24px;color:#344054;\">"
        "Te invitaron a administrar un negocio. Usa el botón para definir tu contraseña.</p>"
        "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\"><tr><td "
        "bgcolor=\"#2563eb\" style=\"background-color:#2563eb;border-radius:8px;\"><a "
        f"href=\"{safe_link}\" style=\"display:inline-block;padding:12px 20px;color:#ffffff;"
        "font-size:16px;line-height:24px;text-decoration:none;font-weight:bold;\">"
        "Aceptar invitación</a></td></tr></table>"
        "<p style=\"margin:20px 0 0;font-size:14px;line-height:21px;color:#667085;\">"
        "El enlace vence en 72 horas y solo se puede usar una vez. Si no esperabas esta invitación, "
        "ignora este correo.</p></td></tr></table></td></tr></table></body></html>"
    )
    payload = {
        "from": config.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                json=payload,
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning("Resend no aceptó invitación (%s)", type(exc).__name__)
        raise EmailDeliveryError("No se pudo enviar el correo de invitación") from None

    logger.info("Resend aceptó un correo de invitación")


async def send_password_reset_email(to_email: str, token: str, account_type: str) -> None:
    """Envía una plantilla transaccional de restablecimiento por Resend."""
    if not config.RESEND_API_KEY or not config.RESEND_FROM_EMAIL:
        logger.warning("No se pudo enviar recuperación: Resend no está configurado")
        raise EmailDeliveryError("El correo de recuperación no está configurado")

    account_label = (
        "administrador de plataforma"
        if account_type == "platform_admin"
        else "dueño de negocio"
    )
    link = f"{config.FRONTEND_BASE_URL}/reset-password#token={quote(token, safe='')}"
    subject = "Restablece tu contraseña de SmartBooking"
    text_body = (
        "Hola,\n\n"
        f"Recibimos una solicitud para cambiar la contraseña de tu cuenta de SmartBooking ({account_label}).\n\n"
        f"Restablece tu contraseña desde este enlace: {link}\n\n"
        "Por seguridad, el enlace vence en una hora y solo se puede usar una vez. "
        "Si no hiciste esta solicitud, puedes ignorar este correo; tu contraseña seguirá igual.\n\n"
        "SmartBooking · Rafenixcore\n"
    )
    safe_link = html.escape(link, quote=True)
    html_body = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        'style="background:#f4f6fb;padding:32px 12px;"><tr><td align="center">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        'style="max-width:560px;background:#ffffff;border:1px solid #e5e9f2;border-radius:16px;">'
        '<tr><td style="padding:36px 32px;">'
        '<div style="font-size:18px;font-weight:bold;color:#2563eb;">SmartBooking '
        '<span style="font-size:12px;font-weight:normal;color:#64748b;">· Rafenixcore</span></div>'
        '<h1 style="margin:22px 0 12px;font-size:26px;line-height:34px;color:#172033;">Cambia tu contraseña</h1>'
        '<p style="margin:0 0 18px;font-size:15px;line-height:24px;color:#475467;">'
        f"Recibimos una solicitud para cambiar la contraseña de tu cuenta de {html.escape(account_label)}."
        '</p><table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td '
        'bgcolor="#2563eb" style="background:#2563eb;border-radius:8px;"><a '
        f'href="{safe_link}" style="display:inline-block;padding:13px 20px;color:#ffffff;'
        'font-size:15px;line-height:22px;text-decoration:none;font-weight:bold;">'
        'Restablecer contraseña</a></td></tr></table>'
        '<p style="margin:22px 0 0;font-size:13px;line-height:21px;color:#667085;">'
        '<strong>Este enlace vence en una hora y solo se puede usar una vez.</strong> '
        'Si no hiciste esta solicitud, ignora este correo; tu contraseña seguirá igual.'
        '</p><hr style="margin:28px 0 18px;border:0;border-top:1px solid #eaecf0;">'
        '<p style="margin:0;font-size:12px;line-height:19px;color:#98a2b3;">Mensaje automático de SmartBooking. '
        'Si el botón no funciona, abre este enlace: '
        f'<a href="{safe_link}" style="color:#2563eb;word-break:break-all;">Restablecer contraseña</a>.</p>'
        '</td></tr></table></td></tr></table></body></html>'
    )
    payload = {
        "from": config.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                json=payload,
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning("Resend no aceptó recuperación (%s)", type(exc).__name__)
        raise EmailDeliveryError("No se pudo enviar el correo de recuperación") from None

    logger.info("Resend aceptó un correo de recuperación")
