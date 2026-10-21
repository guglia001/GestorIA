"""Plazos fiscales del contribuyente, sacados del calendario OFICIAL de la AEAT (sus iCalendar
públicos), no de una tabla escrita a mano.

Cada plazo sale marcado: obligatorio (modelo de alta en perfil.toml) o condicional (con la
condición que lo activa). Los feeds se bajan una vez al día a ~/.cache/gestoria/calendario/.
La AEAT publica el calendario de cada año a finales del anterior: si el feed se acaba antes del
horizonte pedido, se avisa.
Fuente: https://sede.agenciatributaria.gob.es/Sede/ayuda/calendario-contribuyente/icalendar/instrucciones-integrar-calendario.html
"""
from __future__ import annotations

import html
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

CACHE = Path.home() / ".cache" / "gestoria" / "calendario"
G = "https://www.google.com/calendar/ical/{}/public/basic.ics"
FEEDS = {
    "iva": G.format("517mcuhcis0lldnp9b7c0nk2q8%40group.calendar.google.com"),
    "sociedades": G.format("b7g1j3bod3gdjbka03uo6kr988%40group.calendar.google.com"),
    "renta_sociedades": G.format("aio2b0s64q65r7v87j5ma8fvog%40group.calendar.google.com"),
    "informativas": G.format("hqp9h5ft4snag42aea96791g28%40group.calendar.google.com"),
    "renta": G.format("invitado2aeat%40gmail.com"),
}
TRIMESTRALES = {"303", "349", "369", "111", "115", "130", "131", "202"}
# Modelos que pueden tocar según el tipo de contribuyente, con la condición que los activa.
CONDICIONALES = {
    "sl": {
        "390": "resumen anual del IVA, si se presenta el 303",
        "202": "pago fraccionado del IS: si el último 200 salió a pagar",
        "349": "solo con alta en el ROI y operaciones intracomunitarias",
        "369": "solo con alta en la ventanilla única (OSS)",
        "111": "solo si se pagan nóminas o facturas con retención",
        "190": "resumen anual del 111",
        "115": "solo si se alquila un local",
        "180": "resumen anual del 115",
        "347": "operaciones con un mismo tercero por encima de 3.005,06 € en el año",
    },
    "autonomo": {
        "390": "resumen anual del IVA, si se presenta el 303",
        "130": "pago fraccionado del IRPF en estimación directa (salvo 70 % de ingresos con retención)",
        "131": "pago fraccionado del IRPF en estimación objetiva (módulos)",
        "349": "solo con alta en el ROI y operaciones intracomunitarias",
        "111": "solo si se pagan nóminas o facturas con retención",
        "115": "solo si se alquila un local",
        "347": "operaciones con un mismo tercero por encima de 3.005,06 € en el año",
        "100": "declaración de la renta",
    },
}


@dataclass
class Plazo:
    fecha: date
    modelo: str
    obligatorio: bool
    condicion: str
    texto: str


def reglas(perfil) -> dict[str, tuple[bool, str]]:
    """modelo → (¿obligatorio?, condición). Los de alta en el perfil mandan."""
    out = {m: (False, c) for m, c in CONDICIONALES[perfil.tipo].items()}
    out.update({m: (True, "de alta en tu censo (perfil.toml)") for m in perfil.modelos})
    return out


def _feed(nombre: str, cache: Path = CACHE) -> str:
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"{nombre}.ics"
    if not f.exists() or time.time() - f.stat().st_mtime > 86400:
        req = urllib.request.Request(FEEDS[nombre], headers={"User-Agent": "Mozilla/5.0 gestoria"})
        with urllib.request.urlopen(req, timeout=60) as r:
            f.write_bytes(r.read())
    return f.read_text("utf-8", "ignore")


def eventos(ics: str) -> list[tuple[date, str]]:
    """[(día límite, línea «periodo: descripción: modelos»)] de un iCalendar de la AEAT."""
    ics = ics.replace("\r\n ", "").replace("\n ", "")
    out = []
    for ev in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics, re.S):
        d = re.search(r"^DTSTART[^:]*:(\d{8})", ev, re.M)
        desc = re.search(r"^DESCRIPTION:(.*)$", ev, re.M)
        if not d or not desc:
            continue
        dia = datetime.strptime(d.group(1), "%Y%m%d").date()
        txt = html.unescape(desc.group(1).replace("\\,", ",").replace("\\;", ";").replace("\\n", "\n"))
        txt = re.sub(r"<\s*(/li|br|/p|ul|/ul)\b[^>]*>", "\n", txt, flags=re.I)
        cabecera = ""
        for linea in (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", l)).strip() for l in txt.split("\n")):
            if not linea:
                continue
            if linea.endswith(":") and not re.search(r"\b\d{3}\b", linea):
                cabecera = linea  # «Ejercicio en curso:» → aplica a las líneas anidadas
                continue
            out.append((dia, f"{cabecera} {linea}".strip() if cabecera else linea))
    return out


def plazos(perfil, desde: date, hasta: date, ics: dict[str, str] | None = None) -> tuple[list[Plazo], date | None]:
    """Plazos del perfil entre dos fechas y el último día que cubre el calendario publicado.
    `ics` permite pasar los feeds ya bajados (tests); si no, se bajan."""
    r = reglas(perfil)
    nombres = [f for f in FEEDS if f != "renta"] + (["renta"] if perfil.tipo == "autonomo" else [])
    vistos, filas, ultimo = set(), [], None
    for nombre in nombres:
        texto = ics.get(nombre, "") if ics is not None else _feed(nombre)
        for dia, linea in eventos(texto):
            ultimo = max(ultimo or dia, dia)
            if not (desde <= dia <= hasta) or "grandes empresas" in linea.lower():
                continue
            for m in re.findall(r"\b(\d{3})\b", linea.split(":", 1)[-1]):
                # GestorIA es para quien declara por trimestres: las líneas mensuales de un
                # modelo trimestral («Septiembre 2026. Autoliquidación: 303») son de grandes
                # empresas y del registro de devolución mensual.
                if m not in r or (m in TRIMESTRALES and "trimestre" not in linea.lower()):
                    continue
                if (dia, m, linea) in vistos:
                    continue
                vistos.add((dia, m, linea))
                obligatorio, condicion = r[m]
                filas.append(Plazo(dia, m, obligatorio, condicion, linea))
    return sorted(filas, key=lambda p: (p.fecha, p.modelo)), ultimo


DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def fecha_txt(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day:02d}-{MESES[d.month - 1]}-{d.year}"
