"""Seguridad Social (Import@ss) con el certificado de persona física, SOLO LECTURA: en qué
regímenes estás de alta, tu cuota de autónomo y cuándo te la cargan, la regularización de años
anteriores, tus días cotizados y los últimos documentos de la Tesorería.

Cómo entra (comprobado el 21-oct-2026): portal de Import@ss → «Entrar en tu área personal» →
idp.seg-social.es → «DNIe o certificado» → ipce.seg-social.es pide el certificado → vuelve a
«Mi área personal». Se lee esa página; no se pulsa nada más.
"""
from __future__ import annotations

import re
from datetime import datetime

PORTAL = "https://portal.seg-social.gob.es/wps/portal/importass/importass/inicio"
MESES = {m: i for i, m in enumerate(("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"), 1)}
_REGIMEN = re.compile(r"(Trabajador Autónomo|Régimen General|Régimen Especial|Sistema Especial|Empleo de hogar|Mar)", re.I)


def _importe(s: str) -> str:
    """«300,00 €» o «25.50 €» → «300,00 €» y «25,50 €» (la página mezcla los dos formatos)."""
    s = (s or "").replace("€", "").strip()
    if re.fullmatch(r"\d+\.\d{2}", s):
        s = s.replace(".", ",")
    return f"{s} €" if s else ""


def fecha_iso(texto: str) -> str:
    """«30 oct 2026» → «2026-10-30»."""
    m = re.search(r"(\d{1,2}) (\w{3})\w* (\d{4})", texto or "")
    if not m or m.group(2).lower() not in MESES:
        return ""
    return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def area_personal_de(texto: str) -> dict:
    """«Mi área personal» de Import@ss."""
    t = texto or ""
    lineas = [l.strip() for l in t.splitlines() if l.strip()]
    altas, i0 = [], next((i for i, l in enumerate(lineas) if l.startswith("Aquí puedes ver tu situación")), None)
    if i0 is not None:
        for i in range(i0 + 1, min(i0 + 30, len(lineas))):
            l = lineas[i]
            if l.startswith("Ver relación laboral") or l.startswith("Tu vida laboral"):
                break
            if l.startswith("Desde ") and i > 0:
                regimen = lineas[i - 1]
                empresa = lineas[i - 2] if i > 1 and not _REGIMEN.search(lineas[i - 2]) and not lineas[i - 2].startswith("Desde") \
                    and not lineas[i - 2].startswith("Aquí puedes") else ""
                altas.append({"regimen": regimen, "empresa": empresa, "desde": fecha_iso(l)})

    def g(patron, flags=0):
        m = re.search(patron, t, flags)
        return m.group(1).strip() if m else ""

    cuota = g(r"Última cuota\s*\n\s*([\d.,]+\s*€)")
    nuss = g(r"\(NUSS\):\s*(\d+)")
    documentos = []
    j = t.find("Tus documentos")
    if j >= 0:
        bloque = [l.strip() for l in t[j:t.find("Ver todos tus documentos", j)].splitlines() if l.strip()][2:]
        for k in range(0, len(bloque) - 2, 3):
            documentos.append({"documento": bloque[k], "fecha": fecha_iso(bloque[k + 2])})
    return {
        "de_alta": "Estás de alta en la Seguridad Social" in t,
        "altas": altas,
        "nuss": ("*" * (len(nuss) - 4) + nuss[-4:]) if nuss else "",
        "dias_cotizados": g(r"([\d.]+) días en alta"),
        "tiempo_cotizado": g(r"\n(\d+ años?,[^\n]+)"),
        "base_cotizacion": _importe(g(r"([\d.,]+ €) de base de cotización")),
        "cuota_autonomo": _importe(cuota),
        "regularizacion": _importe(g(r"regularización de cuotas anteriores, se cargarán:\s*([\d.,]+\s*€)")),
        "cargo": fecha_iso(g(r"Cargo a partir del ([^\n]+)")),
        "documentos": documentos[:6],
    }


def consultar(nav) -> dict:
    from gestoria.navegador import comprobar

    pg = nav.abrir(PORTAL, espera=3000)
    try:
        for t in ("Rechazar todas", "Rechazar"):
            loc = pg.get_by_text(t, exact=True)
            if loc.count():
                try:
                    loc.first.click(timeout=3000)
                    break
                except Exception:
                    pass
        for paso in ("Entrar en tu área personal", "DNIe o certificado"):
            comprobar(paso)
            pg.get_by_text(paso, exact=True).first.click()
            pg.wait_for_timeout(9000)
        pg.wait_for_load_state("networkidle", timeout=60000)
        if "/personal" not in pg.url:
            raise RuntimeError(f"la Seguridad Social no ha aceptado el certificado (quedó en {pg.url[:80]})")
        nav.captura(pg, "seguridad_social")
        d = area_personal_de(pg.inner_text("body"))
    finally:
        for p in list(nav.ctx.pages):
            p.close()
    d["consultado"] = datetime.now().isoformat(timespec="seconds")
    return d
