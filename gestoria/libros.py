"""Libros de ventas y compras en CSV: el contrato de datos de GestorIA.

Cualquier programa de facturación o banco se adapta escribiendo estos dos ficheros. Columnas
en `ejemplos/sl-demo/libros/`. Separador «;» o «,» (se detecta); importes «1.234,56» o «1234.56».
"""
from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from gestoria.numeros import importe

REG_VENTA = ("general", "rebu", "intracomunitaria", "exportacion", "no_sujeta")
ORIGEN = ("interior", "intracomunitaria", "importacion")
GASTO = ("corriente", "inversion")


@dataclass
class Venta:
    fecha: date
    factura: str
    cliente: str
    nif_cliente: str
    regimen: str
    tipo: Decimal
    base: Decimal | None
    cuota: Decimal | None
    total: Decimal | None
    coste: Decimal | None
    rectifica: str
    retencion: Decimal | None = None   # IRPF que te retuvo el cliente (profesionales), se resta del 130


@dataclass
class Compra:
    fecha: date
    factura: str
    proveedor: str
    nif_proveedor: str
    base: Decimal
    tipo: Decimal
    cuota: Decimal | None
    gasto: str
    origen: str
    deducible: bool


def _filas(f: Path) -> list[dict]:
    if not f.is_file():
        raise FileNotFoundError(f"falta {f}")
    texto = f.read_text(encoding="utf-8-sig")
    cabecera = texto.split("\n", 1)[0]
    sep = ";" if cabecera.count(";") >= cabecera.count(",") else ","
    return [{k.strip(): (v or "").strip() for k, v in r.items()}
            for r in csv.DictReader(texto.splitlines(), delimiter=sep)]


def _uno_de(valor: str, validos: tuple, que: str, donde: str) -> str:
    v = valor.lower()
    if v not in validos:
        raise ValueError(f"{donde}: {que} «{valor}» no es ninguno de {', '.join(validos)}")
    return v


def cargar(carpeta: Path) -> tuple[list[Venta], list[Compra]]:
    d = Path(carpeta) / "libros"
    ventas = []
    for i, r in enumerate(_filas(d / "ventas.csv"), start=2):
        donde = f"ventas.csv línea {i}"
        ventas.append(Venta(
            fecha=date.fromisoformat(r["fecha"]), factura=r["factura"], cliente=r.get("cliente", ""),
            nif_cliente=r.get("nif_cliente", ""),
            regimen=_uno_de(r["regimen"], REG_VENTA, "el régimen", donde),
            tipo=importe(r.get("tipo")) or Decimal("0"), base=importe(r.get("base")),
            cuota=importe(r.get("cuota")), total=importe(r.get("total")),
            coste=importe(r.get("coste")), rectifica=r.get("rectifica", ""),
            retencion=importe(r.get("retencion"))))
    compras = []
    for i, r in enumerate(_filas(d / "compras.csv"), start=2):
        donde = f"compras.csv línea {i}"
        compras.append(Compra(
            fecha=date.fromisoformat(r["fecha"]), factura=r["factura"], proveedor=r.get("proveedor", ""),
            nif_proveedor=r.get("nif_proveedor", ""), base=importe(r["base"]) or Decimal("0"),
            tipo=importe(r.get("tipo")) or Decimal("0"), cuota=importe(r.get("cuota")),
            gasto=_uno_de(r.get("gasto") or "corriente", GASTO, "el gasto", donde),
            origen=_uno_de(r.get("origen") or "interior", ORIGEN, "el origen", donde),
            deducible=(r.get("deducible") or "si").lower() in ("si", "sí", "s", "1", "true")))
    return ventas, compras


def ajustes(carpeta: Path) -> dict:
    f = Path(carpeta) / "ajustes.toml"
    return tomllib.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def pagado(aj: dict, modelo: str) -> Decimal:
    """Lo ya ingresado este año de un modelo (130, 202…), según `[pagado_este_anio]` de ajustes.toml."""
    return sum((Decimal(str(x)) for x in (aj.get("pagado_este_anio") or {}).get(modelo, [])), Decimal("0"))
