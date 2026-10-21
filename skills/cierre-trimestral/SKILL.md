---
name: cierre-trimestral
description: "Use when preparing the quarterly VAT return (modelo 303) of a Spanish SL or autónomo — «prepara el 303», «¿cuánto me sale el IVA?», «cierra el trimestre», the first days of January, April, July or October — when the person has just filed it and the books must be updated, or when checking a 303 prepared or filed by a gestoría against the books."
---

# Cierre trimestral del IVA (303)

## Pasos

0. **Libros limpios:** `gestoria revisar`. Un ❌ (número repetido, NIF mal, cuota que no cuadra,
   rectificativa sin original) se corrige antes de seguir; un ⚠️ se comenta con la persona. Con
   certificado, `gestoria terceros` comprueba además que los NIF de clientes y proveedores existen
   en el censo con ese nombre.
1. **Plazo:** `gestoria calendario --solo-obligatorios`. El 303 del 1T-3T vence el día 20 del
   mes siguiente; el del 4T, el 30 de enero (art. 71.4 RIVA); si cae en fin de semana o festivo,
   el siguiente hábil (lo dice el calendario oficial).
2. **Libros completos:** todas las facturas emitidas del trimestre en `libros/ventas.csv` y las
   recibidas con IVA deducible en `libros/compras.csv`. Las rectificativas, en el trimestre de
   **su** fecha (art. 89 LIVA), con la columna `rectifica`.
3. **Saldo a compensar:** `ajustes.toml` → `compensar_pendiente` = la casilla [110] que toca: lo
   que quedaba pendiente en el 303 anterior presentado ([87]) **más** lo que ese 303 salió a
   compensar (su [71] en negativo, salvo en el 4T, que se devuelve). Con su fuente: el justificante
   o el fichero presentado, nunca un borrador. `gestoria cotejar 303` escribe la línea exacta.
4. **`gestoria trimestre`** (o `--ejercicio AAAA --periodo NT`): borrador, fichero, validación en
   el simulador de la AEAT y resumen en `salida/trimestre_AAAA_NT.md`.
5. **Revisa los avisos** con la persona: márgenes REBU negativos, costes que faltan, facturas
   sin IVA desglosado, compras de menos de 3.005,06 € marcadas como inversión (para el IVA van con
   los corrientes, art. 108.Dos.5.º LIVA). Y dile **cuánto tiene que tener en la cuenta** ese día:
   es la partida «IVA … (cerrado, pendiente de presentar)» de `gestoria hucha`.
6. **Presentarlo**, con las tres llaves (skill `presentar-declaraciones`):
   `gestoria presentar 303 --ejercicio AAAA --periodo NT` hace la revisión entera (libros, manuales
   y BOE, compensación contra el 303 anterior presentado, censo, si ya está presentado, plazo, pago
   y simulador) y da la frase de conformidad. Con `--pruebas --conforme "<frase>"`, el ensayo en el
   entorno de pruebas de la AEAT, sin efectos. Y con la orden de la persona para esa declaración,
   `--conforme "<frase>"` lo presenta y guarda el justificante. Si lo domicilia, el cargo llega el
   último día del plazo (`gestoria domiciliaciones` lo enseña). La persona también puede
   presentarlo ella: formulario del 303 → «Importar» el mismo fichero → revisar → presentar.
7. **Después:** `gestoria cotejar 303` (lo presentado contra los libros, casilla a casilla, y el
   saldo a compensar del siguiente) y, si es autónomo, el 130 ingresado en `[pagado_este_anio]` de
   `ajustes.toml`. Sin esto, la hucha del trimestre siguiente sale mal.

## REBU (bienes usados)

Ventas con `regimen = rebu`, `total` (precio de venta con IVA) y `coste` (precio de compra).
Base = margen − IVA incluido; margen negativo = 0 y no compensa con otras operaciones (arts. 136
y 137 LIVA). Van en las casillas del régimen general por el tipo del bien (21 % el general; 10 % y
4 % los reducidos del art. 91 LIVA). Comprueba con `gestoria censo` que el REBU está de alta.

## Cotejar con lo que preparó o presentó una gestoría

`gestoria cotejar 303 --ejercicio AAAA --periodo NT` baja el fichero presentado de la sede (con
el certificado), lo lee con el diseño de registro oficial y lo compara con los libros. Dice quién lo
presentó y en calidad de qué (colaborador social, apoderado, el propio titular). Descuadres
típicos que conviene buscar: abonos o notas de crédito de proveedores sin restar del IVA deducido,
la cuota del REBU calculada sobre la base total en vez de operación a operación, facturas
anuladas o reembolsadas dentro o fuera según el criterio, y facturas que entraron en otro
trimestre. Antes de corregir nada, averigua cuál de los dos está bien.

## Si el plazo ya pasó

`gestoria recargo <importe> --vencio AAAA-MM-DD`: 1 % más 1 % por mes completo (art. 27 LGT).
Presentar hoy siempre sale más barato que mañana.
