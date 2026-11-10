# Worklog — Registro de tareas y fixes

**Propósito:** toda tarea, fix o cambio de infraestructura que se haga en este repo
**debe quedar anotado aquí**. Es el punto de verdad para que otra sesión (humano o
agente) sepa qué se hizo, qué falta y por qué.

## Convención (obligatoria)

1. **Antes de empezar** una tarea: búscala en la sección *Backlog*. Si existe, cambia su estado.
2. **Al terminar** una tarea: añade una entrada en *Registro de cambios* (más reciente arriba).
3. Cada entrada debe responder: **qué** cambió, **dónde** (archivo/servicio/variable),
   **por qué**, y **cómo se verificó**. Si no se pudo verificar, decirlo explícitamente.
4. Si una tarea se difiere, va al *Backlog* con el motivo y la fecha — nunca se borra.
5. Los cambios de infraestructura (Railway, Vercel, Neon) se anotan igual que los de código.

Estados: `PENDIENTE` · `EN CURSO` · `HECHO` · `DIFERIDO` · `DESCARTADO`

---

## Inventario de infraestructura (referencia rápida)

| Recurso | Identificador | Notas |
|---|---|---|
| Railway · proyecto | `smartbooking-ai` · `a7faa948-1b61-46e0-a0e4-001d68621971` | entorno `production` = `46e1ecd7-4c20-4804-aa1c-aafc12f4a6ba` |
| Railway · servicio backend | `smartbooking-ai` · `4cb7dbe4-5695-44a9-bfef-3dfd39c090dc` | FastAPI, root `/backend/api-backend`, Serverless ON |
| Railway · servicio cron | `reminders-cron` · `79a8984e-86df-4f2d-a82d-58e2edf067f9` | `alpine:latest`, `*/15 * * * *` |
| Neon · proyecto | `hidden-flower-89025402` (nombre: **smartbooking**) | branch `production`, BD `neondb` |
| Vercel · proyecto | `smartbookin-agent-ai` · `prj_dkWTfgeRvTm8pfEh7IEJ8TiSesGa` | plan Hobby, SPA Vite |
| GitHub | `rafenixcore/smartbooking-ai` (antes `smartbookin-agent-ai`) | Railway y Vercel despliegan de aquí |

---

## Backlog

### Bloqueante — resuelto

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 0 | **Commitear los cambios de `backend/`** | HECHO | Commit `a85bb97` pusheado a `main`. GitHub disparó el deploy `c5cfee6f` → `SUCCESS`. Producción ya es reproducible desde git. Ver la entrada de cierre |

### Producción

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 1 | `VITE_API_URL` en Vercel → URL real del backend | HECHO | Configurado por el usuario; verificado en el bundle y con CORS |
| 2 | Cron externo para recordatorios 24h/2h | **DIFERIDO** | **Apagado a petición del usuario (2026-10-04)**: no tiene sentido enviar recordatorios hasta que el MVP esté terminado y en uso. El servicio `reminders-cron` queda montado y configurado; reactivar = volver a poner `cronSchedule` (`*/15 * * * *`) vía `serviceInstanceUpdate`. Dos cosas quedaron **sin resolver** para cuando se retome: (a) la cadencia no era fiable — el contenedor tardaba ~14 min en terminar y Railway salta ejecuciones; (b) el intervalo de 15 min lo elegí yo a partir de `main.py`, nunca se acordó con el usuario |
| 3 | WhatsApp en producción | **EN CURSO** (2026-11-09) | Negocio `SmartBooking` (id 4) creado y enlazado al número real. Los nombres `META_APP_SECRET` y `META_WABA_TOKEN` ya figuran en Railway, con valores ocultos; falta confirmar permisos del token, suscripción y callback en Meta, y un intercambio real con log `wa_route`. Ver entradas del 2026-11-08 y 2026-11-09 |
| 4 | Serverless (App Sleeping) en Railway | HECHO | Ahorro ~$0.65/mes neto |
| 5 | Parar el servicio si el MVP se pausa | PENDIENTE | Decisión del usuario. Ahorro real ~$0.22/mes |
| 6 | `AI_ENABLED=false` explícito en Railway | HECHO | Estaba off solo por default del código |
| 7 | Sentry: activar o asumir ceguera ante errores | PENDIENTE | `SENTRY_DSN` ausente → $0 de costo, cero monitoreo |
| 8 | Verificar migraciones Alembic aplicadas en Neon | HECHO | `alembic_version = f5b6ae5f0595` = head |

### Higiene

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 9 | Renombrar proyecto Neon `hidden-flower-89025402` | HECHO | Ahora se llama `smartbooking` |
| 10 | Borrar filas obsoletas de `apscheduler_jobs` | HECHO | 3 filas de junio borradas; tabla en 0 |
| 11 | Quitar `REDIS_URL` de `.env`/`.env.example` | HECHO | Verificado: ningún código lo lee |
| 12 | Limpiar bloque Django/Celery en `docker-compose.yml` | DESCARTADO | Ya estaba limpio. El plan estaba obsoleto |
| 13 | Actualizar docs que describen infra inexistente | PENDIENTE | `MVP_STACK_ANALYSIS.md`, `README.md`, `PROYECTO_STATUS.md` |
| 14 | Pinear dependencias del backend | HECHO | Topes de versión mayor añadidos a `requirements.txt` |
| 17 | Configurar en Codex los MCP globales de Claude Code | **EN CURSO** (2026-11-09) | Definiciones agregadas y TOML validado: AWS, GitHub, Railway, Vercel, Neon, Resend, Sentry, Meta WhatsApp y Cloudflare. Último `codex mcp list`: OAuth pendiente/estado desconocido en los seis servidores HTTP; AWS no tiene credenciales locales utilizables y Railway login espera completar el navegador. Configuración local en `~/.codex/config.toml`; respaldo pre-reparación en `~/.codex/config.toml.pre-mcp-repair.bak`. |

### Alcance priorizado — UI, acceso y administración

| # | Tarea | Estado | Notas |
|---|-------|--------|-------|
| 15 | Recordatorios y configuración guiada de WhatsApp | **DIFERIDO** (2026-11-09) | Se conserva para una fase posterior: recordatorio único a 24 horas, alta/estado guiado del canal y explicación de tarifas al dueño. La contabilidad de mensajes necesaria para métricas de administración se planificó en #16. |
| 16 | UI, acceso por invitación, recuperación y administración de plataforma | **EN CURSO** (2026-11-09) | Preflight local completo y branch `007-platform-admin-access-ui` pusheado (`8ab8d03`). T017/T033 requieren recorrido real desde la app. Pendientes: acceso autorizado a Vercel, aplicar migración Neon (esperar cambio a Sol y disponer de acceso seguro a Neon), desplegar y probar alta/admin. Límites confirmados: recuperación y login `/admin`, 5/correo y 20/IP por hora. |
| 18 | Corregir hallazgos de seguridad y consistencia de T035 | **HECHO** (2026-11-09) | R1–R6 corregidos y probados localmente tras autorización explícita del usuario. Límite `/admin` confirmado: 5 fallos/correo y 20/IP por hora. Nuevas migraciones `b7c2f3e4d590` y `c8e3d4f5a601`; ver `specs/007-platform-admin-access-ui/security-review.md`. Producción no modificada. |

**Recomendaciones diferidas para #15 (no son comportamiento actual):**

1. **Un solo recordatorio aproximadamente 24 horas antes de la cita.** Retirar el segundo aviso de 2 horas para evitar mensajes duplicados y reducir el costo potencial por cita. Hoy el código aún contempla 24h y 2h; el cron de producción sigue apagado (#2).
2. **Alta guiada de WhatsApp.** Explicar cómo registrar el número, configurar Meta, guardar Phone number ID y WABA ID y hacer una cita de prueba. Guardar IDs por sí solo no activa ni valida el canal.
3. **Estado verificable del canal en la UI.** Distinguir «faltan datos», «IDs guardados» y «conexión probada». El último estado debe depender de una prueba real, no solo de que haya IDs.
4. **Lista de preparación en el dashboard.** Guiar al dueño por servicios, horarios, configuración de WhatsApp y primera cita de prueba, e indicar cuándo se enviaría el único recordatorio.
5. **Identidad visual propia y consistente.** Resuelta en #16 con la marca Turno elegida por el usuario e integrada en acceso, navegación, favicon y correo.
6. **Etiquetas de métricas precisas.** Resueltas en T032 de #16 según el cálculo real del backend; no se presentan importes como dinero cobrado.
7. **Límites y costos visibles.** Explicar que el modelo actual soporta un número de WhatsApp por negocio y que un recordatorio con plantilla de utilidad puede generar un cargo por entrega de Meta. No prometer gratuidad de los 1.000 mensajes de servicio para recordatorios.

**Decisión operativa pendiente:** comprobar el canal y la cadencia antes de valorar la activación del cron externo (#2). Esta lista no autoriza activarlo.

**Alcance conversado para #16 (decisiones históricas; estado actual en `specs/007-platform-admin-access-ui/tasks.md` y `security-review.md`):**

1. **Cuenta de administrador de plataforma separada.** El dueño de la aplicación tendrá una identidad y permisos de plataforma para gestionar cuentas de negocio y consultar métricas globales. Crear esta cuenta mediante bootstrap/control administrativo; no ofrecer registro público de administradores.
2. **Invitación de dueños por correo.** El administrador invita, puede reenviar o revocar invitaciones y consulta su estado (pendiente, aceptada o vencida). El dueño acepta, establece su contraseña y continúa el alta guiada del negocio. La recuperación de contraseña también se hace por correo. Los plazos, límites y reglas del proyecto de referencia Pacelas son referencias de diseño, no requisitos ya acordados para SmartBooking.
3. **Separación de permisos y pantallas.** El panel de plataforma va separado del panel del negocio. Validar permisos en backend en cada operación, mantener a cada dueño limitado a sus propios datos y registrar acciones administrativas sensibles en una bitácora. Se recomienda MFA para la cuenta de plataforma.
4. **Gestión de cuentas.** Mostrar negocios invitados/activos/suspendidos y permitir administrar invitaciones y estado de cuenta. La regla actual limita a un negocio por dueño; mantenerla en la propuesta mientras no se decida explícitamente cambiarla.
5. **Métricas de plataforma.** Considerar conteos y tendencias agregadas de negocios y su estado de incorporación, clientes, citas y actividad de mensajes (enviados, entregados y fallidos), además de costo estimado/real cuando haya datos que lo sustenten. Etiquetar claramente estimaciones y periodos.
6. **Privacidad del panel.** Mostrar agregados sin exponer por defecto conversaciones, contenido de mensajes ni teléfonos completos de clientes. Si soporte requiere acceso detallado, limitarlo y dejar registro de auditoría.
7. **Costos de WhatsApp: brecha actual.** El sistema registra estados en logs, pero no mantiene un libro durable de mensajes asociados a negocio, tipo/categoría de plantilla, estado y tarifa aplicable. Por ello hoy no puede ofrecer gasto real confiable por negocio ni una métrica financiera global. Para calcularlo habrá que persistir esos datos y conciliarlos con la facturación de Meta; hasta entonces mostrarlo como no disponible, o como estimación explícita si se implementa una metodología.

**Alcance implementado de #16:** UI/flujo de acceso por invitación, aceptación, recuperación/restablecimiento de contraseña y panel `/admin` con bootstrap controlado de la primera cuenta. La referencia Pacelas solo aportó el patrón de correo; la especificación 007 fija plazos y límites. La entrega real de correo, el recorrido manual y los hallazgos de seguridad siguen abiertos.

**Reservado para después:** ajustes de recordatorios/WhatsApp, onboarding guiado del canal y explicación de costos al dueño (#15). La base de datos de mensajes y el estado estimado/real de gasto en `/admin` están planificados en #16; «gasto real» requiere conciliación con fuente de facturación.

### Deuda conocida (no bloquea)

- **#3 WhatsApp:** los nombres `META_WABA_TOKEN` y `META_APP_SECRET` ya figuran en
  Railway (2026-11-09), pero la lectura OAuth oculta sus valores y no confirma permisos
  ni suscripción de WABA. Aún falta una prueba real con `wa_route`. El POST devuelve
  HTTP 200 incluso si rechaza una firma inválida; ver auditoría del 2026-11-08.
  Revisar `docs/WHATSAPP_ONBOARDING.md` y `WHATSAPP_COSTING.md`.
- **500 transitorio en el primer request tras dormir Neon.** Con el contenedor frío y
  Neon suspendido, la primera query puede fallar con 500; el reintento funciona. Ocurre
  porque el pool de conexiones mantiene handles muertos. Mitigación pendiente de decidir
  (`pool_pre_ping=True` en `create_async_engine` sería lo natural).
- **Secretos expuestos el 2026-10-04:** `DATABASE_URL`, `JWT_SECRET_KEY`,
  `TELEGRAM_BOT_TOKEN`, `INTERNAL_CRON_TOKEN` y `META_VERIFY_TOKEN` quedaron en el
  transcript de la sesión. Rotación pendiente de decisión del usuario.

---

## Registro de cambios

<!-- Nuevas entradas arriba. Formato: fecha — título, luego qué/dónde/por qué/verificación -->

### 2026-11-09 — Branch publicado; migración de producción pendiente

**Qué:** se publicó el branch `007-platform-admin-access-ui` con el commit `8ab8d03`; la aplicación no se desplegó y la base Neon no se modificó. El preflight local pasó: frontend lint/build, Vitest 47/47, Playwright 4/4 y backend 440 aprobadas/79 omitidas por requerir `TEST_DATABASE_URL`. Se identificó que el MCP de Neon no está disponible y que la configuración local apunta a una base no productiva. El acceso al equipo Vercel aún requiere autorización.

**Dónde:** Git `origin/007-platform-admin-access-ui`; actualización de estado en este backlog. Servicios Railway/Vercel/Neon sin cambios en este paso.

**Por qué:** dejar el trabajo versionado y verificado, sin tocar producción antes de aplicar el esquema de base de datos de forma segura y con el usuario en Sol, como solicitó.

**Verificación:** `git push` terminó correctamente; pruebas y `git diff --check` aprobados. No se creó PR porque GitHub MCP/CLI no tiene permiso de escritura disponible. Próximo bloqueo operativo: acceso Neon seguro y autorización de equipo Vercel; no ejecutar `alembic upgrade` en producción antes de que el usuario cambie a Sol.

---

### 2026-11-09 — Preflight local antes de migrar Neon

**Qué:** se actualizó la lista de requisitos con decisiones ya acordadas, se repararon expectativas de tests obsoletas para el acceso por invitación y onboarding, y se redactaron correos/datos de acceso de demo en el histórico del worklog antes de publicarlo.

**Dónde:** `specs/007-platform-admin-access-ui/checklists/requirements.md`, `quickstart.md`, `plan.md`, `tasks.md`, `frontend/e2e/login.spec.ts`, `frontend/src/pages/Login.test.tsx`, `frontend/src/components/layouts/DashboardLayout.test.tsx`, `backend/api-backend/tests/test_business_mvp_limit.py`, `test_business_whatsapp_fields.py` y `docs/WORKLOG.md`.

**Por qué:** preparar un cambio publicable que refleje el comportamiento acordado, mantenga el worklog libre de credenciales históricas y verifique la UI antes del cambio de esquema de producción.

**Verificación:** frontend lint y build aprobados (0 errores, 20 avisos existentes); Vitest 47/47; Playwright E2E 4/4; backend-all 440 aprobadas y 79 omitidas por requerir PostgreSQL local. `alembic heads` muestra una sola cabeza `c8e3d4f5a601`; `git diff --check` aprobado. Las pruebas de DB ya se habían ejecutado en PostgreSQL local desechable según #18, pero en este preflight se omitieron. No se aplicó ninguna migración a Neon ni se desplegó la UI.

---

### 2026-11-09 — Configuración de correo transaccional en Railway

**Qué:** se creó en Resend una clave con permiso `sending_access` restringida a `rafenixcore.com`, se configuró en Railway junto con el remitente `SmartBooking <[correo omitido]>` y se envió un correo de prueba al destinatario indicado por el usuario. El secreto no se guardó en el repositorio ni en este worklog.

**Dónde:** dominio Resend `rafenixcore.com`; variables `RESEND_API_KEY` y `RESEND_FROM_EMAIL` del backend Railway `production`; procedimiento actualizado en `docs/ADMIN_OPERATIONS.md`; estado actualizado en `specs/007-platform-admin-access-ui/tasks.md`.

**Por qué:** habilitar invitaciones y recuperación de contraseña con el dominio corporativo verificado.

**Verificación:** Railway creó un redeploy que terminó `SUCCESS`; Resend confirmó el mensaje de prueba como `delivered`. El dominio ya estaba verificado y habilitado, por lo que no se cambió DNS. Cloudflare MCP no está disponible. La prueba fue directa desde Resend; falta recorrer invitación y recuperación generadas desde la aplicación y probar un enlace vencido. No se verificaron las migraciones de esta rama en Neon ni se declaró el despliegue completo.

---

### 2026-11-09 — T017/T033/T034: verificación de preparación de correo

**Qué:** revisión inicial de solo lectura: Resend presenta `rafenixcore.com` verificado y habilitado; Railway `production` aún no tenía `RESEND_API_KEY` ni `RESEND_FROM_EMAIL`. La configuración y prueba posterior se registran en la entrada del 2026-11-09. No hay herramienta MCP de Cloudflare conectada en esta sesión.

**Dónde:** consultas de solo lectura a Resend y Railway; `specs/007-platform-admin-access-ui/tasks.md`, `quickstart.md` y `docs/ADMIN_OPERATIONS.md` actualizados con el estado observado.

**Por qué:** separar la verificación del dominio de la entrega efectiva y no declarar completo el flujo antes de comprobar un correo real y el enlace vencido.

**Verificación:** se comprobaron el estado del dominio y los nombres de variables ausentes. En ese momento no se leyeron valores secretos ni se enviaron correos o cambiaron variables; ver el cierre posterior arriba.

---

### 2026-11-09 — #18: correcciones R1–R6 de seguridad y consistencia

**Qué:** se corrigió el alta para crear la membresía dueña en la misma transacción; el reenvío de invitaciones ahora devuelve conflicto de dominio ante otra pendiente o cuenta ya creada; los eventos de Meta se atribuyen con bloqueo transaccional por ID y orden estable en callbacks múltiples; logout revoca accesos de dueño además de refresh; se retiró el enlace de verificación de logs; y el login de `/admin` limita fallos a 5/correo y 20/IP por hora con contadores persistentes y hashes HMAC. El usuario confirmó el límite de administración.

**Dónde:** `backend/api-backend/app/api/businesses.py`, `auth.py`, `platform_auth.py`, `app/core/dependencies.py`, `app/models.py`, servicios `owner_invitations.py`, `message_ledger.py`, `email_service.py`, `platform_login_limits.py`, migraciones `b7c2f3e4d590` y `c8e3d4f5a601`, `scripts/bootstrap_admin.py` y pruebas enfocadas. La regla y operación se actualizaron en `specs/007-platform-admin-access-ui/` y `docs/ADMIN_OPERATIONS.md`.

**Por qué:** T035 detectó ausencia de relación de dueño, errores 500 en reenvío, doble atribución de gasto bajo carrera, accesos válidos tras logout, exposición de tokens en logs y límites administrativos no persistentes. El orden estable de locks evita el interbloqueo observado con callbacks inversos.

**Verificación:** las cinco pruebas de reproducción iniciales fallaron antes del cambio y pasaron después. La regresión enfocada tuvo 55 aprobadas y un fallo del test nuevo por conexión global ligada a otro ciclo de eventos; ajustado el test, los dos casos afectados aprobaron. Luego aprobaron 13 pruebas de mensajería, 5 de autenticación administrativa/logs, 8 de migración/bootstrap con 20 subpruebas y 2 de paridad ORM con 10 subpruebas. `alembic heads` mostró solo `c8e3d4f5a601`; `git diff --check` aprobó. Se usaron y eliminaron tres bases PostgreSQL locales desechables; el servidor local quedó detenido. No se modificó Neon ni producción. Restan T017/T033/T034 antes del despliegue.

---

### 2026-11-09 — T035: revisión final y ajustes de interfaz

**Qué:** se revisaron seguridad, privacidad, migraciones, atribución de mensajes y condiciones de despliegue. Se documentaron seis hallazgos R1–R6; R1–R5 requieren corrección y R6 una decisión antes de publicar. En la UI se aplicó Turno a invitación/recuperación, se añadió mostrar/ocultar contraseña y se ofreció acceso a `/admin` tras restablecerla.

**Dónde:** `specs/007-platform-admin-access-ui/security-review.md`, `spec.md`, `plan.md`, `tasks.md`, `ui-review.md` y `quickstart.md`; `frontend/src/components/ui/Input.tsx`, `frontend/src/pages/AcceptInvitation.tsx`, `ForgotPassword.tsx` y `ResetPassword.tsx`. El seguimiento de correcciones queda en backlog #18.

**Por qué:** la revisión detectó brechas de consistencia, concurrencia y revocación que impiden considerar lista la publicación; las pantallas de acceso necesitaban la misma identidad y claridad que el resto del producto.

**Verificación:** `alembic heads` mostró una sola revisión final (`a6e1c9b4d270`); `npm run build`, ESLint de los archivos modificados y `git diff --check` aprobaron. No se ejecutaron nuevas pruebas de backend ni se cambió producción. La revisión automática rechazó dos intentos de crear una base PostgreSQL local desechable para esas pruebas porque no había autorización explícita del usuario; el servidor local iniciado se detuvo. Las correcciones sensibles quedan pendientes de pruebas enfocadas.

---

### 2026-11-09 — T034: revisión de preparación de correo y dominio (pendiente)

**Qué:** Resend confirma `rafenixcore.com` verificado y con envío habilitado. La lectura de variables del servicio backend `production` no mostró `RESEND_API_KEY` ni `RESEND_FROM_EMAIL`; no se eligió una dirección remitente. No está disponible un MCP de Cloudflare en esta sesión. Se documentó el estado y la dependencia para entrega real.

**Dónde:** verificación de solo lectura mediante MCP de Resend/Railway; estado y pasos pendientes en `docs/ADMIN_OPERATIONS.md` y `specs/007-platform-admin-access-ui/tasks.md`.

**Por qué:** la plantilla en código no prueba que Resend acepte y entregue el mensaje; falta configurar un remitente y clave válidos en un entorno autorizado.

**Verificación:** estado del dominio y sus registros marcados verificados por Resend; las variables no aparecieron en el backend Railway consultado. No se intentó enviar un correo ni se modificó DNS o producción. T034 y T017 siguen pendientes hasta tener remitente/clave y realizar una entrega controlada.

---

### 2026-11-09 — T033: verificación frontend y revisión del recorrido (parcial)

**Qué:** se ejecutó `./scripts/verify-mvp.sh frontend`: lint completo y build Vite pasaron. La revisión de `quickstart.md` identificó que los recorridos de invitación y recuperación necesitan entrega real de correo, todavía pendiente en T017/T034.

**Dónde:** `scripts/verify-mvp.sh`, `specs/007-platform-admin-access-ui/quickstart.md` y salida de build/lint.

**Por qué:** validar el conjunto frontend y registrar las partes que requieren un entorno funcional antes de completar la aceptación integral.

**Verificación:** comando terminó con exit code 0; ESLint reportó 0 errores y 20 avisos existentes; build aprobado. No se ejecutaron pruebas automatizadas ni recorrido visual/manual. T033 permanece pendiente del walkthrough funcional cuando el correo esté configurado.

---

### 2026-11-09 — T032: precisión de métricas del dashboard del negocio

**Qué:** se cambió «Ingresos» por «Valor de citas», dejando explícito que el cálculo suma las tarifas configuradas de citas confirmadas/completadas y no equivale a pagos recibidos. La proporción semanal explica qué estados componen el numerador. «Nuevos clientes» ahora indica personas distintas con citas registradas en el mes. Los servicios populares muestran el periodo y el significado de conteos/valores.

**Dónde:** `frontend/src/pages/Dashboard.tsx`, contrastado con `backend/api-backend/app/api/dashboard.py` y los códigos de estado de citas.

**Por qué:** las fórmulas actuales no consultan cobros ni la fecha de creación del cliente; los rótulos deben describir los datos realmente calculados.

**Verificación:** build Vite y ESLint sobre `Dashboard.tsx` sin errores; revisión estática de filtros y fórmulas en backend; no se ejecutaron pruebas automatizadas.

---

### 2026-11-09 — T031: identidad Turno aplicada a UI y correo

**Qué:** se integró el símbolo aprobado Turno como favicon y marca en acceso, navegación del negocio, panel de plataforma y reserva pública. Se actualizaron título, descripción y color del navegador. Los correos de invitación, recuperación y verificación comparten el wordmark SmartBooking/Rafenixcore y los colores de marca; las plantillas no dependen de una imagen remota.

**Dónde:** `frontend/public/smartbooking-turno.svg`, `frontend/index.html`, `frontend/src/components/BrandMark.tsx`, componentes/páginas de login y navegación, y `backend/api-backend/app/services/email_service.py`. Se retiró `frontend/public/vite.svg`.

**Por qué:** aplicar la elección explícita del usuario y retirar la identidad de plantilla antes de comercializar el flujo de acceso.

**Verificación:** build Vite aprobado; ESLint completo terminó sin errores (20 avisos en otras partes del frontend); `git diff --check` aprobado. No se ejecutaron pruebas automatizadas ni envío real de correo. La compilación sintáctica Python no se verificó porque `python` no está instalado en el entorno.

---

### 2026-11-09 — T028: selección de propuesta Turno

**Qué:** el usuario eligió la propuesta 1, **Turno**, de la lámina de identidad. Se registró como selección aprobada para SmartBooking.

**Dónde:** `specs/007-platform-admin-access-ui/ui-review.md`, `tasks.md` y `plan.md`.

**Por qué:** determinar la identidad a integrar en favicon, interfaz y plantillas de correo.

**Verificación:** selección explícita del usuario en conversación el 2026-11-09.

---

### 2026-11-09 — T030: limpieza del flujo de acceso y alta

**Qué:** se simplificó el login, se quitó el timestamp de build y se mantuvo clara la invitación como vía de acceso. La primera cita ya no se presenta como prueba; la información del negocio y la integración de Telegram tienen etiquetas más precisas; se retiró la mención confusa a una «bandeja de prueba» en invitaciones. La reserva pública y pies de pantalla usan el nombre SmartBooking/Rafenixcore.

**Dónde:** `frontend/src/pages/Login.tsx`, `BusinessOnboarding.tsx`, `Dashboard.tsx`, `platform/AdminInvitations.tsx`, `components/layouts/PublicBookingLayout.tsx`.

**Por qué:** preparar una experiencia comercial clara que no exponga elementos de desarrollo ni dé por hecho que una integración ya está activa.

**Verificación:** el build Vite terminó correctamente. No se ejecutaron pruebas automatizadas por instrucción del desarrollador.

---

### 2026-11-09 — T029: consistencia de campos y tokens de UI

**Qué:** los campos de texto y selección comparten altura de 44 px, radio, borde, foco visible y jerarquía de etiqueta. Las etiquetas de Select quedan asociadas al control y los errores se anuncian; se incorporaron tokens semánticos provisionales para futuras decisiones de marca.

**Dónde:** `frontend/src/index.css`, `frontend/src/components/ui/Input.tsx`, `Select.tsx`, y uso de `Select` en `platform/AdminBusinesses.tsx` y `AdminInvitations.tsx`.

**Por qué:** reducir diferencias visuales y mejorar teclado y lector de pantalla en formularios de acceso y administración.

**Verificación:** build Vite aprobado y ESLint en los archivos modificados sin errores; cinco avisos preexistentes: `any` en alta y tres en `api.ts`, además de una dependencia faltante en el hook del dashboard. No se ejecutaron pruebas automatizadas por instrucción del desarrollador.

---

### 2026-11-09 — T028: propuestas de logo pendientes de elección

**Qué:** se preparó una lámina SVG con tres rutas visuales —Turno, Enlace y Ritmo—, cada una con variante clara y oscura y vista de símbolo reducido. La marca no se integró todavía: T031 depende de que el usuario elija una propuesta.

**Dónde:** `specs/007-platform-admin-access-ui/logo-proposals.svg` y `ui-review.md`.

**Por qué:** reemplazar los recursos genéricos con una identidad propia sin elegirla unilateralmente.

**Verificación:** revisión estructural de la lámina y descripción de conceptos; queda pendiente revisar la propuesta visual y elegir.

---

### 2026-11-09 — T027: inventario de pantallas y contenido comercial

**Qué:** se documentaron rutas de login, invitación, recuperación, alta, panel de negocio y administración; campos y textos sobrantes; favicon de Vite; inconsistencias de nombre, controles y marca; y mejoras recomendadas. Se anotó que `/test-ui` solo existe en desarrollo y que el inventario fue estático.

**Dónde:** `specs/007-platform-admin-access-ui/ui-review.md`.

**Por qué:** establecer el estado real de la UI antes de reemplazar contenido y activos de plantilla.

**Verificación:** cotejo de rutas, componentes, campos y recursos mediante lectura estática; sin capturas ni inspección de navegador.

---

### 2026-11-09 — T026: pantalla administrativa de métricas

**Qué:** se añadió `/admin/metrics` con selección inclusiva de periodo UTC (hasta 366 días), resumen global, desglose de estados, métricas paginadas por negocio y costos como conciliados, estimados o no disponibles. La pantalla muestra fuente, versiones de tarifa, cobertura, fórmulas y estados vacíos. En móvil, el detalle por negocio se presenta en tarjetas. El resumen `/admin` enlaza a esta pantalla.

**Dónde:** `frontend/src/pages/platform/Metrics.tsx`, `AdminLayout.tsx`, `AdminOverview.tsx`, `frontend/src/App.tsx`, `frontend/src/services/api.ts`, `frontend/src/types/platform.ts` y contrato de UI.

**Por qué:** US4 requiere que el administrador pueda interpretar actividad y costos sin confundir estimaciones con gasto real ni ocultar falta de cobertura.

**Verificación:** `npm run build` aprobado y ESLint sobre los archivos modificados sin errores (3 avisos `any` preexistentes en `api.ts`). `npx tsc --noEmit` continúa fallando en `TestUI.tsx` y `authStore.test.ts` por errores ajenos a los archivos modificados. No se ejecutaron pruebas automatizadas por instrucción del desarrollador.

---

### 2026-11-09 — T025: costos estimados, conciliación y métricas de mensajes

**Qué:** se implementó estimación solo con tarifa versionada, fuente, categoría/país y mensaje entregado; sin estos datos el importe queda no disponible. La conciliación exige evidencia y cobertura completa del periodo exacto; una conciliación parcial no se muestra como gasto global real. La API administrativa devuelve estados canónicos de WhatsApp, importe decimal como texto, fuente, versiones y cobertura por negocio/global. No se precargaron tarifas de Meta ni se creó importador de facturas. El campo país de los estados recibidos puede faltar, por lo que no se infiere el costo.

**Dónde:** `backend/api-backend/app/services/message_costs.py`, `app/api/platform_metrics.py`, pruebas `tests/test_message_costs.py` y `tests/test_platform_metrics.py`; contrato y modelo en `specs/007-platform-admin-access-ui/`.

**Por qué:** US4 y FR-013 requieren distinguir evidencia de entrega, estimación y gasto conciliado, sin inventar importes y con fuentes visibles para el administrador.

**Verificación:** seis pruebas del servicio partieron de error de importación; dos pruebas HTTP fallaron antes de integrar mensajería. Después aprobaron 69 pruebas de métricas/costos/ledger y regresiones de webhook, recordatorios y cliente WhatsApp en PostgreSQL local desechable. No se ejecutaron cambios externos ni despliegue.

---

### 2026-11-09 — T024: eventos y estados de WhatsApp persistentes

**Qué:** se guardan IDs salientes aceptados por Meta desde bot y recordatorios, y cada estado firmado recibido por webhook. Una fila por mensaje conserva el estado más fuerte sin retroceder; los estados individuales quedan como evidencia idempotente. Los números de Meta sin negocio o contradictorios con un mensaje ya atribuido no se asignan. No se guardan destinatarios, textos ni conversaciones. Si falla la bitácora después de un recordatorio aceptado, el flag de envío se conserva para evitar repetirlo; si falla la escritura de un estado, el webhook responde 503 para permitir reintento.

**Dónde:** `backend/api-backend/app/services/message_ledger.py`, `main.py`, `app/services/background_tasks.py`, pruebas `tests/test_message_ledger.py` y ajuste del fixture en `tests/test_webhook_endpoints_ci.py`.

**Por qué:** FR-013 y US4 requieren contabilidad por negocio basada en eventos persistidos, sin duplicar webhooks ni atribuir mensajes a otra cuenta.

**Verificación:** 10 pruebas enfocadas T024 aprobaron en PostgreSQL local desechable; el caso de conflicto entre negocios falló primero y luego aprobó. También aprobaron 49 pruebas existentes de recordatorios, webhook y cliente WhatsApp. Sin cambios externos ni despliegue.

### 2026-11-09 — T023: métricas de citas y clientes para la plataforma

**Qué:** se implementó un resumen global y filas paginadas por negocio para citas por estado y clientes distintos con registros de cita. Cada respuesta incluye periodo UTC, fórmula y tabla fuente. Se validan límites de fecha/página y se excluyen datos personales de clientes. La fórmula técnica cuenta registros de todos los estados, incluidas canceladas; no se etiqueta como «clientes nuevos».

**Dónde:** `backend/api-backend/app/api/platform_metrics.py`, montaje en `main.py`, pruebas `tests/test_platform_metrics.py` y contrato de `specs/007-platform-admin-access-ui/`.

**Por qué:** FR-012 exige métricas con periodo, definición y fuente, y US4 requiere cifras comparables con filas reales sin mezclar negocios.

**Verificación:** tras comprobar tres fallos esperados por ruta inexistente, las tres pruebas T022 revisadas aprobaron en PostgreSQL local desechable; cubren autorización, dos negocios, clientes repetidos, límite exacto del periodo, paginación, fecha inválida y privacidad. Sin cambios externos ni de producción.

### 2026-11-09 — T022: contrato de métricas administrativas preparado

**Qué:** se añadieron pruebas HTTP de autorización, conteos globales y por negocio, periodo semiabierto `[from, to)`, coincidencia con filas sembradas y paginación. Se documentó la propuesta de respuesta y se dejaron explícitamente pendientes de decisión el tratamiento de citas canceladas para contar clientes, los estados desconocidos y las citas sin cliente.

**Dónde:** `backend/api-backend/tests/test_platform_metrics.py`, `specs/007-platform-admin-access-ui/contracts/access-admin-ui.md` y `tasks.md`.

**Por qué:** T022 fija un contrato comprobable para citas/clientes antes de T023; las definiciones que no constan en la especificación no deben transformarse en reglas supuestas.

**Verificación:** las tres pruebas corrieron en PostgreSQL local desechable y fallaron como se esperaba porque `/api/platform/metrics` todavía responde 404; T023 implementará la ruta. Las pruebas sembraron dos negocios, varias citas y clientes repetidos para comparar los agregados con filas conocidas. Se requiere revisión Sol de este contrato antes de T023. Sin cambios externos ni de producción.

### 2026-11-09 — T021: panel administrativo `/admin`

**Qué:** se completaron acceso administrativo separado, sesión/renovación, shell adaptativo, resumen con conteos respaldados, listado y detalle de negocios, acciones de invitación y bitácora. El resumen deja claro que los costos de mensajes aún no están disponibles y que no muestra estimaciones como gasto real.

**Dónde:** `frontend/src/pages/platform/`, `frontend/src/store/platformAuthStore.ts`, `frontend/src/types/platform.ts`, cliente separado en `frontend/src/services/api.ts`, rutas en `frontend/src/App.tsx`; GET administrativo de detalle en `backend/api-backend/app/api/platform_businesses.py`, pruebas frontend/backend y `frontend/e2e/admin.spec.ts`.

**Por qué:** US3 requiere que el propietario gestione negocios e invitaciones en `/admin`, sin compartir sesión ni permisos con el panel del dueño y sin inventar métricas o costos.

**Verificación:** 5 pruebas de componentes pasaron; `npm run build` pasó; Playwright comprobó navegación en escritorio y móvil, estado vacío y ausencia de desbordamiento horizontal (2 pasaron). ESLint reportó cero errores y tres avisos `any` ya presentes en `api.ts`. Las 5 pruebas HTTP de negocios/detalle habían pasado en PostgreSQL local desechable. No se desplegó ni se modificó producción.

### 2026-11-09 — T020: bitácora administrativa consultable

**Qué:** se centralizó la creación de eventos con actor, acción, entidad y resultado, sin aceptar cuerpos de solicitud ni detalles personales. El listado paginado de auditoría exige una sesión administrativa vigente y omite el campo interno `details`; las invitaciones existentes usan el mismo servicio. Suspender/reactivar registra `success`, repetir un estado `unchanged` y usar un ID inexistente `not_found`.

**Dónde:** `backend/api-backend/app/services/admin_audit.py`, `app/api/platform_audit.py`, `app/services/owner_invitations.py`, montaje en `main.py`, pruebas `tests/test_platform_businesses.py`, contrato en `specs/007-platform-admin-access-ui/contracts/access-admin-ui.md` y runbook `docs/ADMIN_OPERATIONS.md`.

**Por qué:** FR-011 exige rastrear acciones sensibles y restringir la lectura de la bitácora a la plataforma, sin exponer secretos ni datos innecesarios.

**Verificación:** las 5 pruebas de gestión/auditoría y las 19 de invitaciones aprobaron en PostgreSQL 16 local desechable. `compileall` y `git diff --check` aprobaron. No se tocó Neon ni producción.

### 2026-11-09 — T019: listado y suspensión/reactivación de negocios

**Qué:** se añadieron listado global paginado con filtros de estado y búsqueda por nombre/correo del dueño, y acciones para suspender/reactivar `Business.is_active` bajo bloqueo de fila. Las rutas exigen administrador; el dueño conserva identidad pero pierde acceso operativo al negocio suspendido incluso con una sesión anterior. El listado devuelve solo los campos necesarios para la gestión, sin teléfono ni clientes.

**Dónde:** `backend/api-backend/app/api/platform_businesses.py`, montaje en `main.py`, `tests/test_platform_businesses.py`, contrato y runbook de administración.

**Por qué:** FR-009/010 y US3 requieren gestionar cuentas de negocio sin borrar historial, mantener aislamiento de permisos y permitir entender el estado de incorporación.

**Verificación:** 5 pruebas HTTP aprobaron en PostgreSQL 16 local desechable: acceso público/dueño denegado, vista global, paginación, filtros, bloqueo de operación, reactivación, auditoría, reintento idempotente e ID ausente. `compileall` y `git diff --check` aprobaron. Sin despliegue ni cambios externos.

### 2026-11-09 — T018: pruebas de contrato de administración de negocios (revisadas)

**Qué:** se escribieron pruebas HTTP para rechazar acceso público y de dueño al listado/acciones de plataforma, y para verificar suspensión, bloqueo operativo con sesión previa, reactivación, conservación del negocio y auditoría atribuida al administrador. Solo se añadieron pruebas; no se implementó ni cambió el estado de ninguna cuenta.

**Dónde:** `backend/api-backend/tests/test_platform_businesses.py`; asignación y estado en `specs/007-platform-admin-access-ui/tasks.md` y `plan.md`.

**Por qué:** fijar los casos de autorización y trazabilidad antes de T019, cuya implementación requiere revisión Sol de estas expectativas.

**Verificación:** Sol amplió los casos de listado, filtros, privacidad mínima, reintento e ID inexistente. Inició PostgreSQL 16 local desechable y confirmó 3 fallos esperados por rutas ausentes; después de T019–T020 pasaron 5 pruebas. El contrato quedó revisado antes de implementar las rutas. Sin cambios en producción.

### 2026-11-09 — T017: pantallas y plantilla de recuperación (entrega pendiente)

**Qué:** se añadieron solicitud y cambio de contraseña con respuestas neutrales, manejo de límite 429, enlace de recuperación desde login, rutas públicas y cliente API. La pantalla retira el token del fragmento de URL antes de enviarlo únicamente en el cuerpo POST; ofrece solicitar otro enlace si es inválido/vencido. La plantilla Resend ahora tiene versiones HTML responsive y texto, indica vigencia de una hora y uso único, y escapa el enlace/categoría.

**Dónde:** `frontend/src/pages/ForgotPassword.tsx`, `ResetPassword.tsx`, `PasswordRecovery.test.tsx`, `Login.tsx`, `App.tsx`, `services/api.ts`; `backend/api-backend/app/services/email_service.py` y `tests/test_password_reset_email.py`. Estado en `specs/007-platform-admin-access-ui/`.

**Por qué:** completar el flujo de recuperación confirmado en T016 y hacerlo entendible sin filtrar si existe la cuenta.

**Verificación:** pasaron 7 pruebas de frontend enfocadas, `npm run build`, ESLint (cero errores; avisos existentes en otros archivos), prueba aislada de plantilla Resend simulada, `compileall` y `git diff --check`. La comprobación TypeScript completa sigue reportando errores preexistentes en `TestUI.tsx` y `authStore.test.ts`. Las 11 pruebas de contrato de T016 se omitieron por faltar `TEST_DATABASE_URL`. Se consultó Resend en modo lectura y `rafenixcore.com` figura verificado con envío habilitado; no se envió un correo real: la app no tiene remitente/clave de entorno configurados y no se indicó destinatario de prueba. Sin cambios en DNS, Resend, Railway, Neon ni producción.

### 2026-11-09 — T016: recuperación de contraseña para dueño y plataforma

**Qué:** se añadieron las rutas públicas de solicitud neutral y confirmación de contraseña. El enlace dura una hora y es de un solo uso; los límites confirmados son 5 solicitudes por correo y 20 por IP cada hora. Los contadores se guardan en PostgreSQL con HMAC de correo/IP, para que sobrevivan reinicios y no conserven esos datos en claro. El correo usa Resend con token en el fragmento de la URL; la entrega se programa después de responder y los errores del proveedor se registran sin correo, token ni enlace. Confirmar el reset cambia el hash de contraseña, consume todos los enlaces pendientes de la cuenta y revoca refresh tokens o sesiones de plataforma. Los JWT de dueño anteriores se rechazan por fecha de emisión; login y refresh se serializan con el reset para evitar reemitir sesiones con la contraseña antigua.

**Dónde:** `backend/api-backend/app/api/password_reset.py`, `main.py`, `app/services/password_reset_service.py`, `email_service.py`, `refresh_token_service.py`, `app/core/security.py`, `dependencies.py`, `app/api/auth.py`, `platform_auth.py`, modelo y migración `a6e1c9b4d270_password_reset_attempts.py`, `scripts/bootstrap_admin.py`; pruebas de recuperación, migración, modelo y compatibilidad. Se actualizaron `specs/007-platform-admin-access-ui/`, `.env.example` y `docs/ADMIN_OPERATIONS.md`.

**Por qué:** FR-007/008 y la decisión del usuario del 2026-11-09 exigen un enlace de una hora, respuesta sin enumerar cuentas, límites reales de 5/20 y cierre de sesiones anteriores. El contador en memoria perdía la ventana al reiniciar el proceso, por lo que se reemplazó por una tabla persistente. Se actualizó el bootstrap porque exige exactamente la revisión Alembic vigente.

**Verificación:** las nueve pruebas revisadas de T015 fallaron primero con 404; después pasaron 11 pruebas enfocadas de recuperación, incluidos fallo de proveedor simulado, límites exactos, token vencido/usado, dos confirmaciones concurrentes, enlaces pendientes, JWT legado y sesiones. Pasaron 8 pruebas de aislamiento, 19 de invitación, 2 del flujo de plataforma, 11 unitarias de auth/tokens, 2 de paridad ORM (9 subpruebas), 1 de upgrade/downgrade (18 subpruebas) y 7 de bootstrap en PostgreSQL local desechable. Una regresión de refresh en cuenta suspendida apareció al serializar sesiones y se corrigió antes de cerrar. No se envió correo real, no se tocaron variables externas ni producción. T017 completará plantilla/pantallas y prueba de entrega real.

### 2026-11-09 — T015: pruebas de contrato para recuperar contraseña

**Qué:** se añadieron seis pruebas HTTP y de persistencia para respuesta neutral ante cuenta existente/desconocida (dueño y administrador), límite de solicitudes, token vencido, uso único y revocación de sesiones de ambos tipos. La prueba de expiración altera directamente la fecha del token, sin fijar la duración comercial del enlace.

**Dónde:** `backend/api-backend/tests/test_password_reset.py`; estado de tareas en `specs/007-platform-admin-access-ui/tasks.md`.

**Por qué:** T016 implementará recuperación para dueños y administradores; estas pruebas fijan el contrato de privacidad y evitan reutilizar tokens o conservar sesiones después de cambiar la contraseña.

**Verificación:** ejecutada contra PostgreSQL 16 local desechable y migrada a `head`; las seis fallaron como se esperaba porque `POST /api/auth/password-reset/request` y `/confirm` todavía no existen (404). La suite no envía correo. No se modificó código de autenticación ni producción. La política exacta de frecuencia queda representada por una prueba que espera throttling antes de 100 solicitudes; el contrato aún no fija umbral operativo.

### 2026-11-09 — T014: cierre del registro público de dueños

**Qué:** se eliminó `POST /api/auth/register` y el formulario de alta pública. La ruta antigua `/register` redirige a `/login`, donde ya no se ofrece registrarse ni se publican credenciales demo. Se retiraron el método y tipos cliente exclusivos del registro; la verificación de correo legada permanece para cuentas anteriores. Las altas nuevas siguen el flujo de invitación del administrador.

**Dónde:** `backend/api-backend/app/api/auth.py`, `app/api/owners.py`, `app/schemas/__init__.py`, `tests/test_owner_invitations.py`; `frontend/src/App.tsx`, `pages/Login.tsx`, `pages/Register.tsx` (eliminado), `pages/Login.test.tsx`, `services/api.ts`, `types/index.ts`; estado del plan en `specs/007-platform-admin-access-ui/`.

**Por qué:** FR-001 exige que solo una invitación administrativa cree dueños; el endpoint anterior permitía eludir esa regla y el login anunciaba un registro público con datos de demostración.

**Verificación:** la prueba nueva falló antes del cambio porque el registro devolvía 200; después `POST /api/auth/register` devolvió 404 sin crear cuenta y una cuenta existente inició sesión. Pasaron 19 pruebas de invitación/acceso en PostgreSQL local desechable y 39 pruebas frontend; el build Vite pasó. ESLint de archivos afectados terminó con 0 errores y 4 advertencias preexistentes en `api.ts`/`types/index.ts`; `git diff --check` pasó. Una ejecución frontend concurrente con el build tuvo un fallo temporal en una prueba de onboarding; su ejecución aislada y la repetición de la suite completa pasaron. No se desplegó ni se modificó producción.

### 2026-11-09 — T011–T013: envío de invitaciones, aceptación y alta reanudable

**Qué:** T011 integra correo transaccional de invitación por API HTTP de Resend, con versión HTML/texto, errores visibles en `delivery_status`, estado `sent` solo cuando Resend acepta la petición y sin registrar token, URL ni correo. El enlace usa fragmento `#token=...`; la SPA lo limpia de la barra y envía el token a `POST /api/auth/invitations/preview` en el cuerpo, para evitar incluirlo en la ruta HTTP. T012 añade la pantalla que muestra el correo fijado, solicita contraseña y confirmación, maneja enlace inválido y evita envíos duplicados. T013 detecta negocios incompletos, permite reanudar/guardar el perfil, oculta la navegación operativa hasta completar y deja disponible cerrar sesión. `BusinessOut` ahora expone `onboarding_completed_at` para decidir el estado de la pantalla.

**Dónde:** `backend/api-backend/app/services/email_service.py`, `app/config.py`, `.env.example`, `app/api/platform_invitations.py`, `app/api/auth.py`, `app/services/owner_invitations.py`, `app/schemas/__init__.py`; `frontend/src/pages/AcceptInvitation.tsx`, `BusinessOnboarding.tsx`, `DashboardLayout.tsx`, `App.tsx`, `services/api.ts`, `types/index.ts` y `components/ui/Input.tsx`. Contrato, recorrido y runbook actualizados; pruebas backend/frontend añadidas.

**Por qué:** completar la invitación acordada con correo fijado y aceptación con contraseña, exponer los fallos del proveedor para que no parezcan correos enviados, y cumplir el requisito de bloquear el panel hasta terminar el alta incluso para negocios parciales preexistentes. El estado `sent` no afirma entrega a la bandeja.

**Verificación:** Resend confirmó en consulta de solo lectura que `rafenixcore.com` está verificado y habilitado para envío. No se eligió ni configuró una dirección remitente y no se envió correo real. Pasaron 18 pruebas de invitación, 29 pruebas combinadas de invitación/autenticación y 8 pruebas de aislamiento ejecutadas por separado; el conjunto frontend completo pasó 38 pruebas. El build Vite y `compileall` pasaron; Playwright mostró la pantalla en 390×844 y 1440×900, token fuera de la URL al terminar la carga. `git diff --check` pasó. Al combinar también la suite de aislamiento con otras suites en el mismo proceso, una prueba falló por reutilización de conexión async entre event loops; aislada pasó. No se tocaron DNS, variables de Railway, Neon ni producción.

### 2026-11-09 — T010: servicio y rutas de invitación de dueños

**Qué:** se implementaron creación/listado paginado, reenvío, revocación y aceptación de invitaciones. La vigencia confirmada por el usuario es 72 horas; reenvío rota el token y reinicia el plazo. El token se guarda como hash y nunca se devuelve por API. La aceptación fija el correo invitado, crea un dueño activo/verificado sin nombre y consume el token atómicamente; el login acepta ese perfil incompleto para que pueda completar el alta. Se auditan creación, reenvío y revocación. El listado marca invitaciones vencidas y permite filtrarlas.

**Dónde:** `backend/api-backend/app/services/owner_invitations.py`, `app/api/platform_invitations.py`, ruta pública en `app/api/auth.py`, montaje en `main.py`, esquemas en `app/schemas/__init__.py`, respuesta de dueño incompleto en el mismo esquema y pruebas en `tests/test_owner_invitations.py`. Contrato de acceso y runbook actualizados en `specs/007-platform-admin-access-ui/` y `docs/ADMIN_OPERATIONS.md`.

**Por qué:** FR-003/004/007 y US1 requieren invitar por correo fijado, consumir un enlace una sola vez, invalidarlo al reenviar/revocar y evitar dobles altas concurrentes. La revisión Sol de T009 confirmó la interfaz de servicio usada por las pruebas. T011 aún debe conectar la entrega por Resend; hasta entonces las rutas dejan `delivery_status=pending` y no son un flujo de invitación utilizable para negocio.

**Verificación:** el nuevo caso de reemitir una invitación cuyo estado seguía `pending` pero cuyo plazo ya expiró falló inicialmente; tras corregir la transición a `expired`, pasaron 12 pruebas de invitación y 23 combinadas con autenticación en PostgreSQL 16 local desechable. Cubren hash, vigencia, reenvío, revocación, duplicados, aceptación única/concurrente, separación de roles, auditoría y login posterior. No se envió correo, no se creó cuenta en Neon y no se desplegó.

### 2026-11-09 — T009: pruebas del servicio de invitaciones

**Qué:** se añadieron ocho pruebas PostgreSQL para normalización de correo, hash y unicidad del token, rechazo de correo duplicado o ya registrado, reenvío que invalida el enlace anterior, revocación y reemisión, vencimiento, aceptación de un solo uso y carrera de dos aceptaciones simultáneas.

**Dónde:** `backend/api-backend/tests/test_owner_invitations.py` y estado/dependencias en `specs/007-platform-admin-access-ui/tasks.md`, `plan.md` y `spec.md`. No se creó el servicio ni rutas de invitación.

**Por qué:** fijar el contrato de seguridad y concurrencia antes de T010; conforme a la asignación, Sol debe revisar la interfaz del servicio expresada en los tests antes de implementarla.

**Verificación:** las ocho pruebas fallan de forma esperada por falta de `app.services.owner_invitations`. Se ejecutaron contra PostgreSQL 16 local desechable; no se modificó producción. Los tests asumen las funciones `create_invitation`, `resend_invitation`, `revoke_invitation`, `accept_invitation` y la excepción `InvitationError`; revisar ese contrato antes de T010.

### 2026-11-09 — T008: permisos operativos por dueño y negocio

**Qué:** se exige dueño activo en cada solicitud, inicio y renovación de sesión; el refresh de un dueño suspendido se consume sin emitir otro. Las rutas de servicios, clientes, citas, agenda y métricas comprueban propiedad por `business_id`, negocio activo y alta completada. Se protegieron las rutas de activación Telegram. El alta de negocio valida nombre/teléfono, marca el alta completa y serializa creaciones simultáneas; el dueño no puede cambiar `is_active` ni reactivar un negocio suspendido. Las rutas de lectura del negocio permiten reanudar un alta incompleta, pero rechazan un negocio suspendido.

**Dónde:** guards en `backend/api-backend/app/core/dependencies.py`; rutas en `app/api/{auth,businesses,services,customers,appointments,schedules,dashboard}.py`; renovación en `app/services/refresh_token_service.py`; pruebas en `tests/test_tenant_access_guards.py` y fixture existente en `tests/test_business_whatsapp_fields.py`; estado en `specs/007-platform-admin-access-ui/` y runbook en `docs/ADMIN_OPERATIONS.md`.

**Por qué:** FR-005 y FR-009 exigen impedir acceso operativo antes del alta, tras suspensión y entre negocios, incluso con JWT emitidos antes del cambio. Las rutas REST de creación de clientes/citas y lectura de servicios estaban abiertas sin autenticación; ahora exigen dueño del negocio. Los bots de WhatsApp y Telegram usan servicios internos, no esas rutas REST.

**Verificación:** seis pruebas HTTP iniciales fallaron por las brechas esperadas; otra prueba detectó renovación residual de refresh suspendido. Tras corregirlo, 30 pruebas enfocadas pasaron en PostgreSQL 16 local desechable; `./scripts/verify-mvp.sh backend-api` aprobó 39 y `backend-all` aprobó 435 (19 omitidas porque esa ejecución no recibió `TEST_DATABASE_URL`). Compilación Python y `git diff --check` sin errores. No se modificaron servicios externos ni producción. **Compatibilidad:** clientes externos que usaran las rutas REST antes públicas necesitarán autenticación de dueño; verificar consumidores externos antes de despliegue.

### 2026-11-09 — T007: bootstrap controlado del primer administrador

**Qué:** se añadió un comando de terminal que crea la primera cuenta de plataforma, pide una contraseña oculta y exige la revisión Alembic esperada. Repetirlo con el mismo correo no duplica ni cambia la contraseña; otro correo o una cuenta inactiva se rechazan. Un bloqueo transaccional de PostgreSQL serializa intentos simultáneos.

**Dónde:** `backend/api-backend/scripts/bootstrap_admin.py`, pruebas en `backend/api-backend/tests/test_bootstrap_admin.py`, procedimiento en `docs/ADMIN_OPERATIONS.md`, estado en `specs/007-platform-admin-access-ui/tasks.md` y `plan.md`. Sin cambios en servicios externos.

**Por qué:** FR-002 requiere crear la identidad inicial por un procedimiento controlado y sin registro público; la repetición o dos ejecuciones simultáneas no deben producir administradores adicionales ni revelar secretos.

**Verificación:** la prueba de CLI falló primero por ausencia del comando. Tras implementarlo, 7 pruebas enfocadas pasaron en una base PostgreSQL 16 local desechable: idempotencia, contraseña preservada, rechazo de un segundo correo, inactividad, concurrencia, límites de contraseña y salida sin secreto. No se creó cuenta en Neon ni se aplicó la migración a producción. T008 permanece pendiente.

### 2026-11-09 — Revisada asignación de tareas entre Luna y Sol

**Qué:** T009, T015 y T018 (pruebas previas), T022 (definiciones y pruebas) y T013 (solo UI, después del bloqueo de backend T008) pasaron de high a medium/Luna. Las implementaciones de invitación, recuperación, permisos, métricas con acceso global, mensajería, costos y bootstrap siguen en high/Sol. Sol revisará las pruebas de Luna antes de T010/T016/T019/T023 y hará una revisión integral de su trabajo en T035, como pidió el usuario.

**Dónde:** clasificación y dependencias en `specs/007-platform-admin-access-ui/tasks.md`, nota de ejecución en `plan.md` y backlog #16. Sin cambios de código ni infraestructura.

**Por qué:** aprovechar Luna en trabajo preparatorio y de interfaz, manteniendo decisiones de seguridad, aislamiento, concurrencia y cálculo de costos bajo razonamiento alto antes de entrar en producción.

**Verificación:** revisión de las 35 descripciones contra la constitución y las dependencias del plan: 15 tareas high/Sol y 20 low/medium/Luna en total; tras T001–T006, 11 high/Sol y 18 low/medium/Luna pendientes. No se ejecutaron pruebas porque solo cambió la planificación.

### 2026-11-09 — T006: identidad y sesiones revocables de plataforma

**Qué:** se añadieron rutas backend de login, renovación, cierre de sesión y consulta de identidad administrativa. El JWT de plataforma identifica su tipo y la sesión persistida; el refresh opaco se guarda solo como hash, rota con bloqueo transaccional y deja de servir tras cierre, vencimiento o desactivación del administrador. El guard de dueño rechaza tokens de plataforma y los tokens nuevos de dueño indican su tipo. Los tokens anteriores de dueño sin `principal_type` siguen siendo válidos hasta vencer.

**Dónde:** `backend/api-backend/app/api/platform_auth.py`, `app/core/dependencies.py`, `app/api/auth.py`, `main.py`, pruebas `tests/test_platform_auth.py` y `tests/test_platform_auth_flow.py`, además de `docs/ADMIN_OPERATIONS.md` y estado de Spec Kit. Sin cambios en Railway, Neon o frontend.

**Por qué:** separar la identidad global del administrador de la identidad de dueño y poder cortar acceso administrativo al revocar su sesión.

**Verificación:** dos pruebas HTTP nuevas fallaron inicialmente con 404. Tras implementar, 11 pruebas enfocadas pasaron: frontera entre identidades, compatibilidad del dueño, login, rotación y replay del refresh, expiración de sesión y revocación mediante logout. Las pruebas HTTP usaron una base PostgreSQL 16 local desechable; no se consultó ni migró producción. El bootstrap inicial T007 y los permisos finales T008 siguen pendientes.

### 2026-11-09 — T005: pruebas de frontera entre dueño y administrador

**Qué:** se añadieron pruebas de autenticación para impedir que un JWT de plataforma entre en rutas de dueño o que uno de dueño entre en rutas administrativas, aun cuando compartan correo e ID. También cubren continuidad de tokens anteriores de dueño, sesión administrativa activa/revocada/vencida, administrador inactivo y rechazo de refresh como access. El contrato define `principal_type` y `sid` para la implementación T006.

**Dónde:** `backend/api-backend/tests/test_platform_auth.py`, `specs/007-platform-admin-access-ui/contracts/access-admin-ui.md`, estado de `tasks.md` y `plan.md`. No se modificó código de producto ni infraestructura.

**Por qué:** la dependencia actual de dueño solo comprueba el correo del JWT y rechaza explícitamente `token_kind=refresh`; un token de plataforma con el mismo correo sería aceptado. Las pruebas fijan la frontera antes de modificar autenticación.

**Verificación:** ejecución enfocada de `pytest` con 8 fallos esperados por el guard de plataforma ausente y la aceptación indebida de un token de administrador en `get_current_owner`; 1 prueba pasó para el token anterior de dueño. T006 debe poner la suite en verde. El almacén de cuentas de la prueba es simulado, por lo que la consulta real a PostgreSQL y el ciclo de sesiones deben verificarse en T006. No se tocaron servicios externos.

### 2026-11-09 — T004: runbook de operación del acceso de plataforma

**Qué:** se documentó la preparación de entorno, comprobación de revisión Alembic, aplicación futura de la migración, requisitos para el bootstrap inicial, verificación posterior y recuperación. Se aclaró que el bootstrap y el acceso todavía no están implementados y que el downgrade protegido deja de ser viable después de crear datos de plataforma.

**Dónde:** `docs/ADMIN_OPERATIONS.md`, estado de T004 en `specs/007-platform-admin-access-ui/tasks.md` y `plan.md`. No se ejecutó ningún comando contra Railway, Neon o producción.

**Por qué:** contar con pasos operativos concretos y con límites explícitos antes de habilitar identidades administrativas o tocar datos reales.

**Verificación:** revisión del runbook contra la migración `7c9d2e4f6a10`, el modelo de datos y el estado de tareas. Confirmado que no contiene secretos y que distingue operaciones futuras de la implementación actual. No se ejecutaron pruebas porque el cambio es documental.

### 2026-11-09 — T003: modelos ORM para acceso y administración de plataforma

**Qué:** se añadieron ocho modelos ORM para administradores y sesiones, membresías, invitaciones, recuperación, auditoría y eventos/costos de mensajes. `Owner.name` ahora admite `NULL`, `Owner.is_active` y `Business.onboarding_completed_at` reflejan la migración. Los modelos incluyen índices parciales, restricciones únicas y relaciones, sin habilitar aún rutas ni funciones de producto.

**Dónde:** `backend/api-backend/app/models.py`, `backend/api-backend/tests/test_platform_models.py` y estado de `specs/007-platform-admin-access-ui/{tasks.md,plan.md,data-model.md}`. Sin cambios en infraestructura, Neon o producción.

**Por qué:** mantener el ORM alineado con la migración T002 y preparar las tareas de identidad e invitación sin discrepancias de esquema.

**Verificación:** prueba roja inicial por modelos y campos ausentes; después, 2 pruebas aprobadas y 8 subpruebas de paridad de tablas, columnas, índices y restricciones únicas en PostgreSQL 16 local desechable. Una prueba con dos transacciones concurrentes confirmó que no se aceptan dos invitaciones pendientes del mismo correo con distinta capitalización. `configure_mappers()`, compilación Python y `git diff --check` pasaron. Ruff no está instalado en el entorno local, así que no se ejecutó. La base local de prueba se eliminó al terminar.

### 2026-11-09 — T002: migración de esquema para acceso y administración de plataforma

**Qué:** se añadió una migración Alembic que prepara identidad/sesiones del administrador, invitaciones, recuperaciones, membresías de negocio, auditoría y eventos/costos de mensajes. Se añadió `Owner.is_active`, se hizo `Owner.name` nullable para que el invitado introduzca solo la contraseña y se añadió `Business.onboarding_completed_at`. La migración conserva dueños/negocios existentes y crea sus membresías. El downgrade rechaza ejecutarse si ya existen datos nuevos que perdería o un dueño suspendido/incompleto; por eso es reversible antes de activar la función, y después requiere un plan de datos específico.

**Dónde:** `backend/api-backend/alembic/versions/7c9d2e4f6a10_platform_access_schema.py`, `backend/api-backend/tests/test_platform_schema_migration.py` y documentos de `specs/007-platform-admin-access-ui/`. No se modificaron modelos ORM, rutas, frontend ni infraestructura.

**Por qué:** preparar una base compatible para el acceso por invitación y la administración multi-negocio sin borrar ni bloquear a dueños existentes.

**Verificación:** prueba TDD: primero falló por ausencia de las tablas y cambio de `Owner.name`; después pasó subida y bajada en PostgreSQL 16 local aislado en `/tmp`, conservando un dueño y un negocio existentes. Se repitió tras ajustar formato: 1 prueba aprobada. `git diff --check` pasó y no quedaron líneas de más de 100 caracteres en la migración. No se ejecutó la migración en Neon ni producción.

### 2026-11-09 — T001: inventario estático de cuentas, negocio, acceso y correo

**Qué:** se documentó el estado real del modelo y del flujo actual: registro público activo; Owner sin rol/estado de plataforma; Business ligado al owner, sin marca de alta completa y con `is_active`; alta rechaza cualquier segundo negocio incluso inactivo; auth verifica correo solo según config; no existen invitaciones ni recuperación; el guard de onboarding vive en frontend; correo usa SMTP y registra el enlace completo si no está configurado; no hay integración runtime de Resend. Se anotó que el panel actual no tiene administración de plataforma y que las métricas de dashboard tienen definiciones que no equivalen a cobros/ocupación real.

**Dónde:** `specs/007-platform-admin-access-ui/research.md` y T001 en `tasks.md`. Sin cambios a código de aplicación ni servicios externos.

**Por qué:** saber qué compatibilidad y brechas hay antes de alterar autenticación, migraciones o permisos.

**Verificación:** lectura estática de modelos, rutas, dependencias, pantallas y variables sin mostrar valores secretos. `git diff --check` pasó. No hay MCP de Neon disponible, por lo que no se consultaron conteos reales. No se ejecutaron pruebas.

### 2026-11-09 — Plan Spec Kit para UI, invitaciones, recuperación y `/admin`

**Qué:** se crearon especificación, investigación, modelo de datos, contrato de UI/API, recorrido de verificación, checklist, plan y 35 tareas. Se incorporó la corrección del usuario: correo invitado como usuario, aceptación solo con contraseña, alta de negocio obligatoria y un usuario por negocio en esta fase; miembros futuros preparados. Se incluyó revisión de logo y datos demo, y métricas de gasto con diferencia entre estimado y real.

**Dónde:** `specs/007-platform-admin-access-ui/`, `.specify/feature.json`, referencia de plan en `AGENTS.md`, backlog #15/#16 y esta entrada. No se modificó código de producto ni infraestructura.

**Por qué:** dejar una implementación revisable y dividida en bloques antes de solicitar autorización para desarrollarla, siguiendo la constitución. Pacelas solo se usó como referencia de invitación y recuperación; Rafenixcore se registró como marca corporativa sin asumir dominio exacto.

**Verificación:** revisión estática de baseline, código actual, plantillas y consistencia documental; `git diff --check` y validación de formato de tareas pendientes. No se ejecutaron pruebas de aplicación ni servicios externos. El gancho de rama de Spec Kit falló porque `.git` es de solo lectura en este entorno; el plan quedó en el árbol de trabajo de `main`, sin commit.

### 2026-11-09 — Reparada configuración MCP local de Codex

**Qué:** se reconstruyeron las secciones MCP de `~/.codex/config.toml` usando las ocho definiciones globales de Claude Code, preservando el resto de las preferencias y guardando una copia del archivo previo. Los servidores locales de AWS, GitHub y Railway están habilitados; Vercel, Neon, Resend, Sentry y Meta WhatsApp están registrados pero todavía sin OAuth.

**Dónde:** configuración local de Codex fuera del repositorio; este registro en `docs/WORKLOG.md`. No se cambió la configuración de Railway del producto ni código de la aplicación.

**Por qué:** habilitar en Codex los MCP que ya estaban configurados en Claude Code después de corregir un TOML inválido por entradas duplicadas.

**Verificación:** `codex mcp list` reconoció los ocho servidores iniciales sin error de parseo y el TOML cargó correctamente; en esa comprobación, los servidores HTTP todavía no tenían OAuth completado. El archivo y su respaldo tienen permisos `600`. El estado posterior de OAuth y Cloudflare se registra en la entrada siguiente.

### 2026-11-09 — Añadido Cloudflare y comprobada autenticación local de AWS/Railway

**Qué:** se añadió a Codex el servidor Cloudflare (`https://mcp.cloudflare.com/mcp`) que existe en el plugin instalado en Claude Code. AWS y Railway ya estaban configurados; se verificaron sus credenciales locales sin exponer datos: AWS no tiene credenciales utilizables en esta sesión y Railway no estaba autenticado, por lo que se inició `railway login` y quedó esperando la autorización del usuario en navegador. También se inició OAuth de Cloudflare y quedó esperando aprobación del usuario.

**Dónde:** `~/.codex/config.toml` (servidor Cloudflare) y autenticación local del CLI Railway. Sin cambios en infraestructura del producto.

**Por qué:** completar los servidores que el usuario señaló como faltantes y distinguir configuración MCP de autenticación de cada proveedor.

**Verificación:** `codex mcp list` reconoce Cloudflare, AWS y Railway; `aws sts get-caller-identity` falló por ausencia de credenciales y `railway whoami --json` indicó que no había sesión. Se iniciaron los flujos de navegador para Cloudflare y Railway; al último chequeo aún no se habían completado.

### 2026-11-09 — Priorizado alcance de UI, correo y panel de administración

**Qué:** el usuario priorizó trabajar en la UI, el flujo de invitación y recuperación de contraseña por correo, y el panel de administración de plataforma para gestionar negocios y consultar métricas. Las recomendaciones de recordatorios, configuración guiada de WhatsApp y costos quedaron preservadas para una fase posterior. Se actualizó #16 a `EN CURSO` y #15 a `DIFERIDO`.

**Dónde:** `docs/WORKLOG.md`, backlog #15/#16 y detalle de alcance. Sin cambios de código ni infraestructura.

**Por qué:** fijar el orden de trabajo y evitar mezclar las mejoras de acceso/administración con las de WhatsApp y recordatorios.

**Verificación:** `git diff --check -- docs/WORKLOG.md`; no se ejecutaron pruebas. Antes de implementar, revisar los artefactos Spec Kit conforme a `AGENTS.md`.

### 2026-11-09 — Detalladas recomendaciones para administración de plataforma

**Qué:** se amplió el backlog #16 con el alcance conversado: identidad administrativa separada y creada de forma controlada; invitaciones/reenvíos/revocaciones y estados de cuenta; acceso de dueños solo a sus propios datos; panel global con métricas agregadas; registro de acciones administrativas; recomendación de MFA; y privacidad por defecto sin conversaciones ni teléfonos completos. Se documentó que los plazos del proyecto Pacelas son solo referencia y que el límite actual es un negocio por dueño.

**Dónde:** `docs/WORKLOG.md`, backlog #16 y detalle de alcance en «Propuesta en conversación». Sin cambios de código ni infraestructura.

**Por qué:** conservar las recomendaciones aceptadas y las decisiones que aún deben definirse antes de diseñar la implementación.

**Verificación:** `git diff --check -- docs/WORKLOG.md`. Se dejó explícito que los logs de estados de WhatsApp no son una contabilidad persistente y no permiten reportar gasto real por negocio; no se ejecutaron pruebas, según el alcance documental solicitado.

### 2026-11-09 — Revisado el modelo de invitación y recuperación de referencia

**Qué:** análisis de lectura del flujo existente en el proyecto `pacelas-venta-project`: invitación por Resend con token hasheado de 72 horas, aceptación con nombre y contraseña, recuperación con token de una hora y un solo uso, límite de solicitudes, revocación de sesiones y pantallas de login/aceptación/recuperación/restablecimiento.

**Dónde:** proyecto de referencia en `/home/hendrick-rafael/Documents/Proyectos Oficiales/pacelas-venta-project`, especialmente `src/lib/auth/`, `src/lib/correo/plantillas.ts` y `src/app/{admin/usuarios,invitacion,recuperar,restablecer}`. Sin modificaciones a ese proyecto ni al producto.

**Por qué:** usar una implementación comprobable para definir la etapa de acceso de SmartBooking por invitación y correo.

**Verificación:** lectura estática de código, especificación, QA, progreso y configuración documentada; no se ejecutó la aplicación, pruebas, scripts ni comandos de despliegue. La adaptación queda pendiente de socialización y decisión del emisor de la invitación inicial para los dueños.

### 2026-11-09 — Alcance conversado para administrador de plataforma

**Qué:** se registró como dirección aceptada una cuenta de administrador de plataforma para el dueño de SmartBooking, separada de las cuentas de propietarios de negocio. El administrador gestionará invitaciones/estado de cuentas y consultará métricas agregadas de negocios, citas, mensajes y costos. Los propietarios entrarán por invitación y tendrán recuperación de contraseña por correo.

**Dónde:** este backlog #16 y el análisis de `backend/api-backend/app/models.py`, rutas de negocio/dashboard y webhook de WhatsApp. Sin cambios de código ni infraestructura.

**Por qué:** el modelo actual solo representa dueños ligados a sus negocios; la administración entre negocios necesita identidad, permisos y vistas de plataforma separadas.

**Verificación:** lectura estática. Hallazgo importante: el webhook registra estados WhatsApp en logs, pero el sistema no persiste una bitácora de mensajes/categorías/cargos con la que calcular gasto real. El costo debe quedar como medición pendiente, no como métrica disponible hoy.

### 2026-11-09 — Diagnóstico de UI y acceso para primera etapa comercial

**Qué:** revisión de lectura de pantallas, formularios, recorrido de alta del negocio, registro público, verificación de correo y ausencia de recuperación e invitaciones para dueños. Se prepararon recomendaciones de producto; la comparación con el proyecto de referencia queda pendiente de su URL (#16).

**Dónde:** `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/App.tsx`, `frontend/index.html`, `backend/api-backend/app/api/auth.py`, `app/services/email_service.py`, `app/config.py`, y capturas de `docs/screenshots/`. Sin cambios de código ni infraestructura.

**Por qué:** distinguir el flujo real de los textos y estados de demostración antes de definir una experiencia vendible por invitación.

**Verificación:** lectura estática de archivos y capturas; no se ejecutó la aplicación, pruebas ni código, y no se comprobó el servicio de correo en producción.

### 2026-11-09 — Recomendaciones de recordatorios, WhatsApp y UI registradas

**Qué:** se anotaron siete recomendaciones y sus motivos como propuesta #15, incluida la preferencia del usuario por un único recordatorio a las 24 horas. Quedaron explícitamente pendientes de conversación y sin autorización de implementación.

**Dónde:** sección «Propuesta en conversación» de `docs/WORKLOG.md`. Sin cambios de código ni infraestructura.

**Por qué:** conservar las decisiones propuestas fuera del chat y separar el estado actual del resultado deseado.

**Verificación:** lectura del backlog existente y revisión del diff de este archivo; no se ejecutaron pruebas porque el cambio es solo documental.

### 2026-11-09 — Revisión de alta de negocios, WhatsApp, recordatorios y tarifas

**Qué:** análisis de solo lectura del flujo para incorporar dueños y negocios, activar su número, recibir citas y enviar recordatorios; contraste de tarifas de WhatsApp por categoría y mercado. En Railway producción figuran por nombre `META_APP_SECRET` y `META_WABA_TOKEN` (valores ocultos por OAuth), mientras el cron `reminders-cron` mantiene `cronSchedule=null`. También figura una variable adicional `META_APP_SECRET` con tabulador final en el nombre. Desde el 8 de noviembre hay POST al webhook con HTTP 200, pero en los logs consultados no apareció `wa_route`; dos POST registraron firma inválida. Esto no demuestra una conversación exitosa.

**Dónde:** lectura de `backend/api-backend/app/api/`, `app/services/background_tasks.py`, `app/services/whatsapp_client.py`, `main.py`, `docs/WHATSAPP_ONBOARDING.md`, Railway producción y fuentes públicas de Meta. Sin cambios de código ni infraestructura.

**Por qué:** precisar qué está implementado, qué funciona en producción y qué costos pueden presupuestarse sin suponer el estado de Meta.

**Verificación:** Railway MCP (`get_status`, `list_variables`, `get_service_config`, `get_logs`), lectura de código y tabla USD de Meta vigente desde 2026-10-01 archivada con procedencia y comprobación fechada. El MCP de Meta no está disponible en esta sesión; no se confirmó en vivo la WABA, la suscripción, la plantilla ni la facturación real.

### 2026-11-08 — Auditoría de arquitectura, WhatsApp y UI

**Qué:** se revisaron el flujo de webhooks y envíos WhatsApp, el modelo multi-tenant, el alta manual, las especificaciones vigentes y las pantallas/capturas de la UI. Se identificaron discrepancias para priorizar: un solo número por negocio; alta de IDs sin validación ni suscripción de WABA; token global para todos los negocios; ruta de negocio sin filtro `is_active`; errores del POST de WhatsApp devueltos como HTTP 200; menús interactivos en conflicto con la política de menús numerados; métricas del dashboard con rótulos imprecisos; configuración visual sin estado de conexión; identidad de marca inconsistente y favicon de Vite.

**Dónde:** `backend/api-backend/main.py`, `app/models.py`, `app/services/whatsapp_client.py`, `app/services/db_service.py`, `frontend/src/pages/BusinessSettings.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/components/Sidebar.tsx`, `frontend/index.html`, `specs/001-guided-menu-bot/` y `.specify/memory/constitution.md`. Sin cambios de código ni infraestructura.

**Por qué:** responder con el estado real y separar las limitaciones del producto de las de Meta antes de diseñar cambios.

**Verificación:** lectura de código, especificaciones y capturas guardadas en `docs/screenshots/`; contraste de requisitos de Meta con documentación oficial de WhatsApp Business y la colección oficial de Meta en Postman. No se hizo prueba end-to-end con número real ni se inspeccionó la configuración actual de Meta/Railway.

### 2026-11-08 — WhatsApp: diagnóstico real y negocio enlazado al número de Meta

**Qué:** análisis verificado (código + Railway + Neon + MCP de Meta) del estado de WhatsApp, y
alta del negocio que atenderá el número real. Se creó el owner `[correo omitido]`
(id 6) y el negocio **`SmartBooking`** (id 4) con `whatsapp_phone_number_id =
1180291398493188` (+1 809-243-8778), vía API pública de producción (`/auth/register`,
`/businesses/`), sin tocar la base a mano.
**Dónde:** Neon `neondb` (tablas `owners` y `businesses`); sin cambios de código.
**Por qué:** los 3 negocios existentes son de demo y ninguno tenía el número real, así que el
webhook habría respondido «Business not found». El proyecto limita un negocio por dueño, por eso
se creó una cuenta nueva en lugar de reutilizar `[correo omitido]`.
**Verificación:** `SELECT` en Neon confirma owner 6 + negocio 4 con el `phone_number_id`; la
creación por API devolvió `201`. Los tests de WhatsApp del backend pasan (50 passed).
**Sigue pendiente para que funcione:** (a) `META_APP_SECRET` y `META_WABA_TOKEN` en Railway
servicio `smartbooking-ai`; (b) confirmar en el App Dashboard que el callback es
`https://smartbooking-ai-production.up.railway.app/webhooks/whatsapp` con el verify token de
`META_VERIFY_TOKEN`; (c) prueba con un WhatsApp real y log `wa_route`.
**Seguridad:** la cuenta del owner se creó con contraseña temporal entregada al usuario; conviene
cambiarla desde el panel. No se registró ningún secreto en este worklog.

### 2026-10-20 — Producción al día: token rotado, `93a967f` desplegado y webhook firmado

**Qué:** cierra el pendiente de la entrada anterior. (1) Token del bot rotado en BotFather
(el anterior aparecía en los logs y en la respuesta del webhook); (2) `TELEGRAM_BOT_TOKEN`
actualizado en Railway; (3) creada `TELEGRAM_WEBHOOK_SECRET`; (4) desplegado `93a967f`,
que envuelve los fallos de httpx en `TelegramSendError` para que la URL con el token no
llegue al log; (5) webhook registrado con `secret_token`.
**Dónde:** Railway · servicio `smartbooking-ai` · producción (variables `TELEGRAM_BOT_TOKEN`
y `TELEGRAM_WEBHOOK_SECRET`); `app/services/telegram_client.py`; Telegram `setWebhook`.
**Por qué:** sin token nuevo el bot no podía enviar nada; sin `secret_token` cualquiera con
la URL podía inyectar actualizaciones falsas; y sin el saneado de excepciones el token
seguía escribiéndose en los logs de Railway.
**Verificación:** deploy `7b6bfc41` → `SUCCESS` (arranque, migraciones Alembic y uvicorn OK);
hash SHA-256 del token en Railway == `.env` local (comparado sin imprimir valores);
`getWebhookInfo` → URL correcta, `pending_update_count: 0`, sin último error; `POST` sin
cabecera → **403**, secret incorrecto → **403**, secret correcto + cuerpo inválido → **400**
(prueba de que la firma se valida y el payload se rechaza); logs del despliegue sin ninguna
línea que contenga `api.telegram.org/bot`.
**Nota operativa:** el primer intento (`e4e46c69`) falló en *railpack prepare* porque al
subir solo `backend/api-backend` la ruta `/backend/api-backend` —el `rootDirectory` del
servicio— no existía dentro del archivo. Se relanzó con la estructura completa. Este
despliegue salió de una copia preparada, no de un push; el repo sigue enlazado, así que el
próximo push a `main` volverá a desplegar por git.
**Incidente externo:** entre las 17:03 y las ~20:40 UTC Railway pausó los builds de todos
los workspaces («New builds are temporarily paused», `status.railway.com`); no fue una
desconexión ni el cambio de nombre de usuario. El servicio ya desplegado no se vio afectado.

### 2026-10-20 — Secret token del webhook de Telegram y errores sin detalle

**Qué:** el webhook `/webhooks/telegram` procesaba cualquier petición que llegara a la
URL y, si algo fallaba, devolvía `{"status":"error","message":str(e)}` al cliente.
Ahora comprueba `X-Telegram-Bot-Api-Secret-Token` y responde sin detalle.
**Dónde:** `main.py` (`telegram_webhook`), `app/config.py` (`TELEGRAM_WEBHOOK_SECRET`),
`app/core/webhook_security.py` (nuevo) y `tests/test_webhook_security.py` (nuevo).
**Por qué:** sin firma, cualquiera que conozca la URL puede inyectar actualizaciones
falsas y crear o cancelar citas en nombre de un usuario. Devolver `str(e)` filtraba
detalles internos al cliente.
**Compatibilidad:** la variable es opcional. Si no está definida, el webhook acepta como
antes, así que el código puede desplegarse sin dejar el bot caído. Para activarla hay que
definir `TELEGRAM_WEBHOOK_SECRET` en Railway y registrar el mismo valor con
`setWebhook(secret_token=...)`. **Pendiente de configuración.**
**También:** README corregido — decía «25+ tests backend» cuando hay 423, y afirmaba
firma de webhook para Telegram que no existía.
**Verificación:** `pytest tests -q` → 423 passed (9 nuevos). No se probó contra el bot real.

### 2026-10-20 — Cuenta de demostración real en el login, y repo renombrado

### 2026-10-20 — Cuenta de demostración real en el login, y repo renombrado

**Qué:** el aviso bajo el formulario mostraba credenciales de un *seed local*
(`[correo omitido]`) que no existen en producción. Ahora muestra la
credenciales de demo retiradas del producto; no registrar contraseñas reales en el worklog.
**Dónde:** `frontend/src/pages/Login.tsx` (bloque «Demo Credentials»).
**Por qué:** la demo pública se comparte con reclutadores; un aviso con credenciales que
no funcionan resta credibilidad y confunde.
**Datos de la demo (Railway · producción):** dueño `[correo omitido]` (id 5); negocio
`Barbería Rafenix` (id 3); servicios «Corte de cabello», «Arreglo de barba» y
«Corte + barba»; horarios L-S 09:00-18:00; un cliente y una cita confirmada de ejemplo.
Creados con la API pública (`/auth/register`, `/businesses`, `/services`,
`/schedule-rules?business_id=`, `/customers`, `/appointments`), sin tocar la base a mano.
**Verificación:** login en el panel con Playwright → llega a `/dashboard` con el negocio y
el checklist en 4/5 (la cita de ejemplo se creó después).
**Repo:** renombrado `smartbookin-agent-ai` → **`smartbooking-ai`** (GitHub conserva
redirección desde el nombre viejo).

### 2026-10-19 — MCP oficial de Meta (WhatsApp Business Tools) añadido

**Qué:** servidor MCP `meta-whatsapp` (`--transport http`, scope `user`) apuntando a
`https://mcp.facebook.com/whatsapp_business_tools`.
**Por qué:** el usuario lo pidió para configurar WhatsApp Business desde el agente.
**Autenticación:** OAuth 2.0 Authorization Code + PKCE (S256) con Facebook Login for
Business; registro dinámico de cliente; scopes `business_management`,
`whatsapp_business_management`, `whatsapp_business_messaging`. Sin token estático.
**Estado:** añadido a `~/.claude.json`; queda **pendiente la autenticación interactiva**
del usuario vía `/mcp` (no se puede automatizar).
**Nota:** el MCP no entrega el token de system user que el backend necesita
(`META_WABA_TOKEN` + `META_APP_SECRET`); sirve para configurar la cuenta, no para el
runtime. Meta lo describe como herramienta de setup/pruebas, no de envío en producción.


### 2026-10-04 — Fix `pool_pre_ping` + estado real del cron (⚠️ cadencia no fiable)

**Qué:** commit `4997193` → `app/core/database.py`. Deploy `d936540f` (`SUCCESS`).

**Por qué:** el tick del cron de las 16:02 devolvió
`wget: server returned error: HTTP/1.1 500 Internal Server Error`. Causa: el primer
request tras un periodo de reposo falla porque el contenedor de Railway duerme y Neon
suspende el compute, dejando handles muertos en el pool de SQLAlchemy. El reintento
manual funcionaba, pero **el cron no reintenta**. Sin este fix, el cron falla
precisamente cuando el sistema estuvo inactivo — que es su situación normal.

**Fix:** `pool_pre_ping=True` en `create_async_engine`.

**Verificación (prueba directa en frío):** a las 16:17:02, con el backend ~15 min sin
recibir tráfico y Neon suspendido desde las 16:07, un `POST /api/auth/token` devolvió
**401 en 3.68 s** (antes: 500). Los 3.68 s son el tiempo de despertar Neon.

---

**⚠️ Problema abierto — cadencia del cron.** Los logs con timestamp muestran:

```
15:45:14  EXIT=0                 ← ejecución correcta
16:02:17  wget: 500              ← el bug de pool_pre_ping (ya corregido)
16:16:54  Stopping Container     ← el contenedor de las 16:02 tardó ~14 min en terminar
```

La doc de Railway dice: *"if a previous execution is still running when the next
scheduled execution is due, Railway will skip the new cron job"*. Eso explica que no
hubiera ejecución a las 16:15, y que los ticks observados (15:45, 16:02) no sigan un
patrón `*/15` limpio.

La configuración **está bien** — confirmado por GraphQL:
`cronSchedule = "*/15 * * * *"` con el start command correcto. El problema es el ciclo
de vida del contenedor, no la configuración.

**Hipótesis sin confirmar:** el `startCommand` pasado como `sh -c '...'` deja un shell
como PID 1 que Railway no considera terminado. **Próximo intento sugerido:** quitar el
wrapper `sh -c`, usar `wget -T 30 -t 1 -O /dev/null` (sin barra de progreso y con
timeout acotado) y verificar si el contenedor termina de inmediato. Si Railway sigue
sin terminar el contenedor, **migrar a GitHub Actions** (cron en el repo, sin ciclo de
vida de contenedor).

**Impacto:** los recordatorios se envían cuando el cron logra correr, pero no con la
puntualidad de 15 min que el spec asume. No bloquea, pero no está terminado.


### 2026-10-04 — Cierre de la tarea bloqueante #0: fixes commiteados y deploy desde git validado

**Qué:** commit `a85bb97` en `main` con los fixes del incidente, más `docs/WORKLOG.md`,
la norma de registro en `AGENTS.md` y la limpieza de `REDIS_URL` en `.env.example`.
Autorizado explícitamente por el usuario para commitear y pushear a `main`.

**Dónde:** `main` (`3ef430a..a85bb97`). Railway disparó el deploy `c5cfee6f`
automáticamente desde GitHub — **la primera vez en el día que un deploy sale de git
y no de `railway deployment up`**.

**Por qué:** hasta este commit, el código corriendo en producción no existía en git.
Cualquier deploy disparado por GitHub habría reconstruido la imagen sin los fixes y
reproducido el crash.

**Verificación (deploy `c5cfee6f`, commit `a85bb97` → `SUCCESS`):**
- `GET /` → 200 · `GET /docs` → 200 · `GET /openapi.json` → 200
- `POST /api/auth/token` → **401** ⇒ la BD responde
- `POST /internal/jobs/reminders` sin token → **401** ⇒ protección intacta
- Preflight CORS desde `https://smartbookin-agent-ai.vercel.app` → **200** con
  `access-control-allow-origin` correcto ⇒ el panel puede hablar con el backend

**Estado:** producción es reproducible desde `main`. La ventana de fragilidad
abierta por el incidente queda cerrada.


### 2026-10-04 — Cron de recordatorios + higiene autorizada

**Qué / Dónde:**
- **Nuevo servicio `reminders-cron`** en Railway (`79a8984e-86df-4f2d-a82d-58e2edf067f9`):
  imagen `alpine:latest`, cron `*/15 * * * *`, variables `CRON_URL` (plana) y
  `CRON_TOKEN` (variable de referencia → `${{smartbooking-ai.INTERNAL_CRON_TOKEN}}`,
  para no duplicar el secreto). Start command:
  `sh -c 'wget -O- --header="Authorization: Bearer $CRON_TOKEN" --post-data="" "$CRON_URL"; rc=$?; echo "EXIT=$rc"; exit $rc'`
- **`apscheduler_jobs`**: borradas las 3 filas obsoletas (`reminders_job`,
  `waitlist_job`, `agenda_job`, de junio). Tabla en 0 filas.
- **`requirements.txt`**: topes de versión mayor en las 20 dependencias.
- **`VITE_API_URL`**: configurada por el usuario en Vercel.

**Por qué:** los recordatorios 24h/2h no se enviaban (`CRON_EXTERNAL=true` sin cron);
el resto es la higiene autorizada por el usuario.

**Verificación:**
- Cron: ejecución real a las 15:45:14 → `{"status":"ok","job":"reminders"}` con `EXIT=0`,
  y Neon despertó (`last_active` 15:40:59) ⇒ la query llegó a la base.
- Vercel: el bundle desplegado ahora contiene `https://smartbooking-ai-production.up.railway.app/api`
  y el host muerto `9cce` ya no aparece.
- CORS: preflight `OPTIONS` desde `https://smartbookin-agent-ai.vercel.app` → 200 con
  `access-control-allow-origin` correcto; `POST /api/auth/token` → 401 con el header.
- Deps pineadas: deploy `d9652b09` → `SUCCESS`; `/`, `/docs` en 200 y login 401 consistente.

**Aprendizajes operativos (importantes para la próxima):**
1. **Todo cambio de variable en Railway dispara un redeploy.** Con dependencias sin
   pinear, eso equivale a un cambio de dependencias. Ver el incidente de abajo.
2. **Los ajustes de servicio se hornean al crear el deployment.** `sleep_application`,
   `start_command` y `cron_schedule` no aplican hasta que se **redespliega**. Me pasó con
   el cron: el contenedor arrancaba pero ignoraba el start command hasta hacer
   `railway redeploy --from-source`.
3. **Railway exige un intervalo mínimo de 5 minutos** en cron schedules.
4. Para diagnosticar un cron, **no usar `wget -q`**: silencia el error y el fallo es
   invisible. Y ojo: un **401 no toca la base de datos**, así que "Neon sin actividad"
   no distingue entre "no llegó la petición" y "llegó y falló la auth".

---

### 2026-10-04 — 🔴 Incidente: caída de producción por redeploy + fix de dependencias

**Qué:** al activar `AI_ENABLED=false` (tarea #6) Railway disparó un redeploy. El
contenedor **crasheó al arrancar** y el backend quedó en 502 durante ~14 minutos.
Se arregló y se restauró el servicio.

**Diagnóstico:** el build pasaba; el crash era en el arranque. La causa raíz es que
**`requirements.txt` no tenía versiones fijas**: al reconstruir la imagen se
resolvieron versiones nuevas que rompieron dos cosas encadenadas.

1. **`greenlet` desapareció.** SQLAlchemy ≥2.1 ya no lo instala por defecto (solo vía
   el extra `[asyncio]`). Sin él, `alembic upgrade head` —que corre en el `CMD` del
   Dockerfile— muere con `ModuleNotFoundError: No module named 'greenlet'`.
2. **Al arreglar eso, apareció `psycopg`.** SQLAlchemy ≥2.1 resuelve la URL
   `postgresql://` al dialecto **psycopg3**, que no está instalado.
   Agravante: [scheduler.py:10](backend/api-backend/app/core/scheduler.py#L10) hacía
   `DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")`, un **no-op**,
   porque `DATABASE_URL` llega sin `+asyncpg` (ese sufijo lo añade
   `app/core/database.py:31` y solo para el engine async). Y como `main.py:38`
   importa `app.core.scheduler`, el `SQLAlchemyJobStore` se construye **siempre**,
   incluso con `CRON_EXTERNAL=true`.

**Dónde:**
- `backend/api-backend/requirements.txt` → `sqlalchemy[asyncio]` + `greenlet`
- `backend/api-backend/app/core/scheduler.py` → fuerza `postgresql+psycopg2://`

**Por qué importa:** era una **rotura latente**, no algo introducido por el cambio.
Cualquier rebuild de la imagen la habría expuesto. El redeploy solo la adelantó.

**Verificación:** deploy `f7a4de09` → `SUCCESS`; `/` y `/docs` en 200;
`POST /api/auth/token` → 401; `POST /internal/jobs/reminders` sin token → 401.

**Cómo se desplegó:** con `railway deployment up` (sube el código local), **no desde
git** — de ahí la tarea bloqueante #0.

---

### 2026-10-04 — Auditoría de infraestructura y costos (solo lectura)

**Qué:** inventario y medición de los tres proveedores de este proyecto.
**Dónde:** Railway, Vercel, Neon + probes HTTP + consultas SQL de lectura.
**Por qué:** optimización de gastos solicitada por el usuario.

**Hallazgos:**
- Backend ~$0.97/mes corriendo 24/7 con **cero tráfico HTTP** y **cero queries a BD por 15 días**.
- Frontend de producción **roto**: bundle apuntaba a `smartbooking-production-9cce.up.railway.app` (`404 Application not found`).
- Recordatorios **no se envían**: `CRON_EXTERNAL=true` sin cron externo.
- WhatsApp **inerte**: faltan `META_WABA_TOKEN` y `META_APP_SECRET`.
- Sentry **nunca inicializado**: `SENTRY_DSN` ausente.
- Última cita creada: **2026-08-29** (36 días sin actividad de negocio).

**Verificado:** `railway usage` (soft $8 / hard $15, uso $2.88, estimado $5.22);
Vercel `billing.plan = "hobby"`; Neon free tier.
