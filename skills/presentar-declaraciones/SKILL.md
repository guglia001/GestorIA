---
name: presentar-declaraciones
description: "Use when the person wants a tax return actually filed in the AEAT's sede — «preséntalo», «presenta el 303», «envíalo a Hacienda», «hazlo tú», «¿lo puedes presentar?» — or asks what GestorIA checks before filing, about the AEAT test environment (preproducción, ensayo), the conformity phrase, paying or direct-debiting a return, a filing that failed halfway, or signing a document with AutoFirma. Runs the full pre-filing review, investigates every warning in the AEAT manuals and the BOE, rehearses the filing in the AEAT test environment and files only with the person's explicit conformity for that return; then checks what was filed."
---

# Presentar: la revisión, el ensayo y la conformidad

GestorIA presenta una declaración solo con **tres llaves**, y en este orden:

1. **La revisión entera, limpia (ningún ⛔).** `gestoria presentar 303 --ejercicio AAAA
   --periodo NT`, sin `--conforme`, solo revisa. Comprueba el período, los libros y el borrador, y
   lee en el momento los manuales prácticos de la AEAT y la Ley del IVA en el BOE de lo que lleve el
   trimestre (REBU, adquisiciones intracomunitarias, rectificativas, inversiones). Cuadra el saldo a
   compensar con el 303 anterior PRESENTADO. En la sede mira el censo, si ya está presentado y si
   hay notificaciones sin abrir. Calcula el plazo y el recargo, mira cómo se paga y pasa el fichero
   por el simulador de la AEAT.
2. **Un ensayo bueno de ese mismo fichero.** Con `--pruebas --conforme "<frase>"` hace la
   presentación entera en el entorno de pruebas de la AEAT (prewww1/prewww2.aeat.es) hasta el
   justificante, y ahí lo presentado «no tiene en ningún caso trascendencia tributaria». Cada ensayo
   queda en `salida/presentado/presentaciones.json` con la huella del fichero, y vale una semana.
   Si cambia una casilla, cambia el fichero y hay que ensayarlo otra vez.
3. **La conformidad de la persona para ESA declaración.** La revisión da la frase exacta:
   `PRESENTAR 303 3T 2026 <NIF> 67,60` (modelo, período, NIF y resultado). Cuando la persona te
   dice que presentes esa declaración, su orden es la conformidad y tú ejecutas
   `gestoria presentar 303 … --conforme "<frase>"`. Una orden general («preséntalo todo», «haz lo
   que haga falta») no vale para una declaración que no ha visto. Si cambia el resultado, cambia la
   frase y vuelves a preguntar.

## Paso a paso

1. **La revisión.** Lee cada línea a la persona en lenguaje claro y empieza por los ⛔.
2. **Cada ⚠️ se investiga antes de seguir**:
   - `gestoria manuales "<tema>"` para leer la página entera del manual de la AEAT que cita la
     revisión;
   - `gestoria boe <id> <artículo>` para el artículo;
   - si hace falta, las consultas vinculantes de la DGT
     (https://petete.tributos.hacienda.gob.es), con su número y fecha.

   Dile qué has encontrado y qué significa para su declaración (skill `normativa-fiscal`).
3. **Los ⛔ se arreglan, no se saltan.** Los típicos:
   - **pago**: sale a ingresar y no se puede domiciliar. Que pague en su banco y te dé el NRC
     (`--nrc`), o que domicilie (`[iva] forma_pago = "U"` y `[pago] iban`) hasta 5 días naturales
     antes del fin del plazo.
   - **compensación**: `compensar_pendiente` de `ajustes.toml` no cuadra con el 303 anterior
     presentado. Corrígelo con la línea que da `gestoria cotejar 303` de ese período.
   - **ya presentado**: cambiarlo es una autoliquidación rectificativa, que GestorIA no hace.
     Cotéjalo (`gestoria cotejar 303`) y cuéntaselo.
   - **simulador o libros con errores**: se corrigen en los libros y se repite la revisión.
   - **período sin terminar**: se presenta desde el día 1 del mes siguiente.
   - **sin sede o sin simulador**: para presentar de verdad no valen `--sin-sede` ni
     `--sin-simulador`.
4. **El ensayo.** No tiene efectos, así que lo puedes lanzar tú en cuanto la revisión salga
   limpia. Si se para, mira las capturas de cada paso en `salida/capturas/presentar_pruebas_*` y
   cuéntaselo antes de tocar nada.
5. **La conformidad.** Enséñale:
   - el resultado y si sale a ingresar, a compensar o a devolver;
   - cómo se paga (domiciliado en la cuenta …1234 el último día del plazo, o el NRC);
   - el plazo;
   - lo que has investigado;
   - la frase.

   Solo con su sí para ESA declaración, `--conforme "<frase>"`.
6. **Después.**
   - El justificante (PDF, con su CSV) queda en `salida/presentado/`.
   - GestorIA baja lo presentado y lo coteja con los libros: debe decir «coincide al céntimo».
   - Actualiza `ajustes.toml`: `compensar_pendiente` del siguiente (la línea de
     `gestoria cotejar 303`) y, si es autónomo, lo ingresado en `[pagado_este_anio]`.
   - Confírmalo con `gestoria presentados`.

## Si algo falla a mitad

- **«Parado en …, sin enviar nada»**: no se pulsó el último «Firmar y Enviar». Se arregla lo que
  diga y se vuelve a empezar.
- **«❓ NO sé si ha llegado»**: se pulsó «Firmar y Enviar» y algo falló después. **No se reintenta
  nunca** sin mirar antes `gestoria presentados --modelo 303`. Dos presentaciones del mismo período
  no se arreglan con una tercera.

## El dinero

GestorIA no hace transferencias ni usa la banca para pagar.

| sale | cómo | qué hace GestorIA |
|---|---|---|
| a ingresar, en plazo de domiciliación | `[iva] forma_pago = "U"` y `[pago] iban` | lo pone en la declaración; la AEAT carga el último día del plazo |
| a ingresar, fuera de ese plazo | la persona paga en su banco o con cargo en cuenta en la sede | presenta con el NRC que le da (`--nrc`) |
| a compensar (1T-3T) | nada | anota el saldo para el siguiente |
| a devolver (4T) | `[pago] iban` | lo pone en la declaración |

## Qué se presenta hoy

El **303**, que GestorIA genera, revisa y ensaya. Para los demás modelos (130, 111, 115, 349,
390, 200…) GestorIA todavía no genera el fichero, así que no los presenta. Ayúdale a prepararlos y
los presenta la persona (`gestoria calendario`, `gestoria recargo`).

## Firmar documentos con AutoFirma

La AEAT no la necesita: sus declaraciones se firman en su propio diálogo. Para lo demás está
`gestoria firmar <fichero>`. Firma con AutoFirma y el certificado de la persona: PAdES un PDF,
Facturae una factura electrónica, XAdES otro XML y CAdES lo demás. Cada firma es una orden suya
para ese documento.

## Errores típicos

- **Presentar porque «ya estaba revisado ayer».** La revisión se repite el día que se presenta:
  el plazo, el pago y la sede cambian.
- **Saltarse el ensayo «porque es el mismo de siempre».** El ensayo prueba las pantallas de hoy de
  la AEAT, que cambian sin avisar.
- **Tomar «preséntalo todo» como conformidad.** La conformidad es para una declaración que la
  persona ha visto, con su resultado.
- **Reintentar tras un error a mitad.** Primero `gestoria presentados`.
- **Domiciliar fuera de plazo.** La revisión lo para; no se cambia a «ingreso» sin el NRC.
