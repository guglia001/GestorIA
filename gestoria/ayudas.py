"""Ayudas y subvenciones que puedes pedir, y las bonificaciones que no salen en ninguna base de datos.

La fuente es la Base de Datos Nacional de Subvenciones (BDNS, infosubvenciones.es), donde toda
administración (el Estado, las comunidades, las diputaciones y los ayuntamientos) publica sus
convocatorias (art. 20 de la Ley 38/2003, General de Subvenciones). Se lee en el momento, con su API
pública, filtrada por quién eres (pymes y personas físicas con actividad económica), por dónde estás
(tu provincia, tu comunidad y las de ámbito estatal) y por las palabras que te describen. De cada
convocatoria se enseña si está abierta y hasta cuándo, el órgano, el presupuesto y los enlaces a las
bases y a la sede donde se pide. GestorIA no solicita nada: cada ayuda se pide en la sede del órgano
que la convoca, y las bases de cada una mandan sobre lo que resume aquí.

Aparte van las bonificaciones que no son subvenciones y por eso no están en la BDNS: la cuota
reducida de la Seguridad Social para nuevos autónomos (art. 38 ter de la Ley 20/2007).
"""
from __future__ import annotations

import json
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from gestoria import D2
from gestoria.numeros import eur

API = "https://www.infosubvenciones.es/bdnstrans/api"
WEB = "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/{numero}"
PYME = 3        # tipo de beneficiario «PYME Y PERSONAS FÍSICAS QUE DESARROLLAN ACTIVIDAD ECONÓMICA»
ESPANA = 1      # región «ES - ESPAÑA»: las convocatorias de ámbito estatal
ORDEN_ESTADO = {"🟢": 0, "🟡": 1, "⚪": 2, "🔴": 3}


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper().strip()


def _get(ruta: str, **params):
    """Una petición de lectura a la API pública de la BDNS (JSON)."""
    q = urllib.parse.urlencode({"vpd": "GE", **params})
    req = urllib.request.Request(f"{API}/{ruta}?{q}", headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 gestoria"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def regiones() -> list[dict]:
    """El árbol de regiones (NUTS) de la BDNS, solo España, plano: id, código, nombre y los ids de sus padres."""
    out: list[dict] = []

    def andar(n: dict, padres: list[int]) -> None:
        codigo, _, nombre = (n.get("descripcion") or "").partition(" - ")
        out.append({"id": n["id"], "codigo": codigo.strip(), "nombre": nombre.strip() or codigo.strip(), "padres": padres})
        for h in n.get("children") or []:
            andar(h, padres + [n["id"]])

    for n in _get("regiones"):
        if n.get("id") == ESPANA or (n.get("descripcion") or "").startswith("ES"):
            andar(n, [])
    return out


def ids_region(nombre: str, lista: list[dict]) -> list[int]:
    """La región que se llama así (la provincia antes que la comunidad), su comunidad y España."""
    n = _norm(nombre)
    exactas = [r for r in lista if _norm(r["nombre"]) == n or _norm(r["codigo"]) == n]
    parciales = exactas or [r for r in lista if n in _norm(r["nombre"])]
    if not parciales:
        raise ValueError(f"la BDNS no tiene ninguna región llamada «{nombre}»: prueba con la provincia («Madrid», «Valencia / València», "
                         "«Mallorca») o con la comunidad («Comunidad de Madrid», «Illes Balears», «Andalucía»)")
    r = min(parciales, key=lambda x: (len(x["nombre"]), x["id"]))
    ids = [r["id"]] + list(reversed(r["padres"]))        # la región, su comunidad… y España al final
    return ids if ESPANA in ids else ids + [ESPANA]


@dataclass
class Convocatoria:
    numero: str
    titulo: str
    organo: str
    ambito: str                                   # ESTATAL · AUTONOMICA · LOCAL · OTROS
    recibida: date | None
    abierta: bool | None = None
    inicio: date | None = None
    fin: date | None = None
    texto_inicio: str = ""
    texto_fin: str = ""
    presupuesto: Decimal | None = None
    beneficiarios: list[str] = field(default_factory=list)
    finalidad: str = ""
    regiones: list[str] = field(default_factory=list)
    instrumentos: list[str] = field(default_factory=list)
    url_bases: str = ""
    sede: str = ""
    palabras: list[str] = field(default_factory=list)   # con cuáles de tus palabras ha salido

    @property
    def url(self) -> str:
        return WEB.format(numero=self.numero)


def _fecha(s) -> date | None:
    if not s:
        return None
    s = str(s)[:10]
    for f in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def convocatoria(d: dict) -> Convocatoria:
    """Una convocatoria a partir del JSON de detalle de la BDNS."""
    o = d.get("organo") or {}
    return Convocatoria(
        numero=str(d.get("codigoBDNS") or d.get("numeroConvocatoria") or ""), titulo=(d.get("descripcion") or "").strip(),
        organo=(o.get("nivel3") or o.get("nivel2") or "").strip(), ambito=(o.get("nivel1") or "").strip(),
        recibida=_fecha(d.get("fechaRecepcion")), abierta=d.get("abierto"),
        inicio=_fecha(d.get("fechaInicioSolicitud")), fin=_fecha(d.get("fechaFinSolicitud")),
        texto_inicio=(d.get("textInicio") or "").strip(), texto_fin=(d.get("textFin") or "").strip(),
        presupuesto=D2(d["presupuestoTotal"]) if d.get("presupuestoTotal") is not None else None,
        beneficiarios=[(b.get("descripcion") or "").strip() for b in d.get("tiposBeneficiarios") or []],
        finalidad=(d.get("descripcionFinalidad") or "").strip(),
        regiones=[(r.get("descripcion") or "").strip() for r in d.get("regiones") or []],
        instrumentos=[(i.get("descripcion") or "").strip() for i in d.get("instrumentos") or []],
        url_bases=(d.get("urlBasesReguladoras") or "").strip(), sede=(d.get("sedeElectronica") or "").strip())


def detalle(numero: str) -> Convocatoria:
    return convocatoria(_get("convocatorias", numConv=numero))


def estado(c: Convocatoria, hoy: date) -> tuple[str, str]:
    """🟢 abierta · 🟡 abre después · ⚪ sin fecha estructurada · 🔴 cerrada, con el porqué."""
    from gestoria.calendario import fecha_txt

    if c.fin and c.fin < hoy:
        return "🔴", f"cerrada el {fecha_txt(c.fin)}"
    if c.inicio and c.inicio > hoy:
        return "🟡", f"abre el {fecha_txt(c.inicio)}" + (f", hasta el {fecha_txt(c.fin)}" if c.fin else "")
    if c.fin:
        return "🟢", f"abierta hasta el {fecha_txt(c.fin)}"
    if c.abierta:
        return "🟢", "abierta" + (f" ({c.texto_fin[:80]})" if c.texto_fin else "")
    if c.texto_fin:
        return "⚪", f"plazo: {c.texto_fin[:90]}"
    return "⚪", "sin plazo publicado: míralo en las bases"


def buscar(region: str | None, palabras: list[str], hoy: date, dias: int = 120, maximo: int = 25) -> dict:
    """Las convocatorias para pymes y autónomos publicadas en los últimos `dias` días en España y en tu
    región, y las que además hablan de tus palabras; con el detalle de las `maximo` más recientes."""
    ids = ids_region(region, regiones()) if region else [ESPANA]
    desde = hoy - timedelta(days=dias)
    base = {"page": 0, "pageSize": 50, "order": "fechaRecepcion", "direccion": "desc", "tiposBeneficiario": PYME,
            "regiones": ",".join(str(i) for i in ids), "fechaDesde": desde.strftime("%d/%m/%Y")}
    vistas: dict[str, dict] = {}
    for palabra in [None, *palabras]:
        d = _get("convocatorias/busqueda", **(dict(base, descripcion=palabra) if palabra else base))
        for fila in d.get("content") or []:
            e = vistas.setdefault(str(fila.get("numeroConvocatoria")), {"fila": fila, "palabras": []})
            if palabra:
                e["palabras"].append(palabra)
    candidatas = sorted(vistas.values(), key=lambda e: (len(e["palabras"]), e["fila"].get("fechaRecepcion") or ""), reverse=True)
    out: list[Convocatoria] = []
    for e in candidatas[:maximo]:
        c = detalle(str(e["fila"]["numeroConvocatoria"]))
        c.palabras = e["palabras"]
        out.append(c)
    out.sort(key=lambda c: (ORDEN_ESTADO[estado(c, hoy)[0]], -len(c.palabras), -(c.recibida or date.min).toordinal()))
    return {"convocatorias": out, "desde": desde, "region": region, "ids": ids, "palabras": list(palabras), "total_encontradas": len(vistas),
            "consultado": f"{hoy.isoformat()}T{datetime.now():%H:%M:%S}"}


BONIFICACIONES = {
    "autonomo": [
        "🪙 Cuota reducida de nuevos autónomos (la «tarifa plana»): si es tu alta inicial, o no has estado de alta en los 2 años "
        "anteriores, pagas una cuota reducida durante 12 meses, y otros 12 si tus rendimientos netos quedan por debajo del salario "
        "mínimo; se pide al darte de alta, y antes del segundo periodo (art. 38 ter Ley 20/2007). La cuantía la fija la Ley de "
        "Presupuestos de cada año (80 € al mes en 2023-2025, DT 5.ª RD-ley 13/2022): compruébala en Import@ss "
        "(`gestoria seguridad-social`).",
        "🧾 Lo que te puedes deducir (seguro de salud, suministros de casa, comidas, el 20 % de los dos primeros años…): "
        "`gestoria deducciones`.",
    ],
    "sl": [
        "🏢 El tipo del 15 % de nueva creación, la reserva de capitalización, la de nivelación y lo que deduce y lo que no: "
        "`gestoria deducciones`.",
    ],
}


def texto(r: dict, pf, hoy: date) -> str:
    from gestoria.calendario import fecha_txt

    cs = r["convocatorias"]
    ambito = "España" + (f" y {r['region']}" if r["region"] else "") if r["region"] else "España (ámbito estatal; pon [ayudas] region en perfil.toml para ver las de tu zona)"
    L = [f"📡 Ayudas y subvenciones · {pf.nombre} · {fecha_txt(hoy)}",
         f"   Base de Datos Nacional de Subvenciones: convocatorias para pymes y autónomos publicadas desde el {fecha_txt(r['desde'])} "
         f"en {ambito}" + (f", y las que hablan de {', '.join(r['palabras'])}" if r["palabras"] else "") + "."]
    if not cs:
        L.append("   Ninguna en ese plazo. Prueba con --dias 365 o con otras palabras.")
    for c in cs:
        e, t = estado(c, hoy)
        L += ["", f"{e} {t} · {c.organo} ({c.ambito.lower()})" if c.organo else f"{e} {t}", f"   {c.titulo[:150]}"]
        datos = [f"presupuesto {eur(c.presupuesto)}" if c.presupuesto else "", f"publicada el {fecha_txt(c.recibida)}" if c.recibida else "",
                 f"habla de: {', '.join(c.palabras)}" if c.palabras else "", f"BDNS {c.numero}"]
        L.append("   " + " · ".join(x for x in datos if x))
        L.append(f"   {c.url}" + (f" · bases: {c.url_bases}" if c.url_bases else "") + (f" · se pide en: {c.sede}" if c.sede else ""))
    cuenta = {k: sum(1 for c in cs if estado(c, hoy)[0] == k) for k in ORDEN_ESTADO}
    L += ["", f"{len(cs)} convocatoria(s) con detalle de {r['total_encontradas']} encontradas: {cuenta['🟢']} abiertas, {cuenta['🟡']} por abrir, "
              f"{cuenta['⚪']} sin fecha estructurada, {cuenta['🔴']} cerradas. Las bases de cada una mandan; GestorIA no solicita nada.",
          f"Fuente: BDNS, consultada el {r['consultado'][:16].replace('T', ' ')} (art. 20 Ley 38/2003).",
          "", "## Lo que no está en la BDNS", *BONIFICACIONES.get(pf.tipo, [])]
    return "\n".join(L)


def guardar(carpeta: Path, r: dict, t: str, pf, hoy: date) -> Path:
    salida = Path(carpeta) / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    f = salida / f"ayudas_{hoy.isoformat()}.md"
    f.write_text(f"# Ayudas · {pf.nombre} · {hoy.isoformat()}\n\n```\n{t}\n```\n", encoding="utf-8")
    plano = [{**{k: (v.isoformat() if isinstance(v, date) else float(v) if isinstance(v, Decimal) else v) for k, v in c.__dict__.items()},
              "url": c.url, "estado": estado(c, hoy)[0]} for c in r["convocatorias"]]
    (salida / "ayudas.json").write_text(json.dumps({"consultado": r["consultado"], "desde": r["desde"].isoformat(), "region": r["region"],
                                                     "palabras": r["palabras"], "convocatorias": plano}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    return f
