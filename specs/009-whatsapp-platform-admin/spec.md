# WhatsApp multi negocio desde plataforma y pausa temporal de Telegram

**Estado:** Aprobado para implementación por solicitud del usuario (2026-11-10)

**Base:** `specs/000-project-baseline/`, constitución del proyecto y decisión registrada en `docs/WORKLOG.md` #21.

## Objetivo

Permitir que el administrador de plataforma asigne desde `/admin` un Phone Number ID y una cuenta Meta a cada negocio. Varios negocios pueden compartir el mismo ID de cuenta; cada número sigue perteneciendo a un solo negocio. Telegram queda temporalmente inactivo en interfaz y backend.

El administrador registra previamente cada número y completa su verificación en Meta con la colaboración de su titular. Este alcance vincula identificadores ya registrados; no implementa Embedded Signup ni inicia verificaciones Meta. Los secretos globales de Meta siguen en variables seguras del entorno del backend, no en PostgreSQL ni en respuestas de API. No se agrega ni modifica ningún método de pago.

## Historias y criterios de aceptación

### US1 — Administrar el vínculo WhatsApp por negocio

Como administrador de plataforma, quiero guardar la cuenta Meta y el Phone Number ID desde el detalle del negocio para que el dueño no gestione credenciales del canal.

- Solo una sesión válida de administrador puede leer o modificar el vínculo.
- El dueño no ve ni puede modificar IDs WhatsApp mediante el API de negocio.
- Se permiten IDs de cuenta repetidos entre negocios; el Phone Number ID permanece único.
- El detalle muestra “Credenciales guardadas” cuando hay ambos IDs, sin afirmar que Meta o la entrega fueron probados.
- El formulario exige ambos IDs juntos, valida que sean numéricos y tengan entre 5 y 64 dígitos, mantiene “Guardar credenciales” deshabilitado mientras no haya cambios y pide confirmación explícita antes de vaciar ambos campos.
- Las modificaciones quedan en la bitácora administrativa sin almacenar secretos.
- Métodos de pago y credenciales secretas no se exponen en la UI ni en APIs.

### US2 — Enrutar números al negocio correcto

Al recibir webhook, SmartBooking resuelve el negocio por Phone Number ID único, usa las credenciales Meta globales del entorno y responde desde el mismo número receptor. Un ID sin vínculo no procesa conversación ni crea datos para otro negocio.

### US3 — Pausar Telegram

Telegram deja de aparecer como canal activo en navegación, onboarding, dashboard y textos de ayuda. El webhook de Telegram y rutas de activación dejan de procesar solicitudes. Las tareas de recordatorio no envían por Telegram. Se conserva código y datos históricos para una futura reactivación; no se borran vínculos ni registros.

## Restricciones y fuera de alcance

- Un número por negocio y un negocio por Phone Number ID.
- Un mismo WABA / ID de cuenta puede repetirse en distintos negocios.
- Se mantiene la regla vigente de un negocio por dueño.
- No se integra OAuth/Embedded Signup de Meta ni el alta automatizada de números.
- No se cambian pagos, templates, tarifas, recordatorios ni el cron.
- El estado local solo confirma que las credenciales fueron guardadas; la prueba real requiere configuración Meta, número verificado, permisos, webhook y prueba de mensaje.

## Riesgos y manejo

- Un identificador incorrecto puede impedir envíos: presentar los campos como datos técnicos y el estado como “Credenciales guardadas”, no “conectado”. Los errores deben distinguir campos incompletos, formato inválido y conflicto con otro negocio.
- La migración elimina solo la unicidad de `waba_id`; preserva los valores y la unicidad de Phone Number ID.
- Telegram se puede reactivar explícitamente cambiando el flag de canal y restaurando las rutas/UI; los datos antiguos se conservan.
