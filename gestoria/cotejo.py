"""Cotejo de lo PRESENTADO con lo que sale de tus libros, casilla a casilla.

El fichero presentado se baja de la sede (columna «Descarga fichero presentado» del listado de
declaraciones, en el mismo formato que el de «Importar») y se lee con el diseño de registro
oficial, igual que el que genera GestorIA. Las diferencias se explican por casilla. Es la forma
de revisar lo que te presentó una gestoría, o lo que presentaste tú con otro programa.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from gestoria import D2, dr

NOMBRES_303 = {
    "01": "base al 4 %", "03": "cuota al 4 %", "04": "base al 10 %", "06": "cuota al 10 %",
    "07": "base al 21 %", "09": "cuota al 21 %", "10": "base de adquisiciones intracomunitarias",
    "11": "cuota de adquisiciones intracomunitarias", "14": "base de modificaciones (rectificativas)",
    "15": "cuota de modificaciones (rectificativas)", "27": "total cuota devengada",
    "28": "base deducible de operaciones interiores corrientes", "29": "cuota deducible de operaciones interiores corrientes",
    "30": "base deducible de bienes de inversión", "31": "cuota deducible de bienes de inversión",
    "36": "base deducible de adquisiciones intracomunitarias", "37": "cuota deducible de adquisiciones intracomunitarias",
    "40": "rectificación de deducciones (base)", "41": "rectificación de deducciones (cuota)",
    "45": "total a deducir", "46": "resultado del régimen general", "59": "entregas intracomunitarias",
    "60": "exportaciones", "64": "suma de resultados", "66": "atribuible a la Administración del Estado",
    "69": "resultado de la autoliquidación", "71": "resultado", "78": "cuotas a compensar aplicadas",
    "87": "cuotas a compensar pendientes para después", "110": "cuotas a compensar de periodos anteriores",
    "120": "operaciones no sujetas por reglas de localización", "150": "base al 0 %",
}


def leer_presentado(fichero: Path, modelo: str = "303") -> dict[str, Decimal]:
    texto = Path(fichero).read_bytes().decode("latin-1")
    pags = dr.cargar(dr.DISENOS / "DR303e26v101.xlsx")
    return dr.leer_fichero(texto, pags)


def cotejar_303(presentado: dict[str, Decimal], borrador: dict[str, Decimal]) -> list[dict]:
    """Casillas en las que lo presentado y los libros no dan lo mismo (el % [65] y los tipos,
    que son constantes, no cuentan)."""
    pags = dr.cargar(dr.DISENOS / "DR303e26v101.xlsx")
    constantes = {c.casilla for p in pags.values() for c in p.campos if c.casilla and c.constante} | {"65"}
    cero = D2(0)
    out = []
    for k in sorted(set(presentado) | set(borrador), key=int):
        if k in constantes:
            continue
        a, b = presentado.get(k, cero), borrador.get(k, cero)
        if a != b:
            out.append({"casilla": k, "nombre": NOMBRES_303.get(k, ""), "presentado": a, "libros": b, "diferencia": D2(a - b)})
    return out


def explicar(difs: list[dict]) -> list[str]:
    """Una línea por diferencia y, al final, qué significa para el resultado."""
    from gestoria.numeros import eur

    lineas = [f"[{d['casilla']}] {d['nombre'] or 'casilla'}: presentado {eur(d['presentado'])}, "
              f"tus libros {eur(d['libros'])} (diferencia {eur(d['diferencia'])})" for d in difs]
    por = {d["casilla"]: d for d in difs}
    if "45" in por:
        x = por["45"]["diferencia"]
        lineas.append(f"→ se dedujo {eur(abs(x))} {'MÁS' if x > 0 else 'menos'} IVA del que sale de tus facturas recibidas: "
                      "busca facturas que faltan o sobran, abonos de proveedores sin restar o cuotas no deducibles")
    if "27" in por:
        x = por["27"]["diferencia"]
        lineas.append(f"→ se declaró {eur(abs(x))} {'más' if x > 0 else 'MENOS'} IVA devengado del que sale de tus facturas emitidas")
    if "71" in por:
        x = por["71"]["diferencia"]
        lineas.append(f"→ el resultado presentado es {eur(abs(x))} {'mayor' if x > 0 else 'menor'} que el de tus libros. "
                      "Antes de corregir nada, averigua cuál de los dos está bien; cómo se corrige (rectificativa del "
                      "mismo periodo o regularización en otro posterior) depende del caso: míralo con `gestoria boe`")
    return lineas


def compensar_siguiente(presentado: dict[str, Decimal], periodo: str) -> Decimal:
    """La casilla [110] del 303 siguiente: lo que quedaba por compensar ([87]) más lo que este
    salió a compensar (|[71]| si fue negativo y no es el último periodo, que se devuelve)."""
    pendiente = presentado.get("87", D2(0))
    resultado = presentado.get("71", D2(0))
    if resultado < 0 and periodo not in ("4T", "12"):
        pendiente += -resultado
    return D2(pendiente)
