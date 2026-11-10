# Investigación y decisiones de diseño

**Nota de vigencia:** este inventario describe el estado inicial antes de implementar la fase 007. Para el estado actual, consultar [tasks.md](tasks.md) y [security-review.md](security-review.md).

## Estado comprobado

- **Cuenta de dueño**: `backend/api-backend/app/models.py` define `Owner` con nombre, correo, contraseña hasheada y verificación; no tiene rol de plataforma ni estado de suspensión. `verification_token` se guarda sin hash. La relación `Owner.businesses` usa cascada de borrado, por lo que suspender nunca debe implementarse borrando Owner.
- **Negocios**: `Business.owner_id` vincula un negocio a su dueño y existe `is_active`, pero no hay marca de alta completa. `POST /api/businesses/` rechaza crear si el dueño ya tiene cualquier negocio, también si está inactivo; esto es más estricto que «un negocio activo por dueño» y debe resolverse como decisión funcional antes de cambiarlo.
- **Registro y login**: `backend/api-backend/app/api/auth.py` expone `POST /register`, verificación y resend; no hay invitación ni recuperación. Con `REQUIRE_EMAIL_VERIFICATION=false` se crea la cuenta como verificada y se emiten tokens de acceso/refresh. `frontend/src/App.tsx` expone `/register` y `/verify-email`.
- **Autorización**: `get_current_owner` decodifica JWT, rechaza `token_kind=refresh` y busca por correo, pero no valida estado de cuenta ni rol. Actualmente la UI no tiene ruta `/admin` para plataforma. Las rutas de negocio filtran por `owner_id`, patrón que se debe preservar.
- **Alta y UI (inventario T001; backend actualizado en T008)**: `BusinessOnboarding.tsx` pide nombre y teléfono (obligatorios), dirección y descripción (opcionales). T008 añadió guard de backend para negocio activo y alta completa en rutas operativas; la UI de alta y sus bloqueos visuales se ajustarán en T013. El login tiene icono `Sparkles`, enlace a registro, credenciales demo, copyright 2025 y hora de build.
- `app/api/dashboard.py` solo entrega métricas de un negocio con comprobación de propiedad. Su campo `revenue` suma precios de servicios en citas confirmadas/completadas: no prueba cobro. `occupancy_rate` es proporción de citas, no capacidad ocupada. `new_customers` cuenta clientes distintos con cita del mes, no necesariamente clientes nuevos.
- **Correo**: `app/services/email_service.py` usa SMTP solo para verificación; si `SMTP_HOST` falta, registra en logs la dirección y el enlace con token. No hay integración runtime de Resend. `.env.example` contempla SMTP; el `.env` local inspeccionado no define variables SMTP/Resend. Un MCP de Resend no conecta por sí mismo el runtime. Producción revisada previamente tenía verificación desactivada y SMTP no configurado.
- **Datos reales**: no se obtuvo conteo de cuentas/negocios en Neon en esta revisión; no hay MCP de Neon disponible en la sesión. Las afirmaciones anteriores son del esquema y código, no de cantidades de producción.
- En Pacelas se comprobó invitación con token hasheado de 72 h, recuperación de una hora, un solo uso, respuesta neutral y revocación de sesiones. Se reutiliza el patrón de seguridad y recorrido, no su rol de vendedor ni su panel.
- El sistema no tiene una contabilidad durable de mensajes y cargos por negocio. Logs de estado no bastan para declarar gasto real.

## Decisiones técnicas propuestas

### Identidad y autorización

**Decisión**: identidad administrativa de plataforma separada de `Owner`, con credencial y sesiones propias o tokens explícitamente tipados. Las dependencias del backend deben rechazar un token de dueño en endpoints de plataforma y viceversa. Un primer administrador se crea por bootstrap controlado e idempotente, con secreto no registrado en logs.

**Motivo**: `get_current_owner` hoy significa dueño de negocio; añadir acceso global a esa identidad sin frontera explícita aumenta riesgo de fuga entre negocios.

**Alternativa examinada**: una columna `is_admin` en `Owner`. Se descarta para esta fase porque hace ambiguos los flujos existentes de propiedad y permite errores en rutas que ya aceptan cualquier `Owner`.

### Invitación y alta

**Decisión**: invitación creada por administrador, correo fijado, token aleatorio almacenado solo como hash, estado explícito y consumo atómico. La aceptación define contraseña y confirma la cuenta; el negocio se completa en la pantalla de alta existente adaptada. La cuenta incompleta permanece restringida aunque tenga sesión.

**Motivo**: corresponde al recorrido acordado y conserva la regla de un negocio por dueño. El reenvío invalida el token anterior; la revocación no elimina auditoría.

**Parámetros históricos de esta investigación**: aquí se propusieron 72 h de invitación y 1 h de recuperación. Ambos plazos fueron confirmados posteriormente por el usuario; la regla vigente está en [spec.md](spec.md).

### Miembros futuros

**Decisión**: prever una relación negocio-usuario con rol, pero crear en esta fase una sola membresía `owner`. No exponer altas de personal ni crear permisos ficticios para roles futuros.

**Motivo**: prepara la ampliación sin cambiar el producto MVP ni romper el aislamiento por `business_id`.

### Correo corporativo

**Decisión**: integrar envío transaccional mediante Resend en desarrollo y usar un remitente verificado de dominio Rafenixcore. Verificar dominio/DNS en Cloudflare solo cuando se determine la zona exacta; usar MCP para inspección y configuración autorizada entonces. Mantener salida explícita de error si no se puede enviar, sin imprimir enlaces de producción en logs.

**Motivo**: el SMTP actual no está operativo en la configuración de producción observada. Un MCP conectado es una herramienta de gestión, no un servicio de envío para el runtime.

**Pendiente**: dominio exacto, dirección remitente, acceso a la zona DNS y pruebas de entrega. No configurar DNS en esta planificación.

### Métricas y gasto

**Decisión**: construir métricas de negocio/citas desde datos persistidos con definiciones nuevas. Para mensajes, persistir eventos de salida y webhooks con identificador único, negocio, canal, categoría cuando conste, estado y fecha. Mostrar costo estimado solo con tarifa y categoría verificadas; mostrar gasto real solo tras importar o conciliar una fuente de facturación de Meta. Si falta cobertura, presentar `No disponible` y el motivo.

**Motivo**: las métricas actuales tienen etiquetas imprecisas y no existe una fuente de cargos por mensaje. Meta/WhatsApp puede no exponer un costo exacto por cada webhook de estado.

**Alternativa examinada**: multiplicar entregas por una tarifa fija y titularlo «gasto». Se descarta porque categoría, país, vigencia, facturación y ajustes pueden cambiar el total.

### Identidad visual

**Decisión**: diseñar un símbolo propio para SmartBooking bajo firma discreta «Rafenixcore», con versión horizontal, cuadrada y monocroma. Mantener la marca principal del producto en acceso y navegación; probar legibilidad en favicon y móvil. Definir tokens compartidos de color, tipografía, espaciado y estados de formulario antes de remodelar pantallas.

**Motivo**: el icono Sparkles y el favicon de Vite no identifican el producto; hay estilos inconsistentes y datos demo visibles. El logo final requiere revisión visual del usuario antes de incorporarse.

## Límites de esta fase

- No activar cron ni modificar recordatorios; la decisión de un solo recordatorio a 24 horas sigue registrada en #15.
- No dar de alta miembros del negocio todavía.
- No mostrar ingresos cobrados, ocupación real ni gasto real sin fuente que los sostenga.
- No operar servicios externos durante la planificación; las comprobaciones de Resend, Cloudflare, Railway y Meta son tareas de desarrollo con autorización de esa fase.
