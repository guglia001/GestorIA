---
name: ayudas-y-deducciones
description: "Use when the person asks what they can deduct or write off («¿qué me puedo desgravar?», «¿esto es deducible?», «¿me puedo deducir el coche / la casa / las comidas / el seguro médico?», «¿cómo pago menos impuestos?»), which grants or subsidies they could apply for («¿hay ayudas para mí?», «subvenciones para autónomos / pymes», «Kit Digital», «tarifa plana»), or at the start of a quarter or a year when reviewing their books. Runs `gestoria deducciones` (every rule of the IRPF, VAT and corporate-tax laws checked against their books and bank, each with its article, re-read live in the BOE with --comprobar) and `gestoria ayudas` (the national subsidies database filtered by who they are, where they are and what they do). Covers how to read each finding, what to ask the person before claiming anything, and what GestorIA never does: it does not apply for a grant and does not decide that an expense is deductible."
---

# Ayudas y deducciones: lo que una gestoría con ochenta clientes no mira contigo

Dos órdenes, las dos con fuente oficial y las dos de solo lectura:

| pregunta | orden | de dónde sale |
|---|---|---|
| ¿Qué me puedo deducir? ¿Qué no? ¿Me estoy dejando algo? | `gestoria deducciones [--comprobar]` | las reglas de la LIRPF, la LIVA y la LIS (cada una con su artículo), cruzadas con `libros/compras.csv`, el banco y `perfil.toml` |
| ¿Qué ayudas o subvenciones puedo pedir? | `gestoria ayudas [--region X] [--palabras a,b] [--dias N]` | la Base de Datos Nacional de Subvenciones (art. 20 Ley 38/2003), en el momento, filtrada por pymes y autónomos, tu provincia y comunidad, y tus palabras |

## `gestoria deducciones`: cómo leerlo

Cada regla sale con un estado. Lo que le dices a la persona depende del estado, no del nombre:

| estado | qué significa | qué haces |
|---|---|---|
| ✅ ya lo usas | consta en sus libros o en su banco (N facturas, X € de base) | nada, salvo recordarle el límite si lo hay (500 € por persona en el seguro, 1 % de la cifra de negocios en atenciones) |
| ⚠️ por mirar | no consta nada que lo parezca, o se pasa de un límite, o hace falta una prueba (el coche) | **pregúntaselo**: «¿pagas seguro médico? ¿trabajas desde casa? ¿comes fuera por trabajo?». Si sí, que pida la factura a su nombre y la anote; no se añade nada a los libros sin factura |
| ℹ️ depende de ti | los libros no llevan el dato (metros de la vivienda, plantilla, si va a repartir el beneficio) | se lo explicas con la cifra estimada y la condición, y decide la persona |
| ⛔ no deduce | multas, sanciones, compras sin NIF, compras marcadas como no deducibles, IVA excluido | que no lo deduzca; si es una compra sin NIF, que pida factura completa (art. 97 LIVA) |

Reglas al contarlo:

- **El artículo va con la cifra.** «El seguro médico deduce hasta 500 € por persona (art. 30.2.5.ª.a LIRPF)», no «el seguro
  médico deduce». Con `--comprobar` la orden vuelve a leer cada artículo en el BOE y enseña el párrafo: úsalo antes de afirmar
  una cifra, y siempre que la persona vaya a tomar una decisión con ella.
- **Lo que deduce lo prueba la persona** (art. 106.4 LGT). Que un coche es de uso exclusivo, que trabaja en 20 de los 80 m² de su
  casa o que una comida fue con un cliente no lo decide GestorIA ni lo decides tú: se lo preguntas y se lo apuntas.
- **No muevas nada a los libros** por lo que diga esta orden. Si falta una factura, la pide; si sobra una deducción, la quita ella.
- **Las estimaciones llevan «con los libros de hoy».** El 5 % de difícil justificación, el 20 % de inicio, la reserva de
  capitalización o la de nivelación salen del rendimiento acumulado hasta hoy, no del año entero.
- **Lo que no está:** amortizaciones (no se calculan todavía), módulos, regímenes especiales distintos del REBU, deducciones
  autonómicas de la renta. Si pregunta por eso, `gestoria manuales` y `gestoria boe`, con la cita (skill `normativa-fiscal`).

## `gestoria ayudas`: cómo leerlo

- `perfil.toml` → `[ayudas] region` (como la llama la BDNS: «Madrid», «Mallorca», «Comunidad Valenciana») y `palabras` (lo que
  describe la actividad). Sin región solo salen las de ámbito estatal: dilo y pídesela.
- Cada convocatoria sale con 🟢 abierta hasta una fecha, 🟡 abre después, ⚪ sin fecha estructurada (el plazo está en las bases:
  léelo ahí antes de decir nada) o 🔴 cerrada. Con el órgano, el presupuesto, el enlace a la BDNS, a las bases y a la sede donde se
  pide.
- **Las bases mandan.** La BDNS resume; los requisitos (tamaño, sector, antigüedad, estar al corriente con Hacienda y la Seguridad
  Social) están en las bases. Antes de decir «te la puedes pedir», lee las bases (`gestoria mirar <url>` si la sede lo permite) y
  mira `gestoria deudas` y `gestoria seguridad-social`: casi todas exigen estar al corriente.
- **Las que no están en la BDNS:** la cuota reducida de nuevos autónomos (art. 38 ter Ley 20/2007) se pide al darse de alta en la
  Seguridad Social, y las ventajas fiscales (el 15 % de nueva creación, la reducción del 20 % por empezar, las reservas de
  capitalización y nivelación) son de `gestoria deducciones`.
- **Programa `gestoria ayudas` el día 1 de cada mes** (`workflows/crontab.ejemplo`) y cuéntale solo las nuevas y abiertas.

## Lo que nunca se hace

- Pedir una ayuda, firmar una solicitud o rellenar un formulario en la sede de un órgano: lo hace la persona. GestorIA no solicita,
  no presenta y no firma fuera de `gestoria presentar`.
- Dar por deducible un gasto sin su factura completa, o un coche o una vivienda sin la prueba de afectación.
- Dar una cifra de memoria cuando `--comprobar` o `gestoria boe` la pueden leer en el BOE.
- Inventar una ayuda: si la BDNS no la tiene y la persona la ha visto en un blog, se busca por su nombre (`--palabras "kit digital"`)
  y, si no aparece, se dice que no consta publicada.
