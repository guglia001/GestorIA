---
name: sede-aeat
description: "Use when something must be checked in a Spanish administration's electronic office with the person's certificate — notifications from Hacienda or any other body («¿me ha llegado algo?», requerimiento, comprobación, DEHú), what has really been filed and by whom, which obligations and VAT regimes are registered in the census, who holds powers of attorney, debts, open procedures, the ROI, the Seguridad Social (Import@ss) — or when validating a 303 file in the AEAT simulator, or when tempted to open a notification, file, sign, pay or revoke anything outside `gestoria presentar`."
---

# Las sedes con certificado: leer sí; presentar, solo con `gestoria presentar`

Leer en una sede no tiene riesgo. Estas acciones tienen efectos legales y las órdenes de lectura no
las hacen nunca (el navegador las bloquea por su nombre, y si una pantalla las pide para seguir, se
para):

- **Abrir una notificación** (en la DEHú, «comparecer»). Cuenta como notificada y arranca el plazo
  para contestar o recurrir (art. 43.2 Ley 39/2015). La abre siempre la persona.
- **Presentar una declaración.** Solo `gestoria presentar`, que abre el navegador en modo
  presentar con una lista cerrada de botones («Confirmar», «Firmar y Enviar», «Conforme»), tras la
  revisión entera, el ensayo en el entorno de pruebas de la AEAT y la conformidad de la persona para
  esa declaración (skill `presentar-declaraciones`).
- **Pagar, revocar, renunciar, confirmar o prorrogar poderes; modificar el censo, el domicilio o
  una domiciliación; solicitar certificados o aplazamientos; contestar requerimientos.** Lo decide y
  lo hace la persona.

## Qué orden responde a cada pregunta

| pregunta | orden | de dónde sale |
|---|---|---|
| ¿me ha llegado algo? | `gestoria notificaciones` y `gestoria dehu` | AEAT: resumen y listado sin abrir · DEHú: lista de pendientes de todas las administraciones (su API, sin comparecer) |
| ¿qué tengo de alta, en qué régimen, dónde me notifican? | `gestoria censo` | «Mis datos censales», «Mis obligaciones», «Mi situación tributaria», IAE, representantes, socios, canales de aviso |
| ¿quién puede actuar por mí? | `gestoria poderes` | registro de apoderamientos de la AEAT (otorgados y recibidos) |
| ¿debo algo? | `gestoria deudas` | «Pagar / consultar deudas» (solo consulta) |
| ¿hay algún procedimiento abierto? | `gestoria expedientes` | «Mis expedientes» |
| ¿quién ha entrado en mi sede? ¿hay alertas? | `gestoria accesos` | «Mis últimos accesos» y «Mis alertas» |
| ¿qué está presentado y quién lo presentó? | `gestoria presentados --descargar` | consulta de declaraciones presentadas: justificante (PDF) y fichero presentado |
| ¿lo presentado cuadra con mis libros? | `gestoria cotejar 303` | el fichero presentado leído con el diseño de registro oficial |
| ¿estoy (o está mi proveedor) en el ROI? | `gestoria roi [NIF]` | consulta de operadores intracomunitarios españoles: responde con un certificado con CSV |
| ¿los NIF de mis clientes y proveedores existen? | `gestoria terceros` · `gestoria nif <NIF> <nombre> --censo` | servicio web oficial de comprobación de NIF |
| ¿qué han declarado de mí? | `gestoria datos-fiscales` | datos fiscales de la renta (persona) o del Impuesto sobre Sociedades |
| ¿qué me van a cargar? | `gestoria domiciliaciones` · `gestoria seguridad-social` | domiciliaciones de la AEAT · cuota de autónomo y regularización en Import@ss |
| todo a la vez | `gestoria chequeo` | skill `chequeo-con-certificado` |
| otra pantalla cualquiera | `gestoria mirar <url> [--clave]` | la que digas, en solo lectura, con texto y captura |

`--personal` en las órdenes de la AEAT usa el certificado de persona física (`[sede.personal]`).

## Si aparece una notificación sin abrir

1. **No la abras.** Apunta de quién es, el concepto y la fecha de puesta a disposición (en la AEAT
   sale como «emitida»).
2. **Mira si para esa persona la vía electrónica es obligatoria** (`gestoria censo`: «Obligado a
   notificaciones electrónicas») o la eligió («suscrito voluntariamente»):
   - **Sí**: si nadie la abre en **10 días naturales** desde la puesta a disposición, se entiende
     rechazada (art. 43.2 Ley 39/2015) y el trámite se da por efectuado (art. 41.5). Calcula ese día.
   - **No**: le llega también en papel, y cuenta la primera de las dos (arts. 41.7 y 42.1). Abrirla
     en la sede le da por notificado ese mismo día. No hay rechazo a los 10 días.
3. Avisa a la persona enseguida con esos datos. Si alguien tiene un poder para recibir sus
   notificaciones (`gestoria poderes`, trámite GENERALNOT), ese alguien puede abrirla antes.
4. Se abre solo cuando la persona lo decida, y la abre ella.

## Sin certificado: el simulador público (OPEN)

`gestoria validar 303 <fichero> --ejercicio AAAA` importa el fichero en el simulador del 303 de
la AEAT, el mismo formulario de la sede pero sin poder presentar. Lee «Errores y avisos» y, si no
hay errores, las casillas que **recalcula el propio formulario**, y las coteja con las del fichero.
- «00001 No existen errores» con el ✔ verde = válido.
- «E010072 Declarante no identificado» = el NIF no está en el censo (normal con los ejemplos
  inventados). Con un NIF inventado el formulario no abre sus páginas y no se pueden cotejar.
- «31190 Revise… Información adicional» es un aviso habitual, no un error.

## Certificados y contraseñas

`perfil.toml`: `[sede] certificado` y `clave_fichero` (el principal) y, opcional, `[sede.personal]`.
La contraseña va en un fichero con permisos 600 o en `$GESTORIA_CERT_CLAVE`
(`$GESTORIA_CERT_CLAVE_PERSONAL`). No se imprime, no se pega en el chat y no va a ningún repo.
`gestoria certificado` dice de quién es cada uno y cuándo caduca: con el certificado caducado no
se entra en ninguna sede.

## Errores comunes

- **Abrir una notificación «para ver qué es».** Arranca los plazos.
- **«La gestoría dice que…».** Se comprueba con `gestoria presentados` o `gestoria censo`.
- **«No me ha llegado ningún aviso por correo».** Los avisos son voluntarios y que no lleguen no
  frena la notificación (art. 41.6 Ley 39/2015): mira `gestoria notificaciones` y `gestoria dehu`.
- **Mirar solo la sede de la AEAT.** Las multas, el ayuntamiento o la Seguridad Social notifican
  en la DEHú: `gestoria dehu`.
