"""Radares: las cifras que, al pasar un umbral, cambian lo que tienes que presentar. Un gestor
las vigila para que febrero o el año que viene no traigan sorpresas.

Fuentes (BOE consolidado, leídas el 20-oct-2026):
- 347: hay que declarar a cada persona o entidad con la que las operaciones del año natural
  superen 3.005,06 €, entregas y adquisiciones por separado (art. 33.1 RGAT, RD 1065/2007).
  Quedan fuera las que ya van en otra declaración (349, 190…), importaciones y exportaciones (art. 33.2).
- Liquidación mensual del IVA y SII: volumen de operaciones del año anterior > 6.010.121,04 €
  (arts. 71.3 y 62.6 RIVA).
- Microempresa en el IS (escala del art. 29.1 LIS): cifra de negocios del año anterior < 1 M€.
  Reducida dimensión (art. 101 LIS): < 10 M€.
- Estimación directa simplificada (autónomos): cifra de negocios del año anterior ≤ 600.000 €
  (art. 28.1.b RIRPF).
- Ventas a distancia intracomunitarias a particulares: 10.000 € al año (art. 73 LIVA) → IVA del
  país del cliente (OSS, modelo 369). Aquí no se mide: los libros no llevan el país del cliente.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from gestoria import D2
from gestoria.libros import Compra, Venta

LIMITE_347 = Decimal("3005.06")
UMBRALES = {
    "sl": (("Liquidación mensual del IVA y SII", Decimal("6010121.04"), "arts. 71.3 y 62.6 RIVA", "pasarías a declarar el IVA cada mes y a llevar los libros por el SII"),
           ("Microempresa en el IS", Decimal("1000000"), "art. 29.1 LIS", "perderías la escala reducida del IS (17 %/20 %)"),
           ("Empresa de reducida dimensión", Decimal("10000000"), "art. 101 LIS", "perderías los incentivos de reducida dimensión")),
    "autonomo": (("Estimación directa simplificada", Decimal("600000"), "art. 28.1.b RIRPF", "pasarías a estimación directa normal"),
                 ("Liquidación mensual del IVA y SII", Decimal("6010121.04"), "arts. 71.3 y 62.6 RIVA", "pasarías a declarar el IVA cada mes y a llevar los libros por el SII")),
}


@dataclass
class Tercero:
    nombre: str
    nif: str
    entregas: Decimal
    adquisiciones: Decimal


@dataclass
class Umbral:
    nombre: str
    medido: Decimal
    limite: Decimal
    fuente: str
    consecuencia: str

    @property
    def pct(self) -> int:
        return int(min(self.medido * 100 / self.limite, Decimal(999))) if self.limite else 0


def _importe(v: Venta) -> Decimal:
    return v.total if v.total is not None else D2((v.base or D2(0)) + (v.cuota or D2(0)))


def radar_347(ventas: list[Venta], compras: list[Compra], ejercicio: int) -> list[Tercero]:
    """Terceros que superan 3.005,06 € en el año, en entregas o en adquisiciones."""
    ent: dict[str, Decimal] = defaultdict(lambda: D2(0))
    adq: dict[str, Decimal] = defaultdict(lambda: D2(0))
    nombres: dict[str, str] = {}
    for v in ventas:
        if v.fecha.year != ejercicio or v.regimen in ("intracomunitaria", "exportacion"):
            continue  # van en el 349 o son exportaciones (art. 33.2.g e i RGAT)
        clave = v.nif_cliente or v.cliente
        if not clave:
            continue
        ent[clave] += _importe(v)
        nombres[clave] = v.cliente or v.nif_cliente
    for c in compras:
        if c.fecha.year != ejercicio or c.origen != "interior":
            continue
        clave = c.nif_proveedor or c.proveedor
        adq[clave] += c.base + (c.cuota if c.cuota is not None else D2(c.base * c.tipo / 100))
        nombres[clave] = c.proveedor or c.nif_proveedor
    out = []
    for clave in set(ent) | set(adq):
        if ent[clave] > LIMITE_347 or adq[clave] > LIMITE_347:
            nombre = nombres[clave]
            out.append(Tercero(nombre, clave if clave != nombre else "", D2(ent[clave]), D2(adq[clave])))
    return sorted(out, key=lambda t: -(t.entregas + t.adquisiciones))


def cifra_negocios(ventas: list[Venta], ejercicio: int) -> Decimal:
    """Ventas del año sin IVA (en REBU, el precio entero menos la cuota del margen), restando las rectificativas."""
    from datetime import date

    from gestoria import hucha

    ingresos, _, _ = hucha.ingresos_gastos(ventas, [], date(ejercicio, 1, 1), date(ejercicio + 1, 1, 1))
    return ingresos


def umbrales(perfil, ventas: list[Venta], ejercicio: int) -> list[Umbral]:
    cifra = cifra_negocios(ventas, ejercicio)
    return [Umbral(n, cifra, lim, f, c) for n, lim, f, c in UMBRALES[perfil.tipo]]


def barra(pct: int, ancho: int = 10) -> str:
    llenos = min(ancho, round(pct * ancho / 100))
    return "▓" * llenos + "░" * (ancho - llenos)
