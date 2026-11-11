# Plan: WhatsApp multi negocio desde plataforma y pausa temporal de Telegram

## Diseño

El modelo actual conserva `Business.whatsapp_phone_number_id` como clave de enrutamiento única. Se retira la unicidad de `Business.waba_id`, ya que varios tenants pueden compartir una cuenta Meta. Los cambios de canal se mueven a endpoints `/api/platform/...` protegidos con `get_current_platform_admin`; el API del dueño ya no acepta ni devuelve IDs WhatsApp.

La UI agrega una sección WhatsApp al detalle de negocio en `/admin`, con edición explícita del Phone Number ID y WABA ID y un estado que solo significa “credenciales guardadas”. El backend registra acciones en la bitácora. Tokens, app secret y verify token permanecen en variables de entorno y nunca se guardan ni se devuelven en DB/API.

Telegram se desactiva con `TELEGRAM_ENABLED=false` como valor predeterminado. El webhook y endpoints de activación responden 410, se omiten los envíos de recordatorio y se quitan navegación, rutas, checklist y referencias activas de UI. Se conservan adaptadores y datos para reactivar luego.

## Fases y verificación

1. **Contrato y pruebas backend (high):** autorización admin, IDs editables, ID de cuenta repetible, Phone Number ID duplicado rechazado, owner sin acceso, Telegram 410 y sin envíos Telegram.
2. **Persistencia y API (high):** migración no destructiva para retirar unique de WABA ID; DTO/admin endpoints; bitácora.
3. **UI (medium):** sección `/admin`; retirar campos del dueño y superficies Telegram; pruebas Vitest.
4. **Cierre (medium):** ajustar baseline/constitución/runbooks/worklog; suites enfocadas, build/lint y `git diff --check`.

No se hará configuración de Meta, métodos de pago ni despliegue externo dentro de esta especificación.
