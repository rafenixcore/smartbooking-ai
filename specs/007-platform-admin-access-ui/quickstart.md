# Recorrido de verificación previsto

Los recorridos funcionales siguen siendo las comprobaciones de aceptación manuales. La aplicación está desplegada en Railway y Vercel, y Neon tiene la revisión `c8e3d4f5a601`. La navegación directa a `/admin`, `/invitation` y `/reset-password`, y CORS, se verificaron. Los hallazgos R1–R6 de T035 se corrigieron y probaron localmente. Resend está configurado en Railway y una prueba directa llegó al estado `delivered`; aún falta comprobar los mensajes generados por los flujos de invitación y recuperación desde la aplicación. Ver [security-review.md](security-review.md).

1. Crear administrador mediante procedimiento controlado; verificar que el registro público no permite crear otro administrador ni dueño.
2. Entrar a `/admin`, invitar un correo nuevo y comprobar estado `pendiente`; verificar que `delivery_status=sent` significa aceptado por Resend y comprobar por separado entrega en una bandeja de prueba desde un remitente Rafenixcore verificado. El enlace usa `/invitation#token=...` para que el navegador no envíe el token en la solicitud de página.
3. Abrir invitación: correo fijado, solo contraseña y confirmación. Abrir de nuevo el mismo enlace: rechazo. Reenviar y comprobar que el enlace viejo falla.
4. Entrar como dueño: aparece alta del negocio con nombre y teléfono obligatorios; abandonar y reingresar para comprobar reanudación. Completar y verificar que solo ve su negocio.
5. Pedir recuperación con un correo existente y otro inexistente: mismo mensaje público. Usar enlace una vez; comprobar vencimiento y revocación de sesiones.
6. Suspender negocio desde `/admin`; verificar que el dueño no puede operar con sesión previa. Reactivar y comprobar acceso. Revisar bitácora.
7. Crear citas y eventos de mensajería en entorno de prueba; comparar conteos globales y por negocio. Simular duplicados y eventos sin tarifa; costo no debe aparecer como real.
8. Revisar móvil y escritorio: login, aceptación, recuperación, alta, dueño, `/admin`, correo, favicon. Buscar credenciales demo, «prueba», marca de tiempo de compilación, registro público y recursos genéricos.

## Comprobaciones externas durante desarrollo

- Resend: dominio verificado, remitente configurado y entrega directa probada; falta validar invitación/recuperación desde la app.
- Cloudflare: no cambiar DNS si el dominio continúa verificado en Resend; inspeccionar la zona solo si aparece un fallo DNS que requiera intervención.
- Railway/Vercel: verificar variables necesarias y URLs de retorno durante el despliegue; no registrar secretos.
- Meta: fuente de facturación y cobertura necesaria para cualquier cifra de gasto real.
