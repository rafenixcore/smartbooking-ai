# Feature Specification: Acceso por invitación, administración de plataforma y UI comercial

**Fecha**: 2026-11-09
**Estado**: Implementación en curso; revisión T035 documentada en `security-review.md`, con hallazgos previos al despliegue
**Referencia**: `specs/000-project-baseline/` y decisiones del usuario en la conversación. Pacelas aporta solo el patrón de invitación y recuperación por correo.

## Alcance y actores

La primera fase comercial tiene tres actores: administrador de plataforma (propietario de Rafenixcore/SmartBooking), dueño de negocio invitado y cliente que reserva. Solo se añade acceso administrativo para los dos primeros. Cada negocio tiene un único usuario dueño en esta fase. Se deja preparado el modelo para miembros futuros sin exponer invitaciones de personal ahora.

La cuenta de administrador entra en `/admin` y gestiona negocios, invitaciones, accesos y métricas. El dueño entra a su panel actual, limitado a su negocio. No hay registro público de dueños ni de administradores.

## User Scenarios & Testing

### User Story 1 — Invitar y activar un negocio (P1)

El administrador invita un correo. Quien lo recibe establece únicamente una contraseña; el correo de la invitación es su usuario. Al iniciar sesión, completa los datos necesarios del negocio. Hasta terminar ese paso no ve el panel operativo.

**Verificación independiente**: invitar un correo nuevo, aceptar el enlace, crear contraseña, completar negocio y acceder al panel; repetir con enlace vencido, revocado y usado.

**Criterios de aceptación**:

1. Un visitante sin invitación no puede crear una cuenta de dueño.
2. La pantalla de aceptación muestra el correo asignado sin pedir que se vuelva a escribir; pide contraseña y confirmación únicamente.
3. La invitación vence a las 72 horas; una invitación usada, vencida o revocada no crea una cuenta.
4. Un dueño autenticado sin negocio completo solo puede completar su alta y cerrar sesión.
5. Tras completar el alta, el dueño accede únicamente a su propio negocio.

### User Story 2 — Recuperar acceso (P1)

Administrador y dueño pueden pedir por correo un enlace para restablecer su contraseña.

**Verificación independiente**: solicitar enlace con correo existente y desconocido, comparar respuesta pública, usar el enlace una vez y comprobar que las sesiones anteriores quedan revocadas.

**Criterios de aceptación**:

1. La respuesta pública no revela si existe la cuenta.
2. Un enlace vencido o usado permite solicitar otro sin mostrar datos personales.
3. Cambiar contraseña invalida las sesiones previas.

### User Story 3 — Gestionar negocios desde `/admin` (P1)

El administrador ve negocios e invitaciones, reenvía o revoca invitaciones, y suspende o reactiva cuentas sin borrar historial.

**Verificación independiente**: comprobar cada estado y que un dueño suspendido no puede operar aun con una sesión previa.

**Criterios de aceptación**:

1. Solo la cuenta de plataforma puede consultar o ejecutar estas acciones.
2. Cada acción sensible conserva actor, momento, entidad y resultado en una bitácora.
3. El dueño no ve información de otros negocios ni rutas de plataforma.

### User Story 4 — Consultar métricas y gasto (P2)

El administrador ve métricas globales y por negocio para un periodo definido: negocios por estado, citas por estado, clientes distintos con citas, mensajes enviados/entregados/fallidos y gasto de mensajes cuando exista evidencia para calcularlo.

**Verificación independiente**: comparar conteos con las filas fuente y comprobar que la UI distingue valor real, estimado y no disponible.

**Criterios de aceptación**:

1. Cada métrica incluye periodo, definición y fuente; los conteos por negocio coinciden con sus datos.
2. Los eventos de mensaje se atribuyen a un negocio sin contar reintentos duplicados dos veces.
3. El gasto real solo aparece tras conciliación con una fuente de facturación; una estimación se etiqueta como tal.
4. No se muestran por defecto conversaciones ni teléfonos completos de clientes.

### User Story 5 — UI clara y marca propia (P2)

Administrador y dueños reconocen de inmediato dónde están, qué falta hacer y qué acciones pueden realizar. La interfaz usa una identidad propia de SmartBooking bajo Rafenixcore.

**Verificación independiente**: revisión visual en móvil y escritorio de acceso, invitación, recuperación, alta, panel del dueño y `/admin`; inventario de textos de prueba y recursos de marca.

**Criterios de aceptación**:

1. No aparecen credenciales demo, mensajes de prueba, registro público, fecha de compilación ni favicon de Vite en las superficies comerciales.
2. Logo, favicon, navegación, correo transaccional y pantallas de acceso usan una identidad coherente y legible a tamaños pequeños.
3. Formularios tienen etiquetas claras, estados de carga, error y éxito, foco visible y opción de mostrar contraseña.
4. La navegación móvil y de escritorio separa claramente administración de plataforma y operación de negocio.

### Casos límite

- Invitación enviada a un correo existente, pendiente, revocada o vencida.
- Correo fallido: no presentar la invitación como entregada; permitir reintento controlado.
- Invitado que abandona antes de completar el negocio: reanuda el alta al volver.
- Negocio suspendido durante una sesión activa.
- Dos intentos simultáneos de aceptar el mismo enlace o crear un segundo negocio para el mismo dueño.
- Evento de mensaje sin identificador de negocio o sin datos de tarifa: excluir de gasto real e informar cobertura incompleta.

## Requirements

### Functional Requirements

- **FR-001**: El alta de dueños debe originarse exclusivamente en una invitación emitida por el administrador de plataforma.
- **FR-002**: La cuenta administradora debe crearse mediante un procedimiento controlado; no habrá registro público de administradores.
- **FR-003**: La invitación debe vincular un correo normalizado a un único dueño y registrar estado, vencimiento, emisor y uso.
- **FR-004**: Al aceptar, la persona solo define contraseña y confirmación; el correo queda fijado por la invitación.
- **FR-005**: El dueño debe completar el perfil de negocio antes de acceder al panel operativo. En esta fase solo se permite un usuario y un negocio activo por dueño.
- **FR-006**: La estructura de relación entre negocio y usuarios debe admitir miembros futuros, pero la UI y API de invitación de miembros quedan fuera de esta fase.
- **FR-007**: Invitaciones y recuperación deben usar enlaces de un solo uso, con vencimiento; las invitaciones vencen a las 72 horas y reenvío y revocación invalidan enlaces anteriores.
- **FR-008**: La recuperación debe responder sin revelar existencia de cuenta y revocar sesiones al cambiar contraseña.
- **FR-009**: `/admin` debe exigir identidad de plataforma y autorización de servidor para todas sus operaciones; los dueños conservan aislamiento por `business_id`.
- **FR-010**: El administrador debe poder listar negocios/invitaciones, reenviar, revocar, suspender y reactivar; no borrar negocios para gestionar acceso.
- **FR-011**: Las acciones administrativas sensibles deben quedar auditadas.
- **FR-012**: Las métricas deben definir periodo, estado, fuente y fórmula; el gasto debe distinguir real conciliado, estimado y no disponible.
- **FR-013**: Los eventos de mensajería usados en métricas deben persistir por negocio y ser idempotentes ante webhooks repetidos.
- **FR-014**: La UI comercial debe retirar datos demo/prueba y presentar marca, textos y componentes coherentes en acceso, alta, panel del dueño y panel de plataforma.
- **FR-015**: El correo transaccional debe salir de un dominio corporativo de Rafenixcore solo después de verificar dominio/remitente y entrega en el proveedor.
- **FR-016**: El acceso de administración debe limitar intentos fallidos a 5 por correo y 20 por IP durante una hora, con contadores persistentes y sin guardar correo o IP en claro en esa tabla.

### Key Entities

- **PlatformAdmin**: identidad y estado de acceso de quien administra la plataforma.
- **Owner**: usuario dueño identificado por correo.
- **Business**: negocio del dueño; conserva estado operativo y progreso de alta.
- **BusinessMembership**: relación entre negocio y usuario, preparada para roles futuros; solo una membresía dueña en esta fase.
- **Invitation**: invitación a dueño, con token protegido y ciclo de vida.
- **PasswordReset**: solicitud de recuperación de un solo uso.
- **AdminAuditEvent**: acción administrativa atribuible.
- **MessageEvent / CostRecord**: evidencia de envío, entrega, fallo y costo de mensajería.

## Success Criteria

- **SC-001**: Un invitado puede pasar del enlace recibido a su panel de negocio sin escribir su correo ni crear cuenta pública.
- **SC-002**: El 100 % de accesos a `/admin` y datos entre negocios se rechaza para cuentas sin permiso en pruebas de autorización.
- **SC-003**: El 100 % de invitaciones y restablecimientos usados, vencidos o revocados se rechaza en pruebas de flujo.
- **SC-004**: Los conteos del panel coinciden con los registros fuente para los periodos de prueba; ningún costo sin fuente aparece como gasto real.
- **SC-005**: En las pantallas revisadas no quedan credenciales demo, copias de prueba ni recursos genéricos del andamiaje.

## Decisiones y dependencias para revisión

- La vigencia de invitación quedó confirmada por el usuario en 72 horas. La recuperación vence en una hora y limita las solicitudes a 5 por correo y 20 por IP durante una hora; el usuario confirmó estos valores el 2026-11-09.
- El usuario confirmó el 2026-11-09 el límite de acceso administrativo de 5 intentos fallidos por correo y 20 por IP durante una hora.
- Rafenixcore es la marca corporativa indicada por el usuario. Resend presenta `rafenixcore.com` como dominio verificado y habilitado para envío; la dirección remitente y la clave del backend aún no están configuradas ni se probó entrega real.
- El usuario eligió el logo **Turno** (opción 1) y se integró en la UI. La revisión final de accesibilidad visual sigue pendiente de un recorrido con navegador.
- El costo real de WhatsApp exige evidencia y conciliación con Meta; un total calculado solo desde tarifas será estimado. La activación de recordatorios y el cambio a un único aviso a 24 horas permanecen en la fase diferida #15.
- La posibilidad futura de múltiples miembros no autoriza su UI, invitaciones ni permisos en esta entrega.
