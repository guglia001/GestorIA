"""Qué cuesta presentar tarde, sin que Hacienda te lo haya pedido (art. 27 LGT, Ley 58/2003,
leído en el BOE el 20-oct-2026):
- recargo del 1 % más otro 1 % por cada mes completo de retraso, sobre lo que salga a ingresar,
  sin sanción ni intereses (art. 27.2);
- pasados 12 meses, recargo del 15 % más intereses de demora desde el día siguiente a esos 12
  meses (art. 27.2, párrafo tercero);
- el recargo se reduce un 25 % si se paga todo en plazo (art. 27.5).
El interés de demora lo fija cada año la Ley de Presupuestos; el que se aplica por defecto es el
último publicado (4,0625 %, Ley 31/2022, prorrogado): compruébalo en la sede de la AEAT.
Si salió a compensar o a cero no hay recargo, pero sí puede haber sanción por no presentar
(art. 198 LGT): eso no se calcula aquí.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from gestoria import D2

INTERES_DEMORA = Decimal("4.0625")  # % anual; ⚠️ vigente salvo que la Ley de Presupuestos lo cambie


@dataclass
class Recargo:
    meses_completos: int
    porcentaje: Decimal
    recargo: Decimal
    recargo_reducido: Decimal
    intereses: Decimal
    dias_interes: int
    total: Decimal
    fuente: str


def meses_completos(desde: date, hasta: date) -> int:
    if hasta <= desde:
        return 0
    m = (hasta.year - desde.year) * 12 + hasta.month - desde.month
    return m - 1 if hasta.day < desde.day else m


def calcular(importe: Decimal, vencimiento: date, presentacion: date,
             interes_anual: Decimal = INTERES_DEMORA) -> Recargo:
    importe = D2(importe)
    if presentacion <= vencimiento or importe <= 0:
        return Recargo(0, D2(0), D2(0), D2(0), D2(0), 0, importe, "en plazo o sin importe a ingresar: sin recargo")
    meses = meses_completos(vencimiento, presentacion)
    doce = vencimiento + timedelta(days=0)
    doce = date(doce.year + 1, doce.month, doce.day) if not (doce.month == 2 and doce.day == 29) else date(doce.year + 1, 3, 1)
    if presentacion > doce:
        pct, dias = Decimal(15), (presentacion - doce).days
        intereses = D2(importe * interes_anual / 100 * dias / 365)
        fuente = "art. 27.2 LGT (más de 12 meses): 15 % más intereses de demora desde el día siguiente a los 12 meses"
    else:
        pct, dias, intereses = Decimal(1 + min(meses, 11)), 0, D2(0)
        fuente = f"art. 27.2 LGT: 1 % + 1 % por cada mes completo de retraso ({meses})"
    recargo = D2(importe * pct / 100)
    reducido = D2(recargo * 75 / 100)
    return Recargo(meses, pct, recargo, reducido, intereses, dias, D2(importe + recargo + intereses), fuente)
