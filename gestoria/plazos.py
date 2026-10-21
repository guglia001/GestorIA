"""Plazos de presentación por norma, para cuando el calendario oficial no está a mano (sin red)
y para fechar la hucha. Cuando el calendario de la AEAT está disponible, manda él: incluye los
festivos. Aquí solo se pasa al lunes lo que cae en sábado o domingo (art. 30.5 Ley 39/2015).

Fuentes (BOE consolidado, leídas el 20-oct-2026):
- 303: art. 71.4 RIVA (RD 1624/1992): «veinte primeros días naturales del mes siguiente al
  período de liquidación trimestral»; el último período, «treinta primeros días naturales de enero».
- 130: art. 111.1 RIRPF (RD 439/2007): 1-20 de abril, julio y octubre; 4T, 1-30 de enero.
- 202: art. 40.1 LIS (Ley 27/2014): «primeros 20 días naturales de los meses de abril, octubre y diciembre».
- 200: art. 124.1 LIS: «25 días naturales siguientes a los 6 meses posteriores a la conclusión del
  período impositivo» (ejercicio = año natural → 1-25 de julio).
- 390 (enero), 347 (febrero), 100 (hasta el 30 de junio): las órdenes de cada modelo; el calendario
  de la AEAT es la referencia.
"""
from __future__ import annotations

from datetime import date, timedelta

FUENTE = {
    "303": "art. 71.4 RIVA", "130": "art. 111.1 RIRPF", "202": "art. 40.1 LIS",
    "200": "art. 124.1 LIS", "390": "orden del modelo 390 (calendario AEAT)",
    "347": "orden del modelo 347 (calendario AEAT)", "100": "orden de Renta (calendario AEAT)",
}


def habil(d: date) -> date:
    """Sábado o domingo → lunes siguiente (art. 30.5 Ley 39/2015). Los festivos los pone el calendario oficial."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def trimestre_de(d: date) -> tuple[int, str]:
    return d.year, f"{(d.month - 1) // 3 + 1}T"


def trimestre_anterior(ejercicio: int, periodo: str) -> tuple[int, str]:
    n = int(periodo[0])
    return (ejercicio - 1, "4T") if n == 1 else (ejercicio, f"{n - 1}T")


def vence(modelo: str, ejercicio: int, periodo: str | None = None) -> date:
    """Último día del plazo, ya pasado a día hábil. `periodo`: 1T…4T (303/130) o abril/octubre/diciembre (202)."""
    if modelo in ("303", "130"):
        n = int(periodo[0])
        d = date(ejercicio + 1, 1, 30) if n == 4 else date(ejercicio, 3 * n + 1, 20)
    elif modelo == "202":
        d = date(ejercicio, {"abril": 4, "octubre": 10, "diciembre": 12}[periodo], 20)
    elif modelo == "200":
        d = date(ejercicio + 1, 7, 25)
    elif modelo == "390":
        d = date(ejercicio + 1, 1, 30)
    elif modelo == "347":
        d = date(ejercicio + 1, 3, 1) - timedelta(days=1)
    elif modelo == "100":
        d = date(ejercicio + 1, 6, 30)
    else:
        raise KeyError(f"sin regla de plazo para el modelo {modelo}")
    return habil(d)


def plazos_202(ejercicio: int) -> list[tuple[str, date]]:
    return [(m, vence("202", ejercicio, m)) for m in ("abril", "octubre", "diciembre")]
