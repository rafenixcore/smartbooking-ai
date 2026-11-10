# Checklist de calidad: acceso, administración y UI

**Fecha**: 2026-11-09
**Especificación**: [spec.md](../spec.md)

## Contenido

- [x] Historias, actores y alcance de fase 1 definidos.
- [x] Flujo acordado: correo como usuario, solo contraseña al aceptar, alta de negocio después.
- [x] Un usuario por negocio ahora; preparación futura de miembros sin exposición.
- [x] Separación entre `/admin` y panel de dueño.
- [x] Casos límite, permisos y criterios verificables.
- [x] Estado de métricas y costo condicionado a evidencia.
- [x] UI, logo y datos demo incluidos.
- [x] Dependencias de Resend, Cloudflare y Rafenixcore identificadas sin asumir dominio exacto.

## Decisiones de implementación y publicación

- [x] Aprobar 72 horas para invitación y una hora para recuperación. Ambos valores fueron confirmados por el usuario; el 2026-11-09 también confirmó 5 solicitudes por correo y 20 por IP cada hora para recuperación.
- [x] Usar `rafenixcore.com` para correo corporativo; Resend confirmó el dominio y se configuró el remitente `SmartBooking <no-reply@rafenixcore.com>` en Railway el 2026-11-10.
- [x] Aprobar Turno, propuesta 1, como logo de producto; el usuario la eligió el 2026-11-09 y se integró en UI y correo.
- [x] No presentar gasto de Meta como real durante esta fase: sin conciliación con una fuente de facturación, el panel lo marca «no disponible» o muestra una estimación identificada como tal. La integración contable queda fuera de esta fase.

El secreto de Resend vive solo en Railway y no se guarda en este checklist ni en el repositorio.
