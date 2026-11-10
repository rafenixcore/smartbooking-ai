# Modelo de datos propuesto

La migración `7c9d2e4f6a10` contiene el esquema de plataforma y T003 añadió sus modelos ORM. T016 añadió `a6e1c9b4d270` para los límites de recuperación persistentes; la corrección R4 añadió `b7c2f3e4d590` para revocar accesos de dueño tras logout y R6 añadió `c8e3d4f5a601` para los intentos fallidos de administración. Solo se han aplicado en PostgreSQL local desechable; no se desplegaron ni ejecutaron en producción.

| Entidad | Campos principales | Reglas |
|---|---|---|
| `PlatformAdmin` | id, email único normalizado, password hash, activo, creado_en | Bootstrap controlado; no registro público. No pertenece a un negocio. |
| `PlatformAdminSession` | admin_id, hash/identificador de refresh, vencimiento, revocación | Tokens de plataforma diferenciados de los de dueño. |
| `PlatformLoginAttempt` | hash HMAC de correo, hash HMAC de IP, creado_en | Registra solo fallos de login administrativo. Límites confirmados: 5/correo y 20/IP por hora; contador serializado en PostgreSQL. |
| `Owner` existente | id, email, password hash, email_verified, `name` nullable, `is_active`, `access_revoked_at` | El correo llega de la invitación; el nombre se recoge después en el alta. `access_revoked_at` invalida JWT previos al logout; el login posterior crea un token utilizable. |
| `Business` existente | id, owner_id, nombre, teléfono, dirección, descripción, is_active, onboarding_completed_at | Negocios existentes con nombre/teléfono no vacíos se marcan completos con `created_at` o la fecha de migración. No borrar historial al suspender. |
| `BusinessMembership` | business_id, user_id → owners.id, role, is_active, created_at | La migración crea membresías `owner` para negocios existentes; el alta crea la membresía junto con cada negocio nuevo. El índice parcial impide dos dueños activos de un mismo negocio; otros miembros quedan para una fase futura. |
| `OwnerInvitation` | id, email, token_hash, estado, vence_en, aceptada_en, revocada_en, enviada_en, invitado_por_admin_id | Token de un uso, reenvío invalida anterior. Correo único pendiente sujeto a concurrencia. |
| `PasswordReset` | id, owner_id o platform_admin_id, token_hash, vence_en, usada_en, creada_en | Una restricción exige exactamente uno de los dos principales. El token dura una hora y se consume una vez; al usarlo se invalidan otros enlaces pendientes de la misma cuenta. |
| `PasswordResetRequestAttempt` | id, hash de correo, hash de IP, creada_en | HMAC de correo e IP sin valores en claro. Límites confirmados: 5 por correo y 20 por IP cada hora; la tabla sobrevive a reinicios y se podan registros fuera de ventana. |
| `AdminAuditEvent` | id, admin_id, accion, entidad, entidad_id, resultado, creado_en, resumen seguro | Nunca guardar contraseña, token, contenido de mensaje ni datos personales innecesarios. |
| `MessageEvent` | id, business_id, channel, event_key, provider_message_id, provider_event_id, direction, status, category, country, occurred_at, created_at | Índice único `(business_id, channel, event_key)`. T024 usa hash determinista del ID de Meta y del estado/instante para eventos individuales; `message:*` guarda el último estado conocido. |
| `MessageCostRecord` | id, business_id, message_event_id opcional, idempotency_key, amount, currency, source, rate_version, evidence_reference, periodo, reconciled_at | `source`: `estimated` o `reconciled`. Un costo reconciliado exige evidencia y periodo; el importe es no negativo. |

## Transiciones

**Invitación**: `pending → accepted | expired | revoked`. Reenviar crea token nuevo y deja el anterior inutilizable. Correo fallido conserva estado visible de fallo de envío y posibilidad de reintento.

**Alta del dueño**: `invited → credentials_set → business_incomplete → active`. Un negocio suspendido tiene acceso operativo bloqueado aunque exista sesión válida. Reanudación del alta tras abandono conserva la cuenta y permite completar el negocio.

**Mensaje**: `created → sent → delivered | failed`; pueden llegar eventos fuera de orden. El estado agregado no retrocede por duplicados ni eventos tardíos, pero el historial conserva la evidencia.

## Migración y compatibilidad

- Las cuentas `Owner` existentes se conservan y no se les exige una invitación retroactiva. Antes de quitar registro público se define cómo identificar las cuentas legítimas existentes.
- Los negocios existentes se consideran completos solo si cumplen los datos obligatorios del flujo vigente; la migración no debe bloquearlos accidentalmente.
- Los refresh tokens actuales de dueños continúan válidos según su política hasta un corte planificado; los de plataforma usan tipo y almacenamiento separados.
- La regla de un negocio activo por dueño se mantiene. La relación futura de miembros no habilita multinegocio ni varios usuarios por negocio en esta entrega.
- El downgrade de `7c9d2e4f6a10` se niega a descartar administradores, invitaciones, recuperaciones, auditoría, eventos/costos, dueños incompletos o suspendidos y membresías que no sean el backfill original. Esto permite revertir antes de activar la función sin pérdida silenciosa; después de activarla, cualquier reversión exige plan de conservación/migración de esos datos.
- El downgrade de `a6e1c9b4d270` elimina únicamente contadores temporales de solicitudes de recuperación; durante la reversión se pierde la ventana de límites en curso.
- El downgrade de `b7c2f3e4d590` elimina el marcador de revocación de accesos de dueño; no debe utilizarse para una aplicación con sesiones activas sin un plan de rotación de JWT.
- El downgrade de `c8e3d4f5a601` elimina los contadores de intentos fallidos de administración; se pierde la ventana de límites en curso.
