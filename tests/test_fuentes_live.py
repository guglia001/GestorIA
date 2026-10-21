"""Pruebas contra las fuentes oficiales: avisan si la AEAT o el BOE cambian algo que usamos."""
import hashlib
import urllib.request
from datetime import date
from pathlib import Path

import pytest

from gestoria import boe, calendario, dr, perfil

RAIZ = Path(__file__).parent.parent
INDICE_DR = "https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-300-399.html"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 gestoria"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


@pytest.mark.live
def test_el_diseno_del_303_sigue_siendo_el_que_llevamos():
    """Si la AEAT publica una versión nueva (p. ej. v1.02), este test falla: hay que bajarla,
    pasar los tests y validar otra vez en el simulador."""
    nombre = "DR303e26v101.xlsx"
    indice = _get(INDICE_DR).decode("utf-8", "ignore")
    assert f"/archivos_26/{nombre}" in indice, "la AEAT ya no enlaza este diseño: ¿versión nueva?"
    oficial = _get("https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/"
                   f"DR_300_399/archivos_26/{nombre}")
    local = (dr.DISENOS / nombre).read_bytes()
    assert hashlib.sha256(oficial).hexdigest() == hashlib.sha256(local).hexdigest()


@pytest.mark.live
def test_calendario_oficial_trae_el_303():
    # el año en curso: la AEAT publica el del año siguiente a finales de este, así que mirar 366 días
    # hacia delante falla cada otoño hasta que sale el calendario nuevo
    p = perfil.cargar(RAIZ / "ejemplos" / "sl-demo")
    hoy = date.today()
    filas, ultimo = calendario.plazos(p, date(hoy.year, 1, 1), date(hoy.year, 12, 31))
    assert any(f.modelo == "303" and f.obligatorio for f in filas)
    assert ultimo is not None and ultimo >= date(hoy.year, 10, 20)


@pytest.mark.live
def test_boe_ley_del_iva_art_137():
    a = boe.articulo("BOE-A-1992-28740", "137")
    assert a["texto"] and "margen de beneficio" in a["texto"]
