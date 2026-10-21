"""Contra las sedes reales, con TU certificado: comprueban que las pantallas siguen teniendo la
forma que leen los lectores. Solo lectura. No corren en GitHub (un certificado no se sube a un
servicio de terceros): en tu equipo, `GESTORIA_PRUEBA_CARPETA=<tu carpeta> pytest -m live
tests/test_certificado_live.py`. Sin esa variable, se saltan."""
import os
from pathlib import Path

import pytest

CARPETA = os.environ.get("GESTORIA_PRUEBA_CARPETA")
pytestmark = [pytest.mark.live, pytest.mark.skipif(not CARPETA, reason="sin GESTORIA_PRUEBA_CARPETA (una carpeta con certificado)")]


@pytest.fixture(scope="module")
def pf():
    from gestoria import perfil

    p = perfil.cargar(Path(CARPETA).expanduser())
    if not p.tiene_certificado():
        pytest.skip("la carpeta no tiene [sede] certificado")
    return p


def test_certificado_y_censo_son_del_mismo_nif(pf):
    from gestoria import aeat, certificado, nif
    from gestoria.navegador import Navegador

    c = certificado.leer(pf.ruta_certificado(), pf.clave_certificado())
    with Navegador(pf.ruta_certificado(), pf.clave_certificado(), sitios=("aeat",)) as nav:
        d = aeat.consultar(nav, ("notificaciones", "censo", "obligaciones", "poderes", "deudas", "alertas", "accesos"),
                           es_sociedad=pf.tipo == "sl")
    assert not d["errores"], d["errores"]
    assert nif.normalizar(d["censo"]["nif"]) == nif.normalizar(c.nif)
    assert d["censo"]["neo_obligado"] in (True, False) and d["censo"]["domicilio_fiscal"]
    assert d["no_leidas"] is not None and d["obligaciones"] and d["accesos"]
    assert d["deudas"]["estado"] in ("sin_deudas", "con_deudas", "bloqueado")


def test_roi_y_comprobacion_de_nif(pf):
    from gestoria import aeat, certificado, terceros
    from gestoria.navegador import Navegador

    with Navegador(pf.ruta_certificado(), pf.clave_certificado(), sitios=("aeat",)) as nav:
        d = aeat.consultar(nav, ("roi",), nif=pf.nif)
    assert d["roi"]["en_roi"] in (True, False) and d["roi"]["csv"]
    f = terceros.comprobar([(pf.nif, pf.nombre)], certificado.contexto_tls(pf.ruta_certificado(), pf.clave_certificado()))
    assert f[0]["resultado"] == "IDENTIFICADO"


def test_dehu(pf):
    from gestoria import chequeo

    d = chequeo.dehu_aparte(pf.ruta_certificado(), pf.clave_certificado())
    assert "error" not in d, d
    assert "pendientes" in d["leidas"] and d["titular"]


def test_seguridad_social_con_el_certificado_personal(pf):
    from gestoria import seguridad_social
    from gestoria.navegador import Navegador

    if not pf.tiene_certificado("personal"):
        pytest.skip("sin [sede.personal]")
    with Navegador(pf.ruta_certificado("personal"), pf.clave_certificado("personal"), sitios=("seguridad_social",)) as nav:
        d = seguridad_social.consultar(nav)
    assert d["nuss"] and d["dias_cotizados"]
