# Tareas

## Fase 1 — Contratos y pruebas (US1/US2/US3)

- [x] T001 [US1] Añadir pruebas de API para acceso admin-only, asignación/eliminación de IDs, auditoría, mismo WABA repetido y Phone Number ID duplicado rechazado. (modo: high)
- [x] T002 [US1] Añadir regresiones para que el API de dueño no admita ni exponga IDs WhatsApp. (modo: medium)
- [x] T003 [US2] Añadir prueba del webhook que enruta dos Phone Number IDs a negocios distintos y rechaza IDs desconocidos sin crear datos tenant. (modo: high)
- [x] T004 [US3] Añadir pruebas de webhook/rutas Telegram desactivadas y de que recordatorios no invocan Telegram. (modo: high)
- [x] T005 [US1/US3] Añadir pruebas frontend de sección WhatsApp en `/admin`, ausencia de campos para dueño, y ausencia de Telegram en navegación/onboarding/dashboard. (modo: medium)

## Fase 2 — Backend y persistencia

- [x] T006 [US1] Crear migración que retire solo `uq_businesses_waba_id`, preservando IDs y unicidad de Phone Number ID. (modo: high)
- [x] T007 [US1] Añadir DTO y endpoints protegidos de configuración WhatsApp para administrador; auditar cambios sin persistir secretos. (modo: high)
- [x] T008 [US1/US2] Quitar campos WhatsApp de esquemas y actualización del dueño; mantener lectura interna del modelo para routing. (modo: medium)
- [x] T009 [US3] Desactivar Telegram en webhook, rutas de activación y recordatorios mediante flag cerrado por defecto. (modo: medium)

## Fase 3 — UI y documentación

- [x] T010 [US1] Añadir gestión de IDs WhatsApp y estado “Credenciales guardadas” al detalle `/admin/businesses/:id`. (modo: medium)
- [x] T011 [US1/US3] Eliminar los campos WhatsApp del dueño y retirar rutas, enlaces, checklist y textos activos de Telegram. (modo: medium)
- [x] T012 [US1/US3] Actualizar baseline, constitución (pausa temporal de Telegram), arquitectura, quickstart, backlog y worklog. (modo: medium)
- [x] T013 [US1/US2/US3] Ejecutar suites enfocadas, build/lint frontend y `git diff --check`; registrar resultados. (modo: medium)

## Fase 4 — Corrección de UX del formulario

- [x] T014 [US1] Cambiar el botón a “Guardar credenciales”, deshabilitarlo sin cambios, validar formato numérico y longitud de 5–64 dígitos en cliente y servidor, mostrar mensajes distintos para campos incompletos, formato inválido y conflicto de Phone Number ID, y pedir confirmación antes de vaciar ambos campos. (modo: medium)
