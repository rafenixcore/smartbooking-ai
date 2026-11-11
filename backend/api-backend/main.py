"""
Agent Service - NLU con GPT-4o-mini para WhatsApp Bot
"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Response

import sentry_sdk
from fastapi.middleware.cors import CORSMiddleware
from app.config import config
from app.api import (
    auth,
    password_reset,
    platform_auth,
    platform_invitations,
    platform_businesses,
    platform_audit,
    platform_metrics,
    owners,
    businesses,
    services,
    customers,
    appointments,
    schedules,
    dashboard,
    internal_jobs,
)
from app.services import db_service, whatsapp_client, conversation_manager
from app.core.database import AsyncSessionLocal
from app.services.background_tasks import (
    process_appointment_reminders,
    process_waitlist_expiration,
)
from app.services.telegram_inbound import process_telegram_update
from app.core.orchestrator import run_conversation_turn
from app.services.rate_limit_async import consume_daily_quota
from app.services.guided_menu_router import (
    execute_guided_route,
    route_guided_message,
)
from app.services.whatsapp_renderer import render_bot_reply, strip_html
from app.services.idempotency import should_process_channel_event
from app.services.message_ledger import record_outbound_response, record_whatsapp_status_payload
from app.utils.channel_phone import normalize_channel_phone
from app.core.scheduler import start_scheduler, shutdown_scheduler, scheduler
from app.core.webhook_security import telegram_secret_is_valid

logger = logging.getLogger(__name__)

# Sentry initialization
if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    if config.CRON_EXTERNAL:
        # Fase 4 MVP: el cron externo (Railway) dispara /internal/jobs/*;
        # el APScheduler en proceso queda desactivado.
        logger.info("CRON_EXTERNAL=true: APScheduler desactivado, cron externo activo")
        yield
        return

    # Startup: Start APScheduler and add jobs
    start_scheduler()

    # Run reminders every 30 minutes
    scheduler.add_job(process_appointment_reminders, 'interval', minutes=15, id='reminders_job', replace_existing=True)

    # MVP (fase 1): waitlist diferida tras flag — solo se crea el job si está activa
    if config.WAITLIST_ENABLED:
        scheduler.add_job(process_waitlist_expiration, 'interval', minutes=60, id='waitlist_job', replace_existing=True)

    # Agenda diaria del owner (8:00) diferida post-MVP: el código queda en
    # background_tasks.py pero el job no se registra (cron externo tampoco lo usa)

    yield

    # Shutdown: Stop scheduler
    shutdown_scheduler()

app = FastAPI(title="SmartBooking AI - Agent Service", lifespan=lifespan)

# Simple Rate Limiting State
# { "ip_address": [timestamp1, timestamp2, ...] }
rate_limit_records = {}
RATE_LIMIT_MAX_REQUESTS = 60  # 60 requests
RATE_LIMIT_WINDOW = 60        # per 60 seconds

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if config.DISABLE_USAGE_LIMITS:
        return await call_next(request)
    client_ip = request.client.host
    now = time.time()
    
    # Get current requests for this IP
    requests = rate_limit_records.get(client_ip, [])
    
    # Filter out old requests outside the window
    requests = [t for t in requests if now - t < RATE_LIMIT_WINDOW]
    
    if len(requests) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    
    # Add current request
    requests.append(now)
    rate_limit_records[client_ip] = requests
    
    response = await call_next(request)
    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "service": "api-backend"}


@app.get("/api", include_in_schema=False)
@app.get("/api/", include_in_schema=False)
async def api_root():
    """Evita 404 al abrir /api o /api/ en el navegador o al probar el túnel."""
    return {
        "service": "SmartBooking API",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi_json": "/openapi.json",
        "health": "/",
    }


app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(password_reset.router, prefix="/api/auth", tags=["Password Reset"])
app.include_router(platform_auth.router, prefix="/api/platform/auth", tags=["Platform Auth"])
app.include_router(platform_invitations.router, prefix="/api/platform/invitations", tags=["Platform Invitations"])
app.include_router(platform_businesses.router, prefix="/api/platform/businesses", tags=["Platform Businesses"])
app.include_router(platform_audit.router, prefix="/api/platform/audit", tags=["Platform Audit"])
app.include_router(platform_metrics.router, prefix="/api/platform/metrics", tags=["Platform Metrics"])
app.include_router(owners.router, prefix="/api/owners", tags=["Owners"])
app.include_router(businesses.router, prefix="/api/businesses", tags=["Businesses"])
app.include_router(services.router, prefix="/api/businesses", tags=["Services"])
app.include_router(customers.router, prefix="/api/businesses", tags=["Customers"])
app.include_router(appointments.router, prefix="/api/businesses", tags=["Appointments"])
app.include_router(schedules.router, prefix="/api", tags=["Schedules"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(internal_jobs.router)


def _meta_challenge_response(request: Request) -> Response:
    """Handshake GET de Meta: ?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...

    Meta espera el challenge como string crudo (puede ser alfanumérico); devolver
    int() o JSON rompería la verificación en algunos casos.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if (
        mode == "subscribe"
        and token == config.META_VERIFY_TOKEN
        and challenge is not None
    ):
        return Response(content=str(challenge), media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed")


@app.get("/webhooks/whatsapp")
async def verify_webhook_callback(request: Request):
    """Verificación en la callback URL configurada en Meta.

    Meta hace el GET de verificación exactamente sobre la callback URL, no sobre
    una subruta. Antes solo existía `/webhooks/whatsapp/verify`, así que la
    verificación desde el App Dashboard fallaba con CALLBACK_VERIFICATION_FAILED.
    Esta ruta convive con el POST del webhook en la misma URL.
    """
    return _meta_challenge_response(request)


@app.get("/webhooks/whatsapp/verify")
async def verify_webhook(request: Request):
    """Alias histórico de la verificación (se mantiene por compatibilidad)."""
    return _meta_challenge_response(request)


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request):
    """Webhook Telegram: un solo bot, tenant por vínculo usuario↔negocio."""
    if not config.TELEGRAM_ENABLED:
        raise HTTPException(status_code=410, detail="Telegram está temporalmente desactivado")
    # Si TELEGRAM_WEBHOOK_SECRET está configurado, solo se acepta la cabecera
    # que Telegram firma con ese valor. Sin la variable, el bot sigue igual.
    if not telegram_secret_is_valid(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token"),
        config.TELEGRAM_WEBHOOK_SECRET,
    ):
        logger.warning("Webhook Telegram rechazado: secret token inválido")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook Telegram: payload no es JSON válido")
        raise HTTPException(status_code=400, detail="Bad Request") from None

    try:
        return await process_telegram_update(payload)
    except Exception:
        # El detalle se queda en el log: la respuesta al cliente es genérica.
        logger.exception("Error en webhook Telegram")
        return {"status": "error"}


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Webhook principal para recibir mensajes de WhatsApp

    Flow:
    1. Validar firma Meta
    2. Extraer mensaje
    3. Obtener contexto de conversación
    4. Procesar con NLU
    5. Ejecutar handler según intent
    6. Enviar respuesta por WhatsApp
    7. Guardar en contexto
    """
    try:
        # 1. Validar firma de Meta
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")

        if not whatsapp_client.validate_signature(body, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

        # 2. Parsear payload
        payload = await request.json()

        # Un callback puede contener varios estados. La evidencia se confirma
        # antes de responder 200 para que Meta pueda reintentar si falla la BD.
        try:
            async with AsyncSessionLocal() as db:
                ledger_result = await record_whatsapp_status_payload(db, payload)
                await db.commit()
        except Exception as exc:
            logger.exception("wa_ledger_status_failed")
            raise HTTPException(status_code=503, detail="Estado no registrado") from exc
        if ledger_result.unresolved:
            logger.warning("wa_status_unresolved count=%s", ledger_result.unresolved)

        # 3. Extraer mensaje
        message_data = whatsapp_client.extract_message_from_webhook(payload)

        if not message_data:
            # No es un mensaje válido
            return {"status": "ok"}

        if message_data.get("type") == "status_update":
            # El estado ya quedó registrado; no es un mensaje entrante.
            logger.info(
                "wa_status_update status=%s wamid=%s business_phone=%s recorded=%s",
                message_data.get("status"),
                message_data.get("message_id"),
                message_data.get("business_phone_number_id"),
                ledger_result.recorded,
            )
            return {"status": "ok"}

        # Meta manda `from` en E.164 con formato libre (puede traer +, espacios…);
        # normalizar como punto único de entrada (clientes, contexto e idempotencia).
        phone_number = normalize_channel_phone(message_data["from"])
        # Respuesta interactiva (button_reply/list_reply): se rutea por el id
        # estructurado (nunca por el título visible, que es solo texto).
        payload_id = message_data.get("list_payload") or message_data.get("button_payload")
        message_text = payload_id if payload_id else (message_data.get("text") or "")
        message_id = message_data["message_id"]

        # Marcar como leído
        await whatsapp_client.mark_as_read(
            message_id, message_data["business_phone_number_id"]
        )

        # 4. Mapear phone_number_id a business_id dinámicamente
        phone_number_id = message_data["business_phone_number_id"]
        business_info = await db_service.get_business_by_phone_id(phone_number_id)
        
        if not business_info:
            print(f"Business not found for phone_number_id: {phone_number_id}")
            return {"status": "error", "message": "Business not found"}
            
        business_id = business_info["id"]

        if not await should_process_channel_event(
            channel="whatsapp",
            business_id=business_id,
            user_key=phone_number,
            event_id=message_id,
        ):
            return {"status": "ok"}

        # 4. Obtener contexto y decidir ruta guiada antes de contar cuota IA.
        context = await conversation_manager.get_context(business_id, phone_number)
        decision = route_guided_message(message_text, context)

        quota = await consume_daily_quota(
            business_id=business_id,
            user_channel_id=phone_number,
            is_ai_message=decision.uses_ai,
        )
        if not quota["allowed"]:
            await _send_whatsapp_and_record(business_id, whatsapp_client.send_text_message(
                to=phone_number,
                message=quota["message"],
                phone_number_id=message_data["business_phone_number_id"],
            ))
            return {"status": "ok"}

        resp = await execute_guided_route(business_id, phone_number, decision, context)
        if resp:
            logger.info(
                "wa_route guided_router kind=%s business=%s user=%s",
                decision.kind,
                business_id,
                phone_number,
            )
            await conversation_manager.save_message(
                business_id, phone_number, "user", message_text
            )
            # Decisión #7: las decisiones van SIEMPRE en interactivos nativos
            # (reply buttons ≤3 / list ≤10), nunca menús numerados de texto.
            render = render_bot_reply(resp)
            pid = message_data["business_phone_number_id"]
            if render.kind == "list":
                await _send_whatsapp_and_record(business_id, whatsapp_client.send_list_message(
                    to=phone_number,
                    body_text=render.text,
                    sections=render.sections,
                    phone_number_id=pid,
                ))
            elif render.kind == "button":
                await _send_whatsapp_and_record(business_id, whatsapp_client.send_interactive_buttons(
                    to=phone_number,
                    body_text=render.text,
                    buttons=render.buttons,
                    phone_number_id=pid,
                ))
            else:
                await _send_whatsapp_and_record(business_id, whatsapp_client.send_text_message(
                    to=phone_number,
                    message=render.text,
                    phone_number_id=pid,
                ))
            await conversation_manager.save_message(
                business_id, phone_number, "assistant", resp
            )
            return {"status": "ok"}

        # 6–11. Turno conversacional unificado (orchestrator)
        logger.info(
            "wa_route pass_through kind=%s uses_ai=%s business=%s user=%s",
            decision.kind,
            decision.uses_ai,
            business_id,
            phone_number,
        )
        response_text = await run_conversation_turn(business_id, phone_number, message_text)
        logger.info("wa_route ai_pipeline business=%s user=%s", business_id, phone_number)
        # run_conversation_turn devuelve str: el path NLU queda solo texto (sin
        # interactivos) hasta que el orchestrator emita BotReply.
        out_text = strip_html(getattr(response_text, "text_plain", None) or str(response_text))
        await _send_whatsapp_and_record(business_id, whatsapp_client.send_text_message(
            to=phone_number,
            message=out_text,
            phone_number_id=message_data["business_phone_number_id"],
        ))
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error en webhook WhatsApp")
        return {"status": "error"}


async def _send_whatsapp_and_record(business_id: int, operation):
    """Guarda el ID de Meta sin repetir un envío que ya fue aceptado."""
    response = await operation
    try:
        async with AsyncSessionLocal() as db:
            if await record_outbound_response(db, business_id, response):
                await db.commit()
    except Exception:
        # El mensaje ya salió; un error de bitácora no debe reenviarlo.
        logger.exception("wa_ledger_outbound_failed business=%s", business_id)
    return response
