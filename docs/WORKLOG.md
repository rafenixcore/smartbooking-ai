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
| 3 | WhatsApp en producción | DIFERIDO | Decisión del usuario: lo verifica él después |
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

### Deuda conocida (no bloquea)

- **#3 WhatsApp:** falta `META_WABA_TOKEN` y `META_APP_SECRET`. El commit `794bb88`
  (multi-tenant interactivo) está desplegado pero no puede funcionar:
  `validate_signature()` devuelve `False` sin `app_secret` y el webhook responde 403
  (fail-closed, o sea seguro). Ver `docs/WHATSAPP_ONBOARDING.md` y `WHATSAPP_COSTING.md`.
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
(`barberia.excelencia.demo@local.test`) que no existen en producción. Ahora muestra la
cuenta de demostración real: `demo@rafenixcore.com` / `Demo2026-Rafenix`.
**Dónde:** `frontend/src/pages/Login.tsx` (bloque «Demo Credentials»).
**Por qué:** la demo pública se comparte con reclutadores; un aviso con credenciales que
no funcionan resta credibilidad y confunde.
**Datos de la demo (Railway · producción):** dueño `demo@rafenixcore.com` (id 5); negocio
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
