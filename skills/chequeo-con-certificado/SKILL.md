---
name: chequeo-con-certificado
description: "Use when the person hands over an electronic certificate (.p12/.pfx) of their company or their own («te paso mi certificado», «aquí tienes el certificado de la SL y el mío», «revisa todo lo que puedas con él»), when asked «¿qué sabe Hacienda de mí?», «revísalo todo», «¿está todo en orden?», at the monthly check-up, or when reading the hallazgos of `gestoria chequeo` or `gestoria vigia`. Covers the first-day review, what each finding means and what to tell the person, everything a certificate can be used to look at (AEAT, DEHú, Seguridad Social and other sedes) and the hard limits: the check-up only reads; it never opens, files, signs, pays or revokes."
---

# Chequeo con certificado: lo que un gestor revisa el primer día

Un certificado electrónico abre casi todas las puertas de la administración. El chequeo solo
**mira**: nunca abre una notificación, ni presenta, firma, paga, revoca o cambia nada. Presentar
una declaración es otra orden, `gestoria presentar`, con su revisión, su ensayo y la conformidad de
la persona (skill `presentar-declaraciones`); lo demás lo hace la persona, y solo si quiere.

## El primer día

1. **Guardar el certificado bien.** Fuera de cualquier repositorio. La contraseña va en un fichero
   con permisos 600 (o en `$GESTORIA_CERT_CLAVE`) y nunca en el chat. En `perfil.toml`: `[sede]` es
   el principal (el de la empresa, de representante; o el suyo si es autónomo) y `[sede.personal]`
   el de persona física, si también lo da.
2. **`gestoria certificado`**: de quién es cada uno, de qué tipo (representante de persona
   jurídica o persona física) y cuándo caduca. Si el NIF del certificado no es el del perfil, la
   sede enseñará los datos de otro: arréglalo antes de seguir.
3. **`gestoria chequeo`**: lo mira todo en una pasada (unos minutos) y deja
   `salida/chequeo_AAAA-MM-DD.md` y `salida/chequeo.json`.
4. **Cuéntaselo así:** primero lo 🔴, con fecha y qué hacer; luego lo 🟡; lo 🟢 en una línea; lo ℹ️
   solo si pregunta. Cada hallazgo lleva su norma: cítala.
5. **Programa los workflows** (`workflows/crontab.ejemplo`): `gestoria vigia` cada día y
   `gestoria chequeo` el día 1 de cada mes.

## Qué mira el chequeo y qué significa cada hallazgo

| hallazgo | qué hacer o qué decir |
|---|---|
| 🔴 notificación sin abrir (AEAT o DEHú) | No se abre. Di de quién es, cuándo se puso a disposición y qué pasa si nadie la abre (skill `sede-aeat`). La decisión de abrirla es de la persona |
| 🔴 no consta presentado un 303/130 vencido | Que lo presente ya: `gestoria recargo <importe> --vencio <fecha>` dice cuánto cuesta hoy y cuánto el mes que viene |
| 🔴 deuda con la AEAT | Importe y periodo. En periodo ejecutivo el recargo sube con el tiempo (art. 28 LGT) |
| 🔴 proveedor que no está en el censo | Sin factura completa su IVA no se deduce (art. 97 LIVA): pídele la factura con el NIF bien |
| 🔴 / 🟡 certificado que caduca | Renovarlo antes de que caduque: caducado, no entra en ninguna sede |
| 🟡 poder a un tercero (GENERALNOT, GENERALLEY58…) | Quién puede recibir y abrir sus notificaciones o presentar por él, y hasta cuándo. Si ya no trabaja con esa gestoría, el poder se revoca en la sede: lo hace la persona |
| 🟡 censo y perfil no coinciden | Una obligación de alta que el perfil no lista (no se le avisará de sus plazos) o al revés (sobra en el perfil o falta el alta en el 036) |
| 🟡 régimen de IVA que GestorIA no calcula (recargo, criterio de caja, simplificado…) | El 303 se revisa a mano |
| 🟡 el 303 presentado no cuadra con los libros | `gestoria cotejar 303` lo detalla casilla a casilla. Averigua cuál está bien antes de proponer nada |
| 🟡 no está en el ROI y tiene operaciones intracomunitarias | Sin ROI los proveedores de la UE le cobran su IVA y él no puede vender sin IVA a empresas de la UE; el alta es un 036 (casilla 582), que presenta la persona |
| 🟡 SL unipersonal | La unipersonalidad tiene que constar inscrita, «Sociedad Unipersonal» en facturas y documentos, y los contratos con el socio en un libro-registro legalizado (arts. 13 y 16 LSC) |
| 🟡 pluriactividad | Si lo cotizado como autónomo y por cuenta ajena supera el tope de la Ley de Presupuestos, se devuelve el 50 % del exceso (art. 313 LGSS) |
| 🟡 cargo de la Seguridad Social cerca | Cuota y regularización, con el día del cargo: que lo tenga en la cuenta |
| 🟡 acceso a la sede sin certificado | ¿Es él? Si no, que cambie sus claves de Cl@ve |
| ℹ️ notificaciones electrónicas obligatorias | Si nadie abre una en 10 días naturales, se da por notificada (art. 43.2 Ley 39/2015): por eso el vigía mira cada día |
| ℹ️ a qué correo y móvil avisa Hacienda | El aviso es voluntario y que no llegue no frena nada (art. 41.6 Ley 39/2015). Si va a un buzón que nadie lee, que lo cambie (lo hace él, con un 036) |
| ℹ️ presentado por un tercero | Quién presentó cada 303 y en calidad de qué (colaborador social, apoderado) |
| ℹ️ datos fiscales | Lo que pagadores, bancos y clientes han declarado de él: se coteja con sus nóminas y facturas antes de la renta o del Impuesto sobre Sociedades |

## Todo lo que se puede mirar con un certificado

**Automatizado en GestorIA (solo lectura):**

| sede | qué | orden |
|---|---|---|
| AEAT | notificaciones y comunicaciones sin abrir | `gestoria notificaciones [--personal]` |
| AEAT | censo: identificación, domicilio fiscal, notificaciones electrónicas obligatorias, obligaciones, regímenes de IVA, IAE, representantes, socios, canales de aviso | `gestoria censo [--personal]` |
| AEAT | apoderamientos otorgados y recibidos | `gestoria poderes` |
| AEAT | deudas · expedientes · accesos y alertas | `gestoria deudas` · `gestoria expedientes` · `gestoria accesos` |
| AEAT | declaraciones presentadas, justificante y fichero; cotejo del 303 | `gestoria presentados --descargar` · `gestoria cotejar 303` |
| AEAT | ROI de cualquier NIF español, con CSV | `gestoria roi [NIF]` |
| AEAT | NIF y nombre de clientes y proveedores en el censo | `gestoria terceros` · `gestoria nif <NIF> <nombre> --censo` |
| AEAT | datos fiscales (renta o sociedades) · domiciliaciones | `gestoria datos-fiscales` · `gestoria domiciliaciones` |
| DEHú | notificaciones pendientes y comunicaciones de todas las administraciones adheridas | `gestoria dehu [--personal] [--realizadas]` |
| Seguridad Social | altas, cuota de autónomo, próximo cargo, regularización, días cotizados, últimos documentos | `gestoria seguridad-social` |
| VIES (sin certificado) | NIF-IVA de la UE | `gestoria vies <NIF>` |

**Con `gestoria mirar <url> [--clave]` (sin automatizar todavía; lee la pantalla y explícala):** la
Dirección General de Tráfico (puntos, vehículos, multas), el Catastro (los inmuebles de los que es
titular), la Carpeta Ciudadana (lo que las administraciones tienen de él), el SEPE, el Registro
Mercantil o la sede de su comunidad autónoma y su ayuntamiento. `--clave` entra por Cl@ve con
«DNIe / Certificado electrónico» cuando la sede lo pide. Antes de afirmar nada de esas pantallas,
enséñale a la persona la captura (`salida/capturas/`).

## Lo que nunca se hace

- Abrir o comparecer una notificación · presentar, firmar o pagar · revocar, renunciar, confirmar o
  prorrogar poderes · modificar el censo, el domicilio o una domiciliación · pedir certificados,
  aplazamientos o devoluciones · contestar requerimientos. Si una pantalla lo pide para seguir,
  GestorIA se para y lo dice.
- Pegar la contraseña del certificado en el chat, en un log o en un repositorio.
- Afirmar algo que la sede no ha enseñado: si una pantalla no se pudo leer, el chequeo lo dice
  («no he podido leer…») y se mira a mano.
