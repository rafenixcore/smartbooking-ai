# Revisión de UI comercial — SmartBooking

**Estado:** inventario completado; login, campos y copia comercial inicial actualizados; el usuario seleccionó **Turno (opción 1)** el 2026-11-09 y su identidad ya se integró en la UI y el correo.
**Alcance revisado:** rutas/componentes fuente de `frontend/src`; inspección estática, sin capturas de navegador.

## Inventario de pantallas y flujo

| Ruta o pantalla | Componentes | Campos/acciones principales | Hallazgos |
|---|---|---|---|
| `/login` | `Login.tsx` | correo, contraseña, recuperación, acceso | Mantiene registro cerrado por invitación, pero usa una composición y adornos distintos al resto; pie con año fijo y timestamp de build visible. Icono `Sparkles` en bloque degradado es genérico y no es logo de producto. |
| `/invitation` | `AcceptInvitation.tsx` | correo fijado, contraseña, confirmación | El correo se presenta solo lectura y el enlace sigue el flujo acordado. Tarjeta y campos ya reutilizan componentes comunes. |
| `/forgot-password`, `/reset-password` | páginas de recuperación | correo; contraseña y confirmación | Flujo separado; requiere misma identidad, jerarquía, anchura de control y tono de mensajes que login/invitación. |
| `/admin/login` | `platform/AdminLogin.tsx` | correo de administrador, contraseña | Es una identidad separada y correcta; usa `ShieldCheck` como icono temporal genérico, no una marca final. |
| `/admin/*` | `platform/AdminLayout.tsx` y páginas hijas | resumen, negocios, invitaciones, métricas, actividad | Navegación administrativa está separada del dueño. Hay dos cuadrados «SB» construidos como texto y un pie con marca de plataforma, sin símbolo propio. |
| Alta inicial del negocio | `BusinessOnboarding.tsx` | nombre y teléfono obligatorios; dirección y descripción opcionales | El flujo indica cómo continuar, pero `Telegram dedicado` aparece como beneficio aunque la integración todavía requiere configuración; debe quedar como capacidad/configuración, no como hecho automático. |
| `/dashboard` | `Dashboard.tsx` | preparación del negocio y accesos operativos | El paso «Primera cita» instruía crear una cita «de prueba», lenguaje de demo que no corresponde a un producto activo. |
| Navegación del dueño | `Sidebar.tsx`, `DashboardLayout.tsx` | agenda, servicios, clientes, horarios, integración y salida | Marca solo textual; revisar etiquetas junto al usuario durante T030. |
| Reserva pública | `PublicBookingLayout.tsx` | encabezado y pie del flujo público | Usa «SmartBooking Platform», nombre distinto de «SmartBooking AI» usado en otras pantallas. |

## Hallazgos visuales y de contenido

- La identidad se comunica con `Sparkles`, `ShieldCheck`, `Store`, cuadros «SB» y texto SmartBooking. Ninguno constituye un logo propio y coherente entre acceso, panel, correo y navegador.
- `frontend/index.html` aún carga `frontend/public/vite.svg`; `frontend/src/assets/react.svg` también es un recurso heredado, aunque no está conectado al flujo comercial revisado.
- La paleta parte de azul zafiro, violeta y ámbar, pero el login añade degradados, animación de blobs y resplandores distintos del panel. Conviene conservar un azul confiable, limitar los acentos y retirar decoración que compite con el formulario.
- `Input` mide 44 px y usa borde de 2 px; `Select` mide 40 px y no asocia explícitamente su etiqueta con el control. Formularios propios repiten estilos y sus pesos/espaciado varían.
- Hay texto de demostración «cita de prueba» en el checklist del dashboard. «Bandeja de prueba» aparece como instrucción después de enviar invitación y puede hacer creer que siempre se usa un sandbox de Resend; debe describir el estado de entrega sin asumir entorno.
- `/test-ui` y `TestUI.tsx` son una ruta de desarrollo habilitada solo con `import.meta.env.DEV`; no se usa como pantalla comercial de producción. Mantenerla fuera del flujo de clientes.
- El inventario no valida renderizado visual en navegador ni entrega real de correo. Esas comprobaciones quedan para las tareas de UI y de entrega correspondientes.

## Dirección de diseño propuesta

1. Mantener SmartBooking como nombre de producto y Rafenixcore como empresa propietaria; quitar «AI» o «Platform» de los nombres visibles salvo que el usuario decida conservarlos.
2. Usar formularios simples, una columna, títulos directos, etiqueta visible, ayuda solo cuando resuelve una duda y una acción principal por pantalla.
3. Unificar controles a 44 px, radio de 10–12 px, borde fino, foco visible y errores asociados al campo. Mantener contraste y funcionamiento con teclado.
4. Adoptar la paleta de Turno: azul `#2563EB` y turquesa `#0EA5A4` para la marca, con ámbar `#FBBF24` reservado al punto de cita y acentos puntuales.
5. Retirar timestamp de build y textos de prueba del flujo visible; explicar el siguiente paso real después de invitación y alta.

## Propuestas de símbolo y wordmark

Ver [logo-proposals.svg](logo-proposals.svg). Presenta tres rutas visuales con variantes claro/oscuro: **Turno** (cita y tiempo), **Enlace** (flujo entre negocio y cliente) y **Ritmo** (agenda modular). El usuario eligió **Turno**, un calendario blanco con punto de cita ámbar sobre fondo azul-turquesa. La integración usa un SVG local para conservar nitidez; los correos usan wordmark y paleta en HTML compatible, sin depender de imágenes remotas.

## Cambios de UI realizados después del inventario

- Login simplificado, sin animación decorativa ni timestamp de build; mantiene enlace de recuperación y explica la invitación.
- Las entradas y selecciones comparten altura, borde, etiqueta, foco y asociación del error.
- El checklist del negocio habla de crear o recibir una cita real; el alta etiqueta Telegram como integración, sin decir que ya está activada.
- El resultado de invitación explica que el proveedor aceptó el envío y recomienda revisar correo/spam; ya no presupone una bandeja de prueba.
- El título del resumen del dueño quedó en español; el pie público usa SmartBooking y Rafenixcore.
- Se reemplazaron `vite.svg`, los cuadros «SB» y los iconos genéricos de marca en login, navegación, administración y reserva pública con el símbolo Turno.
- El título y descripción del documento ahora presentan SmartBooking como producto; los correos de invitación, recuperación y verificación comparten el wordmark y la paleta de la marca.
- Las pantallas de invitación y recuperación usan también Turno en sus estados principales; el resultado de recuperación ofrece acceso al negocio y a `/admin`.
- Los campos de contraseña tienen control accesible para mostrar u ocultar el valor, útil al aceptar una invitación y al restablecer la contraseña.
