"""Modelo 303 (IVA trimestral): casillas desde los libros y fichero de importación.

Fuentes (consultadas el 20-oct-2026):
- Instrucciones del modelo 303, ejercicio 2026, sede de la AEAT (casillas 01-09, 10-11, 14-15,
  28-46, 59-60, 64-71, 78, 87, 110, 120).
- Ley 37/1992 del IVA (BOE-A-1992-28740): art. 89 (rectificación de cuotas), art. 108 (no es bien
  de inversión lo que cuesta menos de 500.000 pesetas, 3.005,06 €: va con los corrientes), arts.
  135-139 (REBU: base = margen de beneficio menos el IVA incluido; margen negativo no compensa).
- Diseño de registro DR303e26v101.xlsx (formato del fichero).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from gestoria import D2, dr
from gestoria.libros import Compra, Venta

CASILLAS_TIPO = {Decimal("4"): ("01", "03"), Decimal("10"): ("04", "06"), Decimal("21"): ("07", "09")}
MINIMO_INVERSION = Decimal("3005.06")  # art. 108.Dos.5.º LIVA: «inferior a quinientas mil pesetas»
DEVENGADO = ("152", "167", "03", "155", "06", "09", "11", "13", "15", "158", "170", "18", "21", "24", "26")
DEDUCIBLE = ("29", "31", "33", "35", "37", "39", "41", "42", "43", "44")
INFO_VENTA = {"intracomunitaria": "59", "exportacion": "60", "no_sujeta": "120"}
# Campos de identificación de la página 1 (sin casilla): valor por defecto, buscados por su
# descripción. Notas 3 a 8 del diseño: «0» en los periodos que no son el último del año.
IDENT = {
    "Tributación exclusivamente foral": "2",
    "Registro de devolución mensual": "2",
    "exclusivamente en régimen simplificado": "3",
    "Autoliquidación conjunta": "2",
    "acogido al régimen especial del criterio de Caja": "2",
    "destinatario de operaciones acogidas al régimen especial del criterio de caja": "2",
    "concurso de acreedores en el presente": "2",
    "acogido voluntariamente al SII": "2",
    # Prorrata especial: la nota 6 habla de «blanco», pero el simulador solo admite 1 o 2
    # (E010171 y E010181, 20-oct-2026).
    "- Opción por la aplicación de la prorrata especial": "2",
    "Revocación de la opción por la aplicación de la prorrata especial": "2",
}
IDENT_ULTIMO = {  # (valor en 1T-3T, valor en 4T)
    "exonerado de la Declaración-resumen anual": ("0", "2"),
    "volumen anual de operaciones distinto de cero": ("0", "1"),
    "gasolinas": ("0", "0"),
}


def periodo_fechas(ejercicio: int, periodo: str) -> tuple[date, date]:
    if periodo.endswith("T"):
        n = int(periodo[0])
        ini = date(ejercicio, 3 * n - 2, 1)
        fin = date(ejercicio + 1, 1, 1) if n == 4 else date(ejercicio, 3 * n + 1, 1)
        return ini, fin
    m = int(periodo)
    return date(ejercicio, m, 1), (date(ejercicio + 1, 1, 1) if m == 12 else date(ejercicio, m + 1, 1))


def rebu(total: Decimal, coste: Decimal, tipo: Decimal) -> tuple[Decimal, Decimal]:
    margen = D2(total - coste)
    if margen <= 0:
        return D2(0), D2(0)
    cuota = D2(margen * tipo / (100 + tipo))
    return D2(margen - cuota), cuota


def _base_cuota(v: Venta) -> tuple[Decimal, Decimal]:
    if v.regimen == "rebu":
        if v.total is None or v.coste is None:
            raise ValueError(f"{v.factura}: en REBU hacen falta «total» (venta con IVA) y «coste»")
        return rebu(v.total, v.coste, v.tipo)
    if v.base is None:
        raise ValueError(f"{v.factura}: falta la base")
    return v.base, (v.cuota if v.cuota is not None else D2(v.base * v.tipo / 100))


def casillas(ventas: list[Venta], compras: list[Compra], desde: date, hasta: date,
             compensar_pendiente: Decimal) -> tuple[dict[str, Decimal], list[str]]:
    cas: dict[str, Decimal] = defaultdict(lambda: D2(0))
    avisos: list[str] = []
    por_numero = {v.factura: v for v in ventas}
    for v in (v for v in ventas if desde <= v.fecha < hasta):
        if v.regimen in INFO_VENTA:
            cas[INFO_VENTA[v.regimen]] += v.base if v.base is not None else (v.total or D2(0))
            continue
        if v.rectifica:
            if v.regimen == "rebu":
                orig = por_numero.get(v.rectifica)
                if orig is None:
                    raise ValueError(f"{v.factura} rectifica {v.rectifica}, que no está en ventas.csv")
                b, c = _base_cuota(orig)
                b, c = -b, -c
            else:
                b, c = _base_cuota(v)
            cas["14"] += b
            cas["15"] += c
            continue
        if v.tipo not in CASILLAS_TIPO:
            raise ValueError(f"{v.factura}: tipo {v.tipo} % no soportado (4, 10 o 21)")
        b, c = _base_cuota(v)
        if v.regimen == "rebu" and b == 0:
            avisos.append(f"{v.factura}: margen REBU ≤ 0 (venta {v.total}, coste {v.coste}); base 0")
        cb, cc = CASILLAS_TIPO[v.tipo]
        cas[cb] += b
        cas[cc] += c
    for c in (c for c in compras if desde <= c.fecha < hasta):
        if not c.deducible:
            continue
        cuota = c.cuota if c.cuota is not None else D2(c.base * c.tipo / 100)
        inversion = c.gasto == "inversion" and c.base >= MINIMO_INVERSION
        if c.gasto == "inversion" and not inversion:
            avisos.append(f"{c.factura}: {c.base} € < 3.005,06 €: para el IVA no es bien de inversión y va con los "
                          "corrientes (art. 108.Dos.5.º LIVA); en el IS/IRPF se sigue amortizando")
        if c.origen == "interior":
            b, q = ("30", "31") if inversion else ("28", "29")
        elif c.origen == "importacion":
            b, q = ("34", "35") if inversion else ("32", "33")
        else:
            cas["10"] += c.base
            cas["11"] += cuota
            b, q = ("38", "39") if inversion else ("36", "37")
        cas[b] += c.base
        cas[q] += cuota
    cas["27"] = sum((cas[k] for k in DEVENGADO), D2(0))
    cas["45"] = sum((cas[k] for k in DEDUCIBLE), D2(0))
    cas["46"] = cas["27"] - cas["45"]
    cas["64"] = cas["46"]
    cas["65"] = D2(100)
    cas["66"] = cas["64"]
    cas["110"] = D2(compensar_pendiente)
    cas["78"] = min(cas["110"], max(cas["66"], D2(0)))
    cas["87"] = cas["110"] - cas["78"]
    cas["69"] = cas["66"] - cas["78"]
    cas["71"] = cas["69"]
    return dict(cas), avisos


def tipo_declaracion(resultado: Decimal, periodo: str, forma_pago: str, hay_actividad: bool) -> str:
    if resultado > 0:
        return forma_pago if forma_pago in ("I", "U", "G") else "I"
    if resultado < 0:
        return "D" if periodo in ("4T", "12") else "C"
    return "N"


def generar_fichero(perfil, ejercicio: int, periodo: str, cas: dict[str, Decimal]) -> str:
    pags = dr.cargar(dr.DISENOS / "DR303e26v101.xlsx")
    ultimo = periodo in ("4T", "12")
    hay = any(v for k, v in cas.items() if k != "65")
    p1, p3 = pags["01000"], pags["03000"]
    v1: dict[int, object] = {
        p1.buscar("Tipo Declaración").n: tipo_declaracion(cas.get("71", D2(0)), periodo, perfil.forma_pago, hay),
        p1.buscar("Identificación (1) - NIF").n: perfil.nif,
        p1.buscar("Razón social").n: perfil.nombre,
        p1.buscar("Devengo (2) - Ejercicio").n: ejercicio,
        p1.buscar("Devengo (2) - Período").n: periodo,
    }
    for texto, valor in IDENT.items():
        v1[p1.buscar(texto).n] = valor
    for texto, (normal, fin) in IDENT_ULTIMO.items():
        v1[p1.buscar(texto).n] = fin if ultimo else normal
    v3: dict[int, object] = {}
    for pag, vals in ((p1, v1), (p3, v3)):
        for c in pag.campos:
            if c.casilla and c.casilla in cas and c.constante is None:
                vals[c.n] = cas[c.casilla]
    # La página DID (cuenta para domiciliar o devolver) va siempre: sin ella el simulador
    # rechaza el fichero entero (E060010 «Contenido incorrecto en 'Pagina DID'», 20-oct-2026).
    # Con domiciliación (U) o devolución (D) lleva el IBAN de [pago] iban; en una devolución,
    # además, la marca SEPA (1 = cuenta España, 2 = Unión Europea SEPA; nota 2 de la página DID).
    pd, vd = pags["DID00"], {}
    if v1[p1.buscar("Tipo Declaración").n] in ("U", "D") and perfil.iban:
        vd[pd.buscar("Domiciliación/Devolución - IBAN").n] = perfil.iban[:24] if perfil.iban.startswith("ES") else perfil.iban
        if v1[p1.buscar("Tipo Declaración").n] == "D":
            vd[pd.buscar("Devolución - Marca SEPA").n] = "1" if perfil.iban.startswith("ES") else "2"
    did = dr.pagina_texto(pd, vd)
    return dr.fichero("303", ejercicio, periodo,
                      [dr.pagina_texto(p1, v1), dr.pagina_texto(p3, v3), did])
