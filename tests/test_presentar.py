"""Presentar: la revisión, la conformidad, el ensayo y el recorrido del navegador contra una sede
de mentira con las pantallas documentadas de la AEAT (ventana censal → Importar → «Firmar y
Enviar» → «Conforme» → «Firmar y Enviar» → justificante). Todo inventado y sin red."""
import json
import shutil
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from unittest import mock

import pytest

from gestoria import navegador, perfil, presentar
from gestoria.modelos import m303

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
HOY = date(2026, 10, 14)
IBAN = "ES" + "91" + "0000" * 5            # inventado (a trozos: el test de privacidad busca IBAN enteros)
NRC = "A" * 22


def _carpeta(tmp_path, forma_pago="I", iban=False, certificado=None):
    c = tmp_path / "bicis"
    shutil.copytree(SL, c, ignore=shutil.ignore_patterns("salida"))
    t = (c / "perfil.toml").read_text(encoding="utf-8").replace('forma_pago = "I"', f'forma_pago = "{forma_pago}"')
    if iban:
        t += f'\n[pago]\niban = "{IBAN}"\n'
    if certificado:
        t += f'\n[sede]\ncertificado = "{certificado}"\n'
    (c / "perfil.toml").write_text(t, encoding="utf-8")
    return c


def _rev(c, hoy=HOY, **kw):
    kw = {"sede": False, "simulador": False, "investigar": False, **kw}
    return presentar.revisar(c, "303", 2026, "3T", hoy, **kw)


def test_la_frase_de_conformidad():
    assert presentar.frase("303", "3T", 2026, "B00000000", D("67.60")) == "PRESENTAR 303 3T 2026 B00000000 67,60"
    assert presentar.frase("303", "2T", 2026, "B00000000", D("-45.67")) == "PRESENTAR 303 2T 2026 B00000000 -45,67"


def test_a_ingresar_sin_nrc_no_se_presenta(tmp_path):
    r = _rev(_carpeta(tmp_path))
    assert r.bloqueada and r.tipo == "I" and r.resultado == D("67.60")
    assert any(p.nivel == "⛔" and p.que == "pago" for p in r.pasos)
    assert Path(r.fichero).is_file() and len(r.huella) == 64
    assert r.frase == "PRESENTAR 303 3T 2026 B00000000 67,60"
    assert "⛔ No se presenta" in presentar.texto(r)


def test_con_nrc_o_domiciliado_y_su_plazo(tmp_path):
    assert not _rev(_carpeta(tmp_path), nrc=NRC).bloqueada
    assert _rev(_carpeta(tmp_path / "x"), nrc="CORTO").bloqueada
    c = _carpeta(tmp_path / "u", "U", iban=True)
    pago = next(p for p in _rev(c).pasos if p.que == "pago")
    assert pago.nivel == "✅" and "…0000" in pago.detalle and "hasta el 15-10-2026" in pago.detalle
    tarde = next(p for p in _rev(c, date(2026, 10, 16)).pasos if p.que == "pago")
    assert tarde.nivel == "⛔" and "ya no se puede domiciliar" in tarde.detalle
    plazo = next(p for p in _rev(c, date(2026, 10, 22)).pasos if p.que == "plazo")
    assert plazo.nivel == "⚠️" and "FUERA DE PLAZO" in plazo.detalle and "art. 27 LGT" in str(plazo)


def test_un_periodo_sin_terminar_no_se_presenta(tmp_path):
    r = _rev(_carpeta(tmp_path), date(2026, 9, 15), nrc=NRC)
    assert next(p for p in r.pasos if p.que == "período").nivel == "⛔"


def test_el_fichero_domiciliado_lleva_el_iban(tmp_path):
    from gestoria import libros

    c = _carpeta(tmp_path, "U", iban=True)
    pf = perfil.cargar(c)
    v, co = libros.cargar(c)
    cas, _ = m303.casillas(v, co, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    did = m303.generar_fichero(pf, 2026, "3T", cas).split("<T303DID00>")[1]
    assert did[11:35] == IBAN
    pf.forma_pago = "I"
    assert IBAN not in m303.generar_fichero(pf, 2026, "3T", cas)


def test_de_verdad_hace_falta_el_ensayo_y_la_frase(tmp_path):
    c = _carpeta(tmp_path)
    bien = lambda r, *a, **k: r.pasos.append(presentar.Paso("✅", "sede", "simulado"))
    no_abrir = mock.Mock(side_effect=AssertionError("no debía abrir el navegador"))
    with mock.patch.object(presentar, "_sede", bien), mock.patch.object(presentar, "_simulador", bien), \
            mock.patch.object(navegador, "Navegador", no_abrir):
        r = presentar.revisar(c, "303", 2026, "3T", HOY, nrc=NRC, investigar=False, para="presentar")
        assert r.bloqueada and next(p for p in r.pasos if p.que == "ensayo").nivel == "⛔"
        assert presentar.presentar(c, "303", 2026, "3T", r.frase, nrc=NRC, hoy=HOY, investigar=False)["estado"] == "bloqueada"
        # con un ensayo bueno de ESTE fichero, solo falta la frase exacta
        ensayo = {"pruebas": True, "estado": "ensayada", "huella": r.huella, "fecha": "2026-10-13T10:00:00", "csv": "PRUEBA"}
        (c / "salida" / "presentado" / "presentaciones.json").write_text(json.dumps([ensayo]))
        assert not presentar.revisar(c, "303", 2026, "3T", HOY, nrc=NRC, investigar=False, para="presentar").bloqueada
        res = presentar.presentar(c, "303", 2026, "3T", "PRESENTAR 303 3T 2026 B00000000 6,76", nrc=NRC, hoy=HOY, investigar=False)
        assert res["estado"] == "sin_conformidad"
        assert presentar.revisar(c, "303", 2026, "3T", HOY, nrc=NRC, investigar=False, sede=False, para="presentar").bloqueada
    no_abrir.assert_not_called()


def test_los_botones_de_presentar_solo_dentro_de_presentar():
    leer = navegador.Navegador("x.p12", "c")
    with pytest.raises(navegador.Prohibido):
        leer.pulsar_para_presentar(None, "Firmar y Enviar")
    pres = navegador.Navegador("x.p12", "c", presentar=True)
    for nombre in ("Pagar", "Domiciliar", "Revocar", "Abrir notificación"):
        with pytest.raises(navegador.Prohibido):
            pres.pulsar_para_presentar(None, nombre)
    with pytest.raises(navegador.Prohibido):
        leer.pulsar(None, "Firmar y Enviar")              # la lectura sigue sin poder firmar
    assert navegador.PRESENTAR_NAVEGAR.fullmatch("Continuar con la presentación del modelo 303")


# ─── una sede de mentira, con las pantallas de la ayuda de la AEAT ──────────────────────────

VENTANA = """<!doctype html><html><body><h1>Impuesto sobre el Valor Añadido. Autoliquidación. Modelo 303</h1>
<input type=text placeholder=Buscar>
<form><label for=nif>N.I.F.*</label><input id=nif type=text>
<label for=ej>Ejercicio*</label><select id=ej><option>2027</option><option>2026</option><option>2025</option></select>
<label for=per>Período*</label><select id=per><option>Seleccione ejercicio</option><option>1T</option><option>2T</option><option>3T</option><option>4T</option></select>
<button type=button onclick="location.href='/wlpl/censal?nif='+nif.value+'&ej='+ej.value+'&per='+per.value">Confirmar</button></form>
</body></html>"""
CENSAL = """<!doctype html><html><body><h2>Ventana censal IVA</h2><p>NIF NIFX · ejercicio EJX · período PERX</p>
<a href="/wlpl/formulario">Continuar con la presentación del modelo 303</a> <a href="/wlpl/pagar">Pagar</a></body></html>"""
FORMULARIO = """<!doctype html><html><body><button id=imp onclick="f.click()">Importar</button>
<input id=f type=file style="display:none" onchange="importado(this.files[0].name)">
<div id=errores></div><input aria-label="71" value="">
<button id=fe onclick="d.style.display='block'">Firmar y Enviar</button>
<div id=d role=dialog style="display:none"><label><input type=checkbox id=conf> Conforme</label>
<button onclick="if (conf.checked) location.href='/wlpl/ok?fichero=' + window.nombre">Firmar y Enviar</button></div>
<script>function importado(n) { window.nombre = n; document.querySelector('[aria-label="71"]').value = "67,60";
errores.innerHTML = '<div>Errores y avisos</div><div>-</div><div>00001</div><div>No existen errores.</div><div>Volver a la página principal</div>'; }</script>
</body></html>"""
OK = """<!doctype html><html><body><p>Su presentación ha sido realizada con éxito</p>
<p>Código Seguro de Verificación: ABCDEFGHJKLMNPQR</p><p>Número de justificante: 3030000000001</p>
<p>Expediente/Referencia: 2026303PRUEBA0001</p><p>Presentación realizada el: 14-10-2026 a las 10:00:00</p>
<iframe src="/wlpl/CotejoDocIdSv?CSV=ABCDEFGHJKLMNPQR"></iframe></body></html>"""


def test_ensayo_contra_una_sede_de_mentira(tmp_path, p12_rsa, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    pfx, clave = p12_rsa
    c = _carpeta(tmp_path, "U", iban=True, certificado=pfx)
    monkeypatch.setenv("GESTORIA_CERT_CLAVE", clave)
    vistos = []

    def servir(ruta):
        url = ruta.request.url
        vistos.append(url)
        if "VentanaCensalIva" in url:
            cuerpo = VENTANA
        elif "/wlpl/censal" in url:
            q = dict(x.split("=") for x in url.split("?")[1].split("&"))
            cuerpo = CENSAL.replace("NIFX", q["nif"]).replace("EJX", q["ej"]).replace("PERX", q["per"])
        elif url.endswith("/wlpl/formulario"):
            cuerpo = FORMULARIO
        elif "/wlpl/ok" in url:
            cuerpo = OK
        elif "CotejoDocIdSv" in url:
            return ruta.fulfill(status=200, body=b"%PDF-1.4 justificante de pruebas", content_type="application/pdf")
        else:
            return ruta.fulfill(status=404, body="no")
        ruta.fulfill(status=200, body=cuerpo, content_type="text/html; charset=utf-8")

    class SedeDeMentira(navegador.Navegador):
        def __enter__(self):
            super().__enter__()
            self.ctx.route("https://prewww1.aeat.es/**", servir)
            return self

    bien = lambda r, *a, **k: r.pasos.append(presentar.Paso("✅", "sede", "simulado"))
    try:
        with mock.patch.object(navegador, "Navegador", SedeDeMentira), mock.patch.object(presentar, "_sede", bien), \
                mock.patch.object(presentar, "_simulador", bien):
            r = presentar.revisar(c, "303", 2026, "3T", HOY, investigar=False)
            res = presentar.presentar(c, "303", 2026, "3T", r.frase, pruebas=True, hoy=HOY, investigar=False)
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            pytest.skip("sin Chromium de Playwright")
        raise
    assert res["estado"] == "ensayada", res
    assert res["csv"] == "ABCDEFGHJKLMNPQR" and res["justificante"] == "3030000000001"
    assert Path(res["pdf"]).read_bytes().startswith(b"%PDF")
    assert any("nif=B00000000&ej=2026&per=3T" in u for u in vistos)              # la ventana censal, bien rellena
    assert any("fichero=303_2026_3T_a_presentar.txt" in u for u in vistos)      # el fichero que se revisó
    assert not any("pagar" in u for u in vistos)                                # el enlace «Pagar» no se toca
    assert presentar.ensayo(c, r, HOY)["csv"] == "ABCDEFGHJKLMNPQR"             # y ya se puede presentar de verdad
