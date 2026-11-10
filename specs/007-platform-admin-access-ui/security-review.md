# Revisión final de seguridad, privacidad y migraciones — T035

**Fecha:** 2026-11-09
**Alcance:** revisión de código y artefactos locales de la fase 007, más actualización posterior de configuración de correo en Railway. Neon y migraciones de la rama no se comprobaron en producción.

## Resultado

La separación de identidades existe en servidor: las rutas `/api/platform/*` usan `get_current_platform_admin`, las rutas operativas de dueño comprueban propiedad y estado del negocio, y los tokens de invitación/recuperación se guardan como hash. La bitácora administrativa expone solo actor, acción, entidad, resultado y fecha. El libro de mensajes no guarda destinatarios ni contenido. La revisión Alembic final en el repositorio es `c8e3d4f5a601` y depende de `b7c2f3e4d590`. Estas migraciones no se han aplicado en producción.

La revisión identificó estos puntos antes del despliegue:

| ID | Prioridad | Evidencia local | Efecto y acción requerida |
|---|---|---|---|
| R1 | Alta | `app/api/businesses.py:create_business` inserta `Business` sin `BusinessMembership`. La migración `7c9d2e4f6a10` solo crea membresías para negocios preexistentes; no hay otra inserción de `BusinessMembership` en el backend. | Los negocios creados después de la migración carecen de la relación `owner` prevista por FR-006. Crear ambas filas en la misma transacción y comprobar alta y concurrencia en PostgreSQL. |
| R2 | Alta | `app/services/owner_invitations.py:resend_invitation` permite pasar una invitación `expired` a `pending` sin comprobar si ya existe otra pendiente para ese correo. La migración tiene `uq_owner_invitations_pending_email_ci`. | Si se creó una nueva invitación para el mismo correo, reenviar la antigua puede acabar en `IntegrityError` y HTTP 500. Resolver el conflicto como error de dominio y probar el caso. |
| R3 | Alta | `app/services/message_ledger.py:record_outbound_response` y `record_whatsapp_status_payload` consultan si otro negocio conoce el ID antes de insertar, sin bloqueo común. `uq_message_events_identity` solo incluye `business_id`. | Dos transacciones simultáneas pueden atribuir el mismo ID de Meta a negocios distintos. Serializar por ID de mensaje o imponer unicidad global para la fila canónica y probar la carrera; evitar que el gasto cuente dos veces. |
| R4 | Alta | `app/core/security.py` emite accesos de dueño por siete días; `app/api/auth.py:logout` solo revoca refresh y `get_current_owner` no consulta revocación de logout. | Un access token emitido antes de cerrar sesión sigue utilizable hasta caducar. Reducir duración o introducir sesión revocable para dueño y probar logout con token previo. El reset sí invalida accesos previos mediante `iat_ns`. |
| R5 | Media | `app/services/email_service.py:send_verification_email` registra el enlace completo cuando no hay SMTP; `/api/auth/resend-verification` sigue disponible para cuentas heredadas. | Un token de verificación puede quedar en logs. Retirar el enlace del log y comprobar el caso sin SMTP antes del despliegue. |
| R6 | Media | `main.py:rate_limit_middleware` limita 60 solicitudes por IP y minuto mediante un diccionario en memoria; `app/api/platform_auth.py:login_platform_admin` no tiene límite propio persistente. | El límite cambia entre procesos/reinicios. Definir un límite persistente para intentos de administración y comprobar concurrencia antes de abrir el panel. |

## Seguimiento posterior — 2026-11-09

El usuario autorizó una base PostgreSQL local desechable y pruebas enfocadas. Confirmó además 5 intentos fallidos por correo y 20 por IP durante una hora para `/admin`. R1–R6 están corregidos localmente:

- **R1:** la creación de negocio inserta la membresía `owner` en la misma transacción. La prueba HTTP comprueba exactamente una membresía.
- **R2:** el reenvío rechaza una invitación vencida si ya existe otra pendiente o si el correo ya tiene dueño; las violaciones de unicidad se convierten en error de dominio. Dos casos nuevos probaron ambos conflictos.
- **R3:** un bloqueo transaccional por ID de Meta precede a la consulta de atribución. En callbacks con varios IDs, los bloqueos se toman en orden estable. Pruebas concurrentes cubrieron dos negocios y callbacks inversos; 13 pruebas de mensajería aprobaron.
- **R4:** `logout` marca la revocación de accesos del dueño y elimina sus refresh en una transacción. La migración `b7c2f3e4d590` agrega `owners.access_revoked_at`; upgrade/downgrade pasaron en base local. Se verificó que el token previo falla y un login nuevo funciona. El bootstrap de administrador exige la nueva cabeza Alembic y sus siete pruebas aprobaron.
- **R5:** sin SMTP se registra solo que no se envió verificación, sin URL, token ni destinatario. La prueba de logs pasó.

- **R6:** `platform_login_attempts` guarda solo hashes HMAC y hora del fallo. Un lock transaccional permite aplicar exactamente 5/correo y 20/IP/hora entre workers. La prueba concurrente confirmó cinco respuestas 401 y una 429; las pruebas de login existentes aprobaron. La migración `c8e3d4f5a601` se verificó con upgrade/downgrade.

## Límites operativos verificados

- Resend presenta `rafenixcore.com` verificado y con envío activo. El 2026-11-10 se configuraron en Railway `RESEND_API_KEY` (solo envío, restringida al dominio) y `RESEND_FROM_EMAIL`; el remitente de plataforma se probó con estado `delivered`. T034 queda verificada; T017/T033 aún necesitan recorrido real desde la aplicación. Cloudflare MCP no está disponible, y no se cambió DNS porque Resend ya verificaba el dominio.
- No hay llamadas de producción a `estimate_message_cost` ni a `record_reconciled_period_total`; solo aparecen en el servicio y pruebas. Sin tarifas versionadas ni conciliación, la UI debe mantener el costo como no disponible. No hay base para mostrar gasto real.
- La migración se probó previamente en PostgreSQL local desechable según T002/T016. Después de R4/R6 se probó upgrade/downgrade hasta la nueva cabeza `c8e3d4f5a601` en una base local aparte; no se comprobó Neon.
- El perfil frontend había pasado lint y build en T033. En T035 el build y ESLint de las pantallas ajustadas aprobaron; no se hizo recorrido visual con navegador.
- La revisión automática rechazó inicialmente crear la base de prueba sin autorización explícita. Después el usuario la autorizó y R1–R5 se corrigieron y verificaron localmente. No se modificó producción.

## Correcciones de interfaz realizadas en T035

Las pantallas de invitación y recuperación muestran la marca Turno, los campos de contraseña ofrecen un control accesible para mostrar/ocultar el valor, y el resultado de recuperación ofrece también el acceso de administración. Estas correcciones no cambian datos ni permisos de servidor.

**Estado para despliegue:** pendiente. R1–R6 se corrigieron localmente y correo de producción está configurado. Aún falta completar el recorrido de `quickstart.md` y verificar migraciones, permisos y métricas en un entorno de prueba antes de solicitar autorización para publicar.
