"""Salud de los libros: lo que un gestor mira antes de preparar nada. Cada hallazgo lleva su
nivel (error: la declaración saldría mal; aviso: revísalo) y la norma que lo sostiene.

- Numeración de facturas correlativa dentro de cada serie, y las rectificativas en serie propia
  (art. 6.1.a RD 1619/2012). Un número repetido es un error; un hueco, un aviso.
- NIF con el dígito de control mal: no es una factura completa (art. 6.1.d RD 1619/2012).
- Cuota = base × tipo, con los tipos del 4, 10 y 21 % (arts. 90 y 91 LIVA).
- REBU: sin coste no hay margen (art. 137 LIVA); margen ≤ 0 → base 0 (art. 137.Uno).
- Compras sin NIF del proveedor: sin factura completa no se deduce el IVA (art. 97 LIVA).
- Una rectificativa tiene que apuntar a una factura que exista (art. 15 RD 1619/2012).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from gestoria import D2, nif
from gestoria.libros import Compra, Venta

TIPOS = {Decimal("0"), Decimal("4"), Decimal("10"), Decimal("21")}
_SERIE = re.compile(r"^(.*?)(\d+)$")


@dataclass
class Hallazgo:
    nivel: str        # error | aviso
    donde: str
    texto: str
    fuente: str

    def __str__(self) -> str:
        return f"{'❌' if self.nivel == 'error' else '⚠️'} {self.donde}: {self.texto} ({self.fuente})"


def _serie(numero: str) -> tuple[str, int] | None:
    m = _SERIE.match(numero.strip())
    return (m.group(1), int(m.group(2))) if m else None


def numeracion(ventas: list[Venta]) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    vistos: dict[str, Venta] = {}
    for v in ventas:
        if v.factura in vistos:
            out.append(Hallazgo("error", v.factura, "número de factura repetido", "art. 6.1.a RD 1619/2012"))
        vistos[v.factura] = v
    series: dict[str, list[tuple[int, Venta]]] = {}
    for v in ventas:
        s = _serie(v.factura)
        if s:
            series.setdefault(s[0], []).append((s[1], v))
    normales = {s for s, lista in series.items() if any(not v.rectifica for _, v in lista)}
    for s, lista in series.items():
        lista.sort(key=lambda x: x[0])
        nums = [n for n, _ in lista]
        faltan = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
        if faltan:
            muestra = ", ".join(f"{s}{n}" for n in faltan[:5]) + (f" y {len(faltan) - 5} más" if len(faltan) > 5 else "")
            out.append(Hallazgo("aviso", f"serie «{s or '(sin serie)'}»", f"huecos en la numeración: falta {muestra}",
                                "art. 6.1.a RD 1619/2012: numeración correlativa"))
        for (n1, v1), (n2, v2) in zip(lista, lista[1:]):
            if v2.fecha < v1.fecha:
                out.append(Hallazgo("aviso", v2.factura, f"fecha {v2.fecha} anterior a la de {v1.factura} ({v1.fecha})",
                                    "art. 6.1.a y b RD 1619/2012: la numeración sigue a la fecha"))
        if s in normales and any(v.rectifica for _, v in lista):
            out.append(Hallazgo("aviso", f"serie «{s or '(sin serie)'}»", "mezcla facturas y rectificativas: las rectificativas van en serie propia",
                                "art. 6.1.a.2.º RD 1619/2012"))
    return out


def ventas_coherentes(ventas: list[Venta], hoy: date | None = None) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    numeros = {v.factura for v in ventas}
    for v in ventas:
        if v.rectifica and v.rectifica not in numeros:
            out.append(Hallazgo("error", v.factura, f"rectifica {v.rectifica}, que no está en el libro", "art. 15 RD 1619/2012"))
        if v.nif_cliente and nif.es_espanol(v.nif_cliente) and not nif.valido(v.nif_cliente):
            out.append(Hallazgo("error", v.factura, f"NIF del cliente {v.nif_cliente} con el control mal", "art. 6.1.d RD 1619/2012"))
        if v.regimen in ("general", "rebu") and v.tipo not in TIPOS:
            out.append(Hallazgo("aviso", v.factura, f"tipo {v.tipo} % no es ninguno de 0, 4, 10 o 21", "arts. 90 y 91 LIVA"))
        if v.regimen == "rebu":
            if v.coste is None:
                out.append(Hallazgo("aviso", v.factura, "venta REBU sin coste de compra: sin coste no hay margen", "art. 137 LIVA"))
            elif v.total is not None and v.total - v.coste <= 0 and not v.rectifica:
                out.append(Hallazgo("aviso", v.factura, f"margen REBU ≤ 0 (venta {v.total}, coste {v.coste}): base 0", "art. 137.Uno LIVA"))
        elif v.regimen == "general" and v.base is not None and v.cuota is not None:
            esperada = D2(v.base * v.tipo / 100)
            if abs(esperada - v.cuota) > Decimal("0.01"):
                out.append(Hallazgo("error", v.factura, f"cuota {D2(v.cuota)} ≠ base {D2(v.base)} × {v.tipo} % = {esperada}", "art. 78 LIVA"))
        if hoy and v.fecha > hoy:
            out.append(Hallazgo("aviso", v.factura, f"fecha futura ({v.fecha})", "art. 6.1.b RD 1619/2012"))
    return out


def compras_coherentes(compras: list[Compra]) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    vistas: set[tuple[str, str]] = set()
    for c in compras:
        clave = (c.factura, c.nif_proveedor or c.proveedor)
        if clave in vistas:
            out.append(Hallazgo("error", c.factura, f"compra repetida ({c.proveedor})", "art. 64 RIVA: una anotación por factura"))
        vistas.add(clave)
        if c.deducible and not c.nif_proveedor:
            out.append(Hallazgo("aviso", c.factura, f"sin NIF del proveedor ({c.proveedor}): sin factura completa el IVA no se deduce",
                                "art. 97 LIVA; art. 6.1.d RD 1619/2012"))
        elif c.nif_proveedor and nif.es_espanol(c.nif_proveedor) and not nif.valido(c.nif_proveedor):
            out.append(Hallazgo("error", c.factura, f"NIF del proveedor {c.nif_proveedor} con el control mal", "art. 6.1.d RD 1619/2012"))
        if c.origen == "intracomunitaria" and c.nif_proveedor and nif.es_espanol(c.nif_proveedor):
            out.append(Hallazgo("aviso", c.factura, "marcada intracomunitaria pero el NIF del proveedor es español", "art. 13 LIVA"))
        if c.origen == "intracomunitaria" and c.cuota is not None and c.cuota != D2(c.base * c.tipo / 100):
            out.append(Hallazgo("aviso", c.factura, f"intracomunitaria: la cuota se autoliquida ({D2(c.base * c.tipo / 100)}), no la del proveedor",
                                "arts. 84.Uno.2.º y 85 LIVA"))
        if c.tipo not in TIPOS:
            out.append(Hallazgo("aviso", c.factura, f"tipo {c.tipo} % no es ninguno de 0, 4, 10 o 21", "arts. 90 y 91 LIVA"))
    return out


def revisar(ventas: list[Venta], compras: list[Compra], hoy: date | None = None) -> list[Hallazgo]:
    h = numeracion(ventas) + ventas_coherentes(ventas, hoy) + compras_coherentes(compras)
    return sorted(h, key=lambda x: (x.nivel != "error", x.donde))
