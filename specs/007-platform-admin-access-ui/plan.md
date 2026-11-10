# Implementation Plan: Acceso por invitación, administración de plataforma y UI comercial

**Rama**: `007-platform-admin-access-ui`
**Fecha**: 2026-11-09
**Especificación**: [spec.md](spec.md)
**Estado**: T001–T016, T018–T032, T034 y T035 completadas. Los hallazgos R1–R6 de T035 se corrigieron localmente. T017/T033 siguen pendientes de recorridos funcionales desde la aplicación antes del despliegue.

## Resumen

Convertir el registro público actual en acceso de dueños por invitación de administrador. El correo invitado será el usuario; la aceptación solo define contraseña. El primer acceso exige completar el negocio. Añadir identidad de plataforma y panel privado en `/admin` para gestionar negocios, permisos de esta fase y métricas sustentadas por datos. Unificar la UI comercial, retirar textos demo y diseñar una marca SmartBooking propia bajo Rafenixcore. Resend y Cloudflare se consultarán y configurarán durante desarrollo, tras verificar dominio/remitente.

## Technical Context

**Lenguajes**: Python y TypeScript existentes; versiones exactas según manifiestos del repositorio.
**Dependencias**: FastAPI, SQLAlchemy async, Alembic, PostgreSQL; React, Vite, Zustand, React Query, TailwindCSS.
**Almacenamiento**: PostgreSQL/Neon; modelos existentes `Owner`, `Business`, `Appointment` y refresh tokens.
**Pruebas**: pytest/backend y pruebas frontend existentes; pruebas nuevas enfocadas en auth, permisos, migración, aislamiento y métricas.
**Plataforma**: backend Railway y SPA Vercel; Resend confirma `rafenixcore.com` verificado. Remitente y clave limitada al dominio están configurados en Railway; una prueba directa fue entregada. Cloudflare MCP no está disponible y no se necesitó cambiar DNS.
**Tipo**: aplicación web con API multi-tenant.
**Objetivos**: flujos de alta y recuperación completos; ningún acceso cruzado entre negocios; métricas exactas para las fuentes disponibles; UI legible en móvil y escritorio.
**Restricciones**: un negocio activo y un usuario dueño por negocio en fase 1; no presentar gasto estimado como gasto real; no activar recordatorios ni crear miembros de negocio.
**Escala**: primer lanzamiento comercial sin cuota nueva de negocios definida; listas del admin paginadas desde el inicio.

## Constitution Check

| Principio | Diseño previsto | Resultado |
|---|---|---|
| Specs como fuente | `spec.md`, este plan y `tasks.md` antes del código | Cumple |
| Aislamiento por `business_id` | Separación de principal administrador/dueño y filtros en rutas del dueño | R3 corregido y probado localmente bajo concurrencia; verificar en entorno de prueba antes de desplegar |
| Acciones deterministas | Alta, invitación y suspensión en servicios transaccionales, no IA | Cumple |
| Canales y conversación | No modifica bot, recordatorios ni flujo de citas | Cumple |
| Seguridad y límites | Tokens de un uso, rate limits, sesiones revocables, auditoría | R2 y R4–R6 corregidos y probados localmente; verificar en entorno de prueba antes de desplegar |
| Pruebas sensibles | Tareas de auth/permisos/métricas incluyen pruebas de comportamiento | Cumple |
| Un negocio activo por dueño | Restricción existente preservada y verificada | Cumple |

**Revisión posterior al diseño**: T035 encontró R1–R6 y se corrigieron localmente con pruebas enfocadas; ver [security-review.md](security-review.md). La entrega directa de correo está verificada, pero los recorridos de invitación/recuperación y la validación en entorno de prueba siguen abiertos. El gasto real sigue condicionado a conciliación con fuente de facturación.

## Fases de implementación

1. **Base y migraciones**: inventario de cuentas existentes, modelo de identidad de plataforma, invitaciones, recuperación, membresía futura, auditoría y eventos de mensajes. Migraciones compatibles y plan de reversión.
2. **Seguridad y correo**: bootstrap de administrador, autenticación diferenciada, autorización de rutas, Resend con remitente Rafenixcore verificado, rate limits, enlaces de un uso y revocación de sesiones.
3. **Invitación y alta del dueño**: panel para invitar/revocar/reenviar, aceptación con contraseña, acceso y alta de negocio obligatoria; desactivar registro público sin bloquear cuentas existentes.
4. **Recuperación**: solicitud neutral, entrega y restablecimiento para dueño y administrador.
5. **Gestión `/admin`**: negocios, estados, usuarios de esta fase, bitácora y suspensión/reactivación; filtros y paginación.
6. **Métricas**: definiciones exactas para citas/clientes; eventos de mensajería por negocio; gasto estimado con fuente/tarifa, gasto real solo con conciliación. Estados de cobertura.
7. **UI y marca**: logo Turno aprobado por el usuario e integrado; tokens visuales, pantallas de acceso/alta/admin y ajuste de panel de negocio; limpiar demo, textos de prueba y registro. Verificación responsive/accesibilidad.
8. **Cierre**: pruebas por etapa, recorrido de aceptación, comprobación de servicios externos y documentación operativa. El despliegue requiere autorización posterior.

Las fases 2–4 tienen dependencias de seguridad y datos; no deben fusionarse en un cambio grande. Cada bloque se revisa al cerrar según `tasks.md`.

**Revisión de modos (2026-11-09):** T009, T015, T018 y T022 pueden prepararse en Luna porque solo añaden pruebas o documentan definiciones; Sol revisará esos resultados antes de implementar los servicios sensibles que dependen de ellos. T013 pasa a Luna únicamente para UI, después de que T008 proteja el backend. T035 incluye una revisión integral en Sol de los trabajos de Luna antes de cualquier despliegue. La asignación y las dependencias detalladas están en `tasks.md`.

## Estructura del proyecto

```text
specs/007-platform-admin-access-ui/
  spec.md  plan.md  research.md  data-model.md  quickstart.md
  security-review.md  ui-review.md
  contracts/access-admin-ui.md  tasks.md  checklists/requirements.md

backend/api-backend/
  app/models.py
  app/api/auth.py  app/api/businesses.py  app/api/dashboard.py
  app/core/dependencies.py  app/services/email_service.py
  alembic/versions/  tests/
frontend/
  src/App.tsx  src/pages/Login.tsx  src/pages/BusinessOnboarding.tsx
  src/pages/AcceptInvitation.tsx  src/pages/ForgotPassword.tsx
  src/pages/ResetPassword.tsx  src/pages/platform/
  src/components/  src/store/  src/services/
  public/  index.html
```

**Decisión estructural**: ampliar backend y frontend existentes. Las nuevas rutas de plataforma se agrupan separadas de las rutas de dueño. La UI reutiliza componentes compartidos y usa un shell distinto para `/admin`.

## Contratos y migración

- Ver [data-model.md](data-model.md) para entidades, transiciones y compatibilidad.
- Ver [contracts/access-admin-ui.md](contracts/access-admin-ui.md) para rutas, respuestas y permisos.
- Ver [research.md](research.md) para decisiones y brechas comprobadas.
- Ver [quickstart.md](quickstart.md) para los recorridos de aceptación.

**Puertas antes de producción**: Turno ya fue aprobado e integrado, Resend confirmó `rafenixcore.com`, Railway tiene remitente y clave restringida al dominio, y una prueba directa fue entregada. R1–R6 y las migraciones se probaron en PostgreSQL local. Faltan el recorrido manual, migrar Neon y verificar permisos/métricas en el entorno desplegado. Mostrar «gasto real» solo después de conciliar con la facturación de Meta.
