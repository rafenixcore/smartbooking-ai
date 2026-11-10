# Contratos de acceso, administración y UI

Son contratos de diseño. Los nombres de rutas API son propuestos; durante implementación se adaptarán a la convención existente sin cambiar estos comportamientos.

## Rutas públicas de la UI

| Ruta | Estado esperado |
|---|---|
| `/login` | Acceso del dueño por correo y contraseña; enlace «Olvidé mi contraseña». Sin registro público ni credenciales demo. |
| `/invitation#token=...` | El token llega en el fragmento del navegador, que no se envía en la petición HTTP; se limpia de la barra tras leerlo. Muestra el correo asignado y pide contraseña y confirmación. |
| `/forgot-password` | Solicitud por correo con respuesta neutral. |
| `/reset-password#token=...` | El token viaja en el fragmento y la SPA lo limpia al cargar. Solicita contraseña y confirmación; enlace vencido/usado permite pedir otro. |
| `/admin` | Acceso/entrada a panel de plataforma; identidad de plataforma obligatoria. |
| Panel de negocio actual | Si falta negocio completo, mostrar solo alta; después, panel operativo. |

## Contratos API propuestos

| Operación | Principal | Respuesta/garantía |
|---|---|---|
| `POST /api/auth/invitations/preview` | Token de invitación | Devuelve correo fijado y vencimiento solo mientras la invitación siga válida; token viaja en el body, no en la URL. |
| `POST /api/auth/invitations/accept` | Enlace público válido | Consume token una vez, fija contraseña del correo invitado y crea/activa dueño. Enlace válido 72 horas; respuesta de error genérica para token inválido, vencido, revocado o usado. |
| `POST /api/auth/password-reset/request` | Público | Respuesta neutral para correo conocido/desconocido; enlace válido una hora. Máximo 5 solicitudes por correo y 20 por IP cada hora. |
| `POST /api/auth/password-reset/confirm` | Enlace válido | Cambia contraseña y revoca sesiones de acceso y renovación. El token solo se usa una vez. |
| `POST /platform/auth/token` | Administrador | Token tipado como plataforma; no aceptado por rutas de dueño. Tras 5 fallos por correo o 20 por IP en una hora responde 429; los contadores persisten sin correo ni IP en claro. |
| `GET/POST /api/platform/invitations` | Administrador | Lista/crea invitaciones con estados y control de duplicados. |
| `POST /api/platform/invitations/{id}/resend|revoke` | Administrador | Reenvío rota token y reinicia plazo de 72 horas; revocación invalida enlace. Las respuestas nunca incluyen el token plano. |
| `GET /platform/businesses` | Administrador | Lista paginada y filtrable; datos personales mínimos. |
| `GET /api/platform/businesses/{id}` | Administrador | Detalle mínimo de negocio y dueño asociado. |
| `POST /platform/businesses/{id}/suspend|reactivate` | Administrador | Cambio de acceso auditable; no borra datos. |
| `GET /api/platform/audit` | Administrador | Bitácora paginada de actor, acción, entidad, resultado y momento; sin detalles sensibles. |
| `GET /platform/metrics` | Administrador | Periodo y definiciones; global y por negocio. Costo con `status=actual|estimated|unavailable` y fuente. |

### Contrato de métricas implementado en T023–T025

La ruta es `GET /api/platform/metrics`, solo para administrador activo con sesión
vigente. Acepta `from` y `to` como instantes ISO-8601 con zona horaria, normaliza
a UTC y usa el intervalo semiabierto `[from, to)`. El periodo debe ser positivo
y no superar 366 días. `offset` comienza en 0 y `limit` admite 1–100; el valor
predeterminado es 25.

La respuesta contiene `period` (`start`, `end`, `timezone: "UTC"`),
`global` y un objeto paginado `businesses` (`items`, `total`, `offset`, `limit`).
Cada resumen incluye `appointments.total`, `appointments.by_status`,
`customers_with_appointments`, `messages` y `cost`. La clave `definitions`
explica fórmula y tabla fuente. Cada fila de negocio añade ID y nombre, sin
teléfono, clientes o contenido de mensajes. Una cita cuenta una vez por fila,
sin excluir canceladas; los estados P/C/A/D aparecen con cero si faltan y otros
estados conservan su clave. Los clientes son `customer_id` distintos no nulos
con cualquier cita del periodo. La cifra no se llama «clientes nuevos».

`messages.total` y `messages.by_status` cuentan una fila canónica `message:*`
por ID saliente de WhatsApp cuyo instante del último estado conocido cae en el
periodo. Los eventos individuales `status:*` no se suman. Una actualización de
estado puede mover el mensaje a otro periodo: esta métrica muestra estado
actual de mensajes en el periodo, no un histórico inmutable de envíos.

`cost.status` es `actual`, `estimated` o `unavailable`; `amount` es texto decimal
o `null`, con moneda, motivo, fuente, versiones de tarifa y cobertura
`delivered`/`priced`. `actual` requiere conciliación completa del periodo exacto
con evidencia de facturación. `estimated` requiere que todos los mensajes
entregados tengan estimación con tarifa versionada, fuente y la misma moneda.
La cifra global solo es `actual` si todos los negocios tienen conciliación del
periodo en la misma moneda; una conciliación parcial deja el global como
`unavailable`. No hay tarifa precargada ni importador de facturas en esta fase:
sin esos datos el importe queda `unavailable`. El estado entregado puede venir
sin país verificable; tampoco se infiere país del teléfono del cliente.

La pantalla está disponible en `/admin/metrics`, con selección inclusiva de días
UTC (máximo 366 días), tarjetas globales, desglose visual de estados y tabla
paginada por negocio. En móvil, el detalle por negocio se muestra en tarjetas.
Se muestra el origen de conciliación/tarifa cuando existe, y la cobertura
incompleta indica cuántos mensajes entregados tienen precio. Los estados sin
datos explican la razón; no se usan datos de ejemplo.

### Gestión de negocios y bitácora implementadas en T019–T020

- La ruta concreta de listado es `GET /api/platform/businesses`. Acepta `offset`
  (desde 0), `limit` (1–100), `status=active|suspended` y `q` (nombre de negocio
  o correo del dueño). Devuelve `items`, `total`, `offset` y `limit`. Cada item
  incluye ID, nombre, estado del negocio, si completó el alta, ID/correo/estado
  del dueño y fecha de creación. No expone teléfono, clientes ni conversaciones.
- `GET /api/platform/businesses/{id}` devuelve el mismo esquema mínimo para
  mostrar el detalle de una cuenta, y responde 404 si no existe.
- `POST /api/platform/businesses/{id}/suspend` y `/reactivate` modifican
  `Business.is_active`. El dueño conserva su identidad, pero las rutas
  operativas del negocio suspendido se deniegan incluso con una sesión previa.
  Un reintento del mismo estado no cambia la cuenta y queda auditado como
  `unchanged`; un ID inexistente responde 404 y se audita como `not_found`.
- `GET /api/platform/audit` acepta `offset`, `limit`, `entity_type` y
  `entity_id`. Devuelve `items`, `total`, `offset` y `limit`; cada evento contiene
  ID, ID del administrador, acción, tipo/ID de entidad, resultado y fecha. El
  campo interno `details` no se devuelve. Las rutas de auditoría exigen la
  misma sesión de plataforma vigente que el resto de `/api/platform`.

## Frontera de tokens de acceso

- Los JWT nuevos llevan `token_kind=access` y `principal_type=owner` o
  `principal_type=platform_admin`. Un token de plataforma incluye `sid` de una
  sesión administrativa vigente. Un token refresh no sirve como access token.
- El guard de plataforma exige tipo `platform_admin`, sesión existente no
  revocada ni vencida y administrador activo. Un token de dueño se rechaza
  incluso si su correo e ID numérico coinciden con los del administrador.
- El guard de dueño exige tipo `owner`. Para conservar las sesiones actuales,
  acepta temporalmente JWT de dueño sin `principal_type` hasta su vencimiento;
  ese token sin tipo nunca es válido en la plataforma.
- Revocar la sesión administrativa invalida el acceso vinculado a su `sid`.
  El guard de plataforma comprueba esa condición en cada solicitud.
- El token de invitación se conserva como hash SHA-256; el valor plano solo
  queda disponible internamente para el envío de correo y no se devuelve en API.
  En el enlace se coloca en el fragmento `#token=...`, que no forma parte de la
  petición HTTP al servidor frontend; la SPA lo retira de la barra y lo envía a
  la API en el cuerpo de una petición POST.

## Permisos

| Acción | Admin plataforma | Dueño | Público |
|---|---:|---:|---:|
| Invitar dueño / gestionar negocios | Sí | No | No |
| Ver métricas globales y gasto entre negocios | Sí | No | No |
| Completar y operar negocio propio | No por defecto | Sí | No |
| Recuperar contraseña propia | Sí | Sí | Solicitar enlace |
| Invitar miembros de un negocio | Fase futura | Fase futura | No |

## Reglas de pantalla y contenido

- El panel de plataforma tiene: Resumen, Negocios, Invitaciones/usuarios, Mensajes y consumo, Métricas/actividad y bitácora administrativa.
- Las cifras tienen título preciso, periodo, definición, estado de datos y enlace al detalle cuando existe.
- El panel del dueño conserva su operación; los rótulos de «ingresos», «ocupación» y «nuevos clientes» se corrigen de acuerdo con la fórmula real antes de exponerlos.
- Estados vacíos y errores usan español claro; formularios indican obligatorio/opcional y no pierden datos ante error.
- La marca final incluye logo y favicon propios, uso consistente en correo y UI, y aprobación visual antes de reemplazar el recurso actual.
