from decimal import Decimal
from pathlib import Path

import pytest

from gestoria import dr

XLSX = Path(__file__).parent.parent / "gestoria" / "disenos" / "DR303e26v101.xlsx"


@pytest.fixture(scope="module")
def pags():
    return dr.cargar(XLSX)


def test_paginas_y_longitudes_del_diseno(pags):
    assert pags["01000"].longitud == 1581
    assert pags["03000"].longitud == 1017
    assert pags["DID00"].longitud == 823


def test_casillas_con_su_posicion(pags):
    p1 = pags["01000"]
    assert (p1.campo("01").pos, p1.campo("01").lon) == (209, 17)
    assert p1.campo("03").pos == 231
    assert p1.campo("27").casilla == "27"  # «Total cuota devengada ( … ) [27]»
    assert p1.campo("02").constante == "00400"
    assert pags["03000"].campo("71").tipo == "N"


def test_constante_sin_la_palabra_constante(pags):
    # [169] viene como «"00050". Nota 7.»: el simulador la exige (E010541, 20-oct-2026)
    assert pags["01000"].campo("169").constante == "00050"
    # «"1" SI, "2" NO» son opciones, no una constante
    assert pags["01000"].buscar("Autoliquidación conjunta").constante is None


def test_formatear_numericos_y_signo(pags):
    p1 = pags["01000"]
    assert dr.formatear(p1.campo("01"), Decimal("1234.56")) == "00000000000123456"
    assert dr.formatear(pags["03000"].campo("71"), Decimal("-45.67")) == "N0000000000004567"
    assert dr.formatear(pags["03000"].campo("65"), Decimal("100")) == "10000"


def test_formatear_alfanumerico(pags):
    nombre = pags["01000"].buscar("Apellidos y nombre o Razón social")
    assert dr.formatear(nombre, "Bicis Demo, S.L.") == "BICIS DEMO S L".ljust(80)


def test_pagina_completa_con_constantes(pags):
    t = dr.pagina_texto(pags["01000"], {})
    assert len(t) == 1581
    assert t.startswith("<T30301000>") and t.endswith("</T30301000>")


def test_leer_es_la_inversa_de_escribir(pags):
    p1 = pags["01000"]
    valores = {p1.campo("01").n: Decimal("1234.56"), p1.campo("46").n: Decimal("-45.67")}
    t = dr.fichero("303", 2026, "3T", [dr.pagina_texto(p1, valores)])
    leidas = dr.leer_fichero(t, pags)
    assert leidas["01"] == Decimal("1234.56") and leidas["46"] == Decimal("-45.67")
    assert leidas["03"] == Decimal("0.00")


def test_fichero_cabecera_y_cierre():
    f = dr.fichero("303", 2026, "3T", ["X"])
    assert f.startswith("<T303020263T0000><AUX>")
    assert f.index("</AUX>") == 322 and f[328] == "X"
    assert f.endswith("</T303020263T0000>")
