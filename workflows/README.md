# Workflows de GestorIA

Diez flujos para la persona (nueve van en el cron; `gestoria presentar` no, porque necesita su
conformidad) y dos para el repositorio (GitHub Actions). Ninguno paga, solicita ni abre una
notificación, y solo `gestoria presentar` presenta, nunca desde el cron.

| flujo | cuándo | qué deja | código de salida |
|---|---|---|---|
| `gestoria vigia` | cada día a primera hora | `salida/vigia.json` (lo que hay en rojo y en amarillo), `salida/vigia.log` y la foto de la sede que lee el panel. Mira notificaciones de la AEAT y de la DEHú, deudas, alertas y la caducidad de los certificados, con el de la empresa y con el personal | 2 si hay algo rojo **nuevo** desde la pasada anterior · 1 si sigue habiendo algo rojo · 0 si no |
| `gestoria hoy` | cada mañana, después del vigía | el panel en la terminal: plazos con semáforo, hucha, salud de los libros registro, radares, sede, certificado y último chequeo | 0 verde · 1 amarillo · 2 rojo |
| `gestoria semana` | lunes | `salida/semana_AAAA-WNN.md`: el panel y la lista «Esta semana» | 2 si hay rojo |
| `gestoria trimestre` | día 2 de ene/abr/jul/oct | `salida/trimestre_AAAA_NT.md` y el fichero del 303 validado en el simulador de la AEAT | 1 si la validación falla |
| `gestoria presentar 303` | después de `trimestre`, **a mano**: necesita la conformidad de la persona | la revisión antes de presentar (el ensayo con `--pruebas` y, con `--conforme`, la presentación); el justificante en `salida/presentado/` | 2 si algo lo para |
| `gestoria banco` | cuando haya un extracto nuevo en `banco/` (o con `--descargar`, que necesita las cookies recién exportadas) | `salida/banco_AAAA-MM-DD.md`: cada movimiento casado con su factura y lo que queda por explicar | 1 si hay algo por explicar |
| `gestoria cotejar 303` | día 21 de ene/abr/jul/oct, ya vencido el plazo | el 303 **presentado** (bajado de la sede) contra los libros, casilla a casilla, y la línea de `compensar_pendiente` para el trimestre siguiente | 1 si hay diferencias o no consta presentado |
| `gestoria chequeo` | día 1 de cada mes, y el primer día que haya certificado | `salida/chequeo_AAAA-MM-DD.md` y `salida/chequeo.json`: la revisión completa (AEAT, DEHú, Seguridad Social, NIF de terceros, cotejo de lo presentado) con hallazgos 🔴 🟡 🟢 ℹ️ | 2 rojo · 1 amarillo · 0 verde |
| `gestoria ayudas` | día 1 de cada mes | `salida/ayudas_AAAA-MM-DD.md` y `salida/ayudas.json`: las convocatorias de la Base de Datos Nacional de Subvenciones para pymes y autónomos en tu zona, abiertas o no, con el enlace a las bases y a la sede donde se piden | 0 |
| `gestoria anual` | enero | `salida/anual_AAAA.md`: IVA por trimestres, IS o IRPF estimado, 347, calendario del cierre | 0 |

`crontab.ejemplo` tiene las líneas. Las de la sede necesitan el certificado en `perfil.toml`; sin
él fallan con un mensaje claro y no hacen nada más.

## Avisos

El vigía sale con código 2 solo cuando aparece algo rojo que no estaba en la pasada anterior. Así
el cron te escribe una vez por cada notificación, deuda o certificado a punto de caducar, y no
cada mañana:

```
30 7 * * *   $G vigia > $F 2>&1; [ $? -eq 2 ] && mail -s "GestorIA: algo nuevo en la sede" tu@correo < $F
```

Cambia `mail` por lo que uses (`msmtp`, un bot de Telegram, `notify-send`…).

## En GitHub

- `.github/workflows/ci.yml`: tests en cada cambio (Python 3.11-3.14), búsqueda de secretos y el
  test de privacidad (ni NIF, ni IBAN, ni correos reales, ni certificados, ni claves privadas).
- `.github/workflows/aeat.yml`: cada noche, contra las fuentes oficiales: el fichero del 303 sigue
  pasando el simulador de la AEAT, el diseño de registro no ha cambiado de versión, y el calendario
  y el BOE responden. Si Hacienda cambia algo, falla ese mismo día.

Las órdenes con certificado no corren en GitHub a propósito: un certificado electrónico no se
guarda en un servicio de terceros. Sus pantallas se prueban con textos inventados que tienen la
misma forma que los reales (`tests/test_aeat_lectura.py`, `tests/test_dehu_ss_terceros.py`) y, en
tu equipo, con `GESTORIA_PRUEBA_CARPETA=<tu carpeta> pytest -m live tests/test_certificado_live.py`.
