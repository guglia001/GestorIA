from datetime import date
from pathlib import Path

from gestoria import calendario, perfil

RAIZ = Path(__file__).parent.parent
ICS = {k: "" for k in calendario.FEEDS}
# dos eventos reales del feed de IVA de la AEAT (20 y 30 de octubre de 2026)
ICS["iva"] = (RAIZ / "tests" / "datos" / "aeat_iva.ics").read_text(encoding="utf-8")


def test_303_del_trimestre_obligatorio_y_349_condicional():
    p = perfil.cargar(RAIZ / "ejemplos" / "sl-demo")
    filas, ultimo = calendario.plazos(p, date(2026, 10, 1), date(2026, 10, 31), ICS)
    claves = {(f.fecha, f.modelo, f.obligatorio) for f in filas}
    assert (date(2026, 10, 20), "303", True) in claves
    assert (date(2026, 10, 20), "349", False) in claves
    # la línea mensual del 303 del día 30 es de grandes empresas: fuera
    assert not any(f.modelo == "303" and f.fecha == date(2026, 10, 30) for f in filas)
    assert ultimo == date(2026, 10, 30)


def test_fecha_txt():
    assert calendario.fecha_txt(date(2026, 10, 20)) == "mar 20-oct-2026"
