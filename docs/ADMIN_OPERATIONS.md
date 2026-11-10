# Operación del acceso de plataforma

Este documento describe cómo preparar el esquema y habilitar el primer
administrador de SmartBooking. Es un runbook para las tareas T002–T020. La
migración y el bootstrap se ejecutaron en Neon production el 2026-11-10. La
configuración de la contraseña y el acceso a `/admin` se completaron; la
invitación de un dueño nuevo sigue pendiente de prueba productiva.

## Estado de implementación

- Las migraciones `7c9d2e4f6a10`, `a6e1c9b4d270`, `b7c2f3e4d590` y `c8e3d4f5a601`, y sus modelos ORM, existen en el repositorio.
- La migración se verificó en PostgreSQL local desechable y se aplicó a Neon
  production el 2026-11-10. La revisión es `c8e3d4f5a601`; se conservaron 6
  dueños y 4 negocios y se crearon 4 membresías `owner`. El respaldo previo se
  restauró correctamente en PostgreSQL 18 desechable; ver `docs/WORKLOG.md`.
- El backend ya implementa `POST /api/platform/auth/token`, renovación, cierre
  de sesión y `GET /api/platform/auth/me` (T006). Los JWT de plataforma duran
  15 minutos y el refresh de sesión, 7 días, sujeto a revocación.
- La cuenta de plataforma no se crea con la migración. T007 añadió un comando
  de bootstrap para crear únicamente el primer administrador.
- El login de `/admin` limita fallos a 5 por correo y 20 por IP durante una hora.
  Los contadores persisten en PostgreSQL como hashes HMAC, sin guardar correo ni
  IP en claro en esa tabla; el bloqueo devuelve HTTP 429.
- T008 añadió restricciones de backend para dueños y negocios suspendidos o
  incompletos. T010 añadió rutas de invitaciones y aceptación con vigencia de 72
  horas. T011 conecta el envío por Resend; el frontend de invitación/alta está en
  T012–T013. T016 añadió recuperación de contraseña para dueño y plataforma;
  T017 completó sus pantallas y plantillas; Resend entregó un correo directo de
  prueba y una recuperación generada desde la app. La invitación sigue pendiente.
  T019–T026 añadieron gestión, bitácora y métricas de `/admin`. El panel se
  desplegó el 2026-11-10. Se creó la única cuenta inicial de administrador con
  contraseña aleatoria no divulgada; la recuperación solicitada desde la app
  fue entregada por Resend, consumida y permitió entrar a `/admin`. Falta
  probar invitación desde el panel antes de invitar usuarios reales.

## Correo de invitación

Resend muestra `rafenixcore.com` como dominio verificado y habilitado para
envíos. El código de invitación usa la API HTTP de Resend y requiere estas
variables en el backend:

- `RESEND_API_KEY`: clave secreta del entorno, solo en el gestor de secretos.
- `RESEND_FROM_EMAIL`: remitente explícito dentro del dominio verificado. En
  Railway `production` está configurado como `SmartBooking <no-reply@rafenixcore.com>`.
- `FRONTEND_BASE_URL`: origen público del frontend; el enlace se construye como
  `/invitation#token=...`.

Sin clave o remitente configurados, la invitación se conserva y su
`delivery_status` queda `failed`, disponible para reintentar desde la plataforma.
`sent` significa que Resend aceptó la solicitud; no prueba que el correo llegó a
la bandeja. El token plano solo se usa dentro del proceso de envío y no se
devuelve en API ni se escribe en logs. En la revisión de Railway `production`
(2026-11-09), ambas variables faltaban. El 2026-11-09 se configuró una clave
Resend con permiso de envío limitada al dominio `rafenixcore.com`; el valor
secreto está solo en Railway y no se registra aquí. El backend redeployó
correctamente. Resend confirmó como `delivered` un correo de prueba enviado desde
el remitente configurado. El dominio ya estaba verificado y habilitado para
envío, por lo que no fue necesario cambiar DNS. El MCP de Cloudflare no está
disponible en esta sesión y no se inspeccionó la zona allí.

## Recuperación de contraseña

`POST /api/auth/password-reset/request` responde igual para correos existentes y
desconocidos. Los enlaces duran una hora y se limitan a 5 solicitudes por correo
y 20 por IP cada hora; los contadores HMAC se guardan en PostgreSQL. El cambio de
contraseña consume el enlace y revoca sesiones de dueño o plataforma. El correo
usa Resend y un enlace con fragmento `/reset-password#token=...`; T017 añadió
las pantallas y plantillas. La clave de envío y el remitente están configurados
en Railway `production`. La entrega directa de prueba desde Resend fue confirmada.
La solicitud iniciada desde la aplicación se entregó el 2026-11-10 y su enlace
fue consumido; el usuario confirmó que entró a `/admin`. El vencimiento y uso
único están cubiertos por pruebas locales, no se probaron manualmente en producción.

## Suspensión de negocios y bitácora

El administrador autenticado puede consultar `GET /api/platform/businesses`,
filtrar por `status=active|suspended` o buscar por nombre/correo con `q`.
`POST /api/platform/businesses/{id}/suspend` bloquea la operación del negocio
incluso si el dueño conserva una sesión previa. `reactivate` restablece el
acceso operativo. Estas acciones cambian `Business.is_active`, no borran citas
ni modifican la contraseña o el estado de `Owner`. Las solicitudes repetidas y
los IDs inexistentes se registran con resultado `unchanged` o `not_found`.

`GET /api/platform/audit` requiere sesión administrativa vigente y permite
consultar eventos por entidad; devuelve actor, acción, entidad, resultado y
fecha. No expone `details`, teléfonos, correos de clientes, mensajes ni tokens.
Antes de suspender una cuenta real, verificar el ID y el negocio en el panel;
las rutas están implementadas localmente, sin despliegue a producción.

## Preparación de un entorno

1. Confirma el entorno, proyecto, servicio y base de datos destino desde sus
   consolas oficiales. No copies una URL de base de datos entre entornos.
2. Verifica que la versión de código a desplegar contiene la migración y los
   modelos ORM. La revisión de plataforma es `7c9d2e4f6a10`, su revisión
   previa es `f5b6ae5f0595`; la revisión de recuperación es `a6e1c9b4d270`, la revocación de accesos es `b7c2f3e4d590` y la cabeza actual es `c8e3d4f5a601`.
3. Confirma que existe un respaldo recuperable de la base. En producción,
   registra el punto de restauración y acuerda una ventana de cambio antes de
   aplicar la migración.
4. Inyecta `DATABASE_URL` usando el gestor de secretos del entorno o una sesión
   segura. No la escribas en comandos, tickets, capturas, shell history ni logs.
5. Desde `backend/api-backend`, consulta la revisión actual:

   ```sh
   alembic current
   ```

   Si hay más de una cabeza, la revisión no coincide con la esperada o la base
   no es el destino confirmado, detente y revisa las migraciones antes de
   continuar. No cambies manualmente `alembic_version`.

## Aplicar la migración

Ejecuta solo después de completar la preparación y autorizar el cambio para ese
entorno:

```sh
cd backend/api-backend
alembic upgrade head
alembic current
```

Confirma que `alembic current` muestra `c8e3d4f5a601` y revisa los logs de la
migración por errores. La migración agrega las tablas de administración,
invitaciones, recuperaciones, membresías, auditoría y eventos/costos; conserva
los dueños y negocios existentes, crea una membresía para cada dueño asociado y
marca como completados los negocios existentes que tienen nombre y teléfono no
vacíos.

Después del cambio, valida los conteos de dueños y negocios contra los valores
previos al cambio. La migración no debe borrar esas filas. El bootstrap es un
paso separado y requiere autorización operativa para el entorno concreto.

## Crear el primer administrador

Tras verificar el destino, aplicar la migración y obtener la autorización
operativa para ese entorno, ejecuta desde `backend/api-backend`:

```sh
python -m scripts.bootstrap_admin --email admin@tu-dominio.example
```

Sustituye el ejemplo por el correo aprobado. El comando pide dos veces la
contraseña en una terminal sin mostrarla; debe tener al menos 12 caracteres y
como máximo 72 bytes UTF-8. No la incluyas en argumentos, variables impresas,
archivos versionados ni logs. El comando requiere que Alembic esté exactamente
en la revisión `c8e3d4f5a601`; de lo contrario, se detiene.

El primer intento crea una sola cuenta. Repetirlo con el mismo correo, incluso
con otras mayúsculas, informa que ya existe y no cambia la contraseña. Si se
indica otro correo o la cuenta está inactiva, se detiene sin crear ni reactivar
cuentas. Dos intentos simultáneos se serializan en PostgreSQL. Este comando no
sirve para rotar credenciales ni para crear administradores adicionales.

Registra quién autorizó el bootstrap, el entorno y el resultado, sin guardar
contraseñas, tokens ni hashes. Completa los permisos de plataforma de T008
antes de permitir el acceso al administrador.

## Comprobación posterior

- La revisión Alembic es `c8e3d4f5a601`.
- Siguen presentes los dueños y negocios que existían antes del cambio.
- Los negocios preexistentes tienen una membresía de rol `owner` para su dueño.
- No se habilitó el acceso de plataforma antes de completar T005–T008.
- No hay secretos ni enlaces de invitación en logs.
- La creación de administrador y las operaciones posteriores quedan registradas
  según la bitácora que implementará T020.

Si cualquiera de estos puntos falla, no continúes con invitaciones ni habilites
el panel. Conserva los logs técnicos sin secretos y diagnostica primero el
entorno y el estado de la base.

## Reversión y recuperación

La migración tiene una salvaguarda: `alembic downgrade f5b6ae5f0595` aborta si
detecta datos de plataforma que perdería, dueños incompletos o suspendidos, o
membresías que ya no coinciden con la relación original entre negocio y dueño.
El downgrade solo es viable mientras no se hayan creado datos de plataforma ni
se hayan cambiado esas condiciones.

Antes de considerar un downgrade:

1. Detén el despliegue y bloquea nuevas escrituras de la función afectada.
2. Conserva el estado actual y confirma que el respaldo está disponible.
3. Revisa en un entorno aislado si el downgrade pasa sus salvaguardas.
4. Si la base ya contiene al administrador inicial, invitaciones, auditoría,
   recuperaciones, eventos/costos o cambios de membresía, **no borres esos datos
   para forzar el downgrade**. Recupera un respaldo previo en un destino aislado
   para evaluar la recuperación, o prepara una migración correctiva hacia
   delante que conserve esos datos.
5. Para producción, la restauración o migración correctiva requiere autorización
   y un plan de recuperación aprobado para el entorno concreto.

Nunca marques manualmente `alembic_version` para simular una reversión. El
respaldo y la migración correctiva son las opciones de recuperación si el
downgrade protegido no aplica.

## Límites conocidos

- El flujo de invitación y recuperación aún no ha completado el recorrido manual
  desde la app. La prueba directa de Resend sí figura como entregada.
- El dominio de Resend está verificado; la clave restringida al dominio y el
  remitente están configurados en Railway `production`. No se cambió DNS. No se
  inspeccionó la zona Cloudflare porque no hay un MCP de Cloudflare habilitado.
- `/admin` y sus rutas están desplegados; la navegación directa y CORS se
  verificaron. Falta el recorrido autenticado, la invitación y la recuperación.
- Después de crear datos de plataforma, la migración no puede revertirse con
  downgrade sin perderlos; usar un plan de conservación y recuperación.
