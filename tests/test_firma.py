"""Firmar con AutoFirma: ficheros (PAdES, CAdES) y el gancho para las sedes que firman desde la
web. Con un certificado de prueba inventado; sin AutoFirma instalada, lo que la necesita se salta."""
import base64
from pathlib import Path

import pytest

from gestoria import firma

con_autofirma = pytest.mark.skipif(not firma.ejecutable(), reason="AutoFirma no está instalada")


def test_formato_segun_el_fichero(tmp_path):
    (tmp_path / "f.xml").write_text('<?xml version="1.0"?><fe:Facturae xmlns:fe="x"/>')
    (tmp_path / "o.xml").write_text('<?xml version="1.0"?><escrito/>')
    assert firma.formato_de(Path("a.pdf")) == "pades" and firma.formato_de(Path("a.txt")) == "cades"
    assert firma.formato_de(tmp_path / "f.xml") == "facturae" and firma.formato_de(tmp_path / "o.xml") == "xades"


@con_autofirma
def test_firma_pades_y_cades_con_autofirma(tmp_path, p12_rsa):
    pypdf = pytest.importorskip("pypdf")
    pfx, clave = p12_rsa
    w = pypdf.PdfWriter()
    w.add_blank_page(width=595, height=842)
    w.write(tmp_path / "escrito.pdf")
    salida = firma.firmar_fichero(tmp_path / "escrito.pdf", pfx, clave)
    assert salida.name == "escrito_firmado.pdf"
    campos = pypdf.PdfReader(str(salida)).get_fields() or {}
    assert any(v.get("/FT") == "/Sig" for v in campos.values())
    cades = firma.firmar_datos("Texto con acentos: áéí\n".encode("utf-8"), "cades", pfx, clave, config="mode=implicit")
    assert cades[:1] == b"\x30" and len(cades) > 500                     # una estructura CMS (DER)
    with pytest.raises(firma.ErrorFirma, match="(?i)contrase"):
        firma.firmar_datos(b"x", "cades", pfx, "otra")


PAGINA = """<!doctype html><html><body><input id=r><script>
var AutoScript = (function () { return {
  cargarAppAfirma: function () { throw "la aplicación no debería abrirse"; },
  sign: function (d, a, f, p, ok, ko) { ko("x", "la página no debería firmar por su cuenta"); } }; })();
AutoScript.cargarAppAfirma();
AutoScript.sign(DATOS, "SHA256withRSA", "CAdES", "mode=implicit",
  function (firma, cert) { document.getElementById("r").value = "OK " + firma + " " + cert; },
  function (t, m) { document.getElementById("r").value = "KO " + m; });
</script></body></html>"""


def _pagina(datos_js: str, firmar) -> str:
    sync_api = pytest.importorskip("playwright.sync_api")
    try:
        with sync_api.sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context()
            firma.enganchar(ctx, firmar)
            pg = ctx.new_page()
            pg.set_content(PAGINA.replace("DATOS", datos_js))
            pg.wait_for_function("document.getElementById('r').value !== ''", timeout=60000)
            valor = pg.input_value("#r")
            b.close()
            return valor
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip("sin Chromium de Playwright")
        raise


def test_el_gancho_atiende_el_sign_de_la_pagina():
    vistos = []

    def firmar(op, datos, alg, fmt, params):
        vistos.append((op, base64.b64decode(datos), alg, fmt, params))
        return "FIRMA", "CERT"

    assert _pagina('btoa("hola sede")', firmar) == "OK FIRMA CERT"
    assert vistos == [("sign", b"hola sede", "SHA256withRSA", "CAdES", "mode=implicit")]


def test_sin_datos_ni_fichero_la_pagina_recibe_el_error(p12_rsa):
    assert _pagina('""', firma.con_certificado(*p12_rsa)).startswith("KO la página quiere que elijas el fichero")


@con_autofirma
def test_el_gancho_firma_con_autofirma_y_lo_apunta(tmp_path, p12_rsa):
    registro = tmp_path / "firmas.log"
    v = _pagina('btoa("hola sede")', firma.con_certificado(*p12_rsa, registro=registro))
    assert v.startswith("OK ") and len(v.split()[1]) > 600
    assert " cades sha256 9 bytes sha256=" in registro.read_text()
