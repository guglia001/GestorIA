from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from gestoria import libros, perfil, sede
from gestoria.modelos import m303

DEMO = Path(__file__).parent.parent / "ejemplos" / "sl-demo"


@pytest.mark.live
def test_demo_3t_pasa_el_simulador(tmp_path):
    v, c = libros.cargar(DEMO)
    cas, _ = m303.casillas(v, c, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    f = tmp_path / "303.txt"
    f.write_text(m303.generar_fichero(perfil.cargar(DEMO), 2026, "3T", cas), encoding="latin-1")
    r = sede.validar("303", 2026, f, tmp_path)
    # el NIF del ejemplo es inventado: el único error admitido es que no está en el censo
    otros = [e for e in r["errores"] if not e.startswith(sede.NO_IDENTIFICADO)]
    assert r["importado"] and otros == [], r["errores"] or r["texto"][-3000:]
    # Con un NIF fuera del censo el formulario no abre sus páginas: no hay casillas que cotejar.
    # Con un NIF real (variable GESTORIA_NIF_REAL) sí: ver test_nif_real_coteja_casillas.
    assert r["casillas_aeat"] == {}


@pytest.mark.live
def test_nif_real_coteja_casillas(tmp_path):
    import os
    nif, nombre = os.environ.get("GESTORIA_NIF_REAL"), os.environ.get("GESTORIA_NOMBRE_REAL")
    if not nif or not nombre:
        pytest.skip("sin GESTORIA_NIF_REAL y GESTORIA_NOMBRE_REAL (un NIF dado de alta en el censo)")
    v, c = libros.cargar(DEMO)
    cas, _ = m303.casillas(v, c, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    pf = perfil.cargar(DEMO)
    pf.nif, pf.nombre = nif, nombre
    f = tmp_path / "303.txt"
    f.write_text(m303.generar_fichero(pf, 2026, "3T", cas), encoding="latin-1")
    r = sede.validar("303", 2026, f, tmp_path)
    assert r["sin_errores"], r["errores"]
    # el formulario de la AEAT recalcula los totales y llega a lo mismo
    assert r["casillas_aeat"]["71"] == D("67.60")
    assert r["casillas_aeat"]["27"] == D("134.80") and r["casillas_aeat"]["45"] == D("67.20")
