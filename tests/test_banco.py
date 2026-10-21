"""El banco: Norma 43, CSV, cookies y la conciliación con los libros. Datos inventados."""
import io
import os
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from unittest import mock

import pytest

from gestoria import banco, libros

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
HOY = date(2026, 10, 14)


def test_norma43_del_ejemplo_cuadra():
    [e] = banco.cargar(SL)
    assert e.saldo_inicial == D("3000.00") and e.saldo_final == D("6126.00") and e.cuadra is True
    assert len(e.movimientos) == 12 and (e.desde, e.hasta) == (date(2026, 7, 1), date(2026, 10, 13))
    m = e.movimientos[1]
    assert m.importe == D("-145.20") and m.concepto == "RECIBO TRANSPORTES DEMO SL" and m.comun == "03"


def test_conciliacion_del_ejemplo():
    v, c = libros.cargar(SL)
    r = banco.conciliar(banco.cargar(SL), v, c, HOY)
    casados = {f.factura for _, f in r.casados}
    assert casados == {"2026/001", "2026/002", "2026/003", "2026/004", "2026/005", "R2026/001", "T-0715", "R-0820", "SAAS-09"}
    assert [(cat, m.importe) for m, cat, _ in r.explicados] == [("comisiones e intereses del banco", D("-4.50"))]
    assert [m.importe for m in r.cobros_sin_factura] == [D("350.00")] and [m.importe for m in r.pagos_sin_factura] == [D("-89.00")]
    assert r.saldo == D("6126.00") and not r.sin_cobrar and not r.sin_pagar
    t = banco.texto(r, HOY, D("199.04"))
    assert "te sobran 5.926,96 €" in t and "BIZUM DE PEDRO DEMO" in t and "art. 97 LIVA" in t


def test_un_pago_a_hacienda_se_coteja_con_el_303_de_los_libros():
    v, c = libros.cargar(SL)
    e = banco.Extracto("x", [banco.Movimiento(date(2026, 10, 20), D("-67.60"), "ADEUDO AEAT MODELO 303"),
                             banco.Movimiento(date(2026, 10, 20), D("-47.60"), "AGENCIA TRIBUTARIA 303")])
    r = banco.conciliar([e], v, c, HOY)
    notas = [n for _, cat, n in r.explicados if cat == "Hacienda"]
    assert notas[0] == "cuadra con el 303 del 3T 2026 de tus libros"
    assert "sale 67,60 €" in notas[1] and "gestoria cotejar 303" in notas[1]


def test_csv_con_cargo_y_abono_a_la_espanola(tmp_path):
    f = tmp_path / "banco" / "movimientos.csv"
    f.parent.mkdir()
    f.write_text("Movimientos de la cuenta\n\nFecha;Fecha valor;Concepto;Cargo;Abono;Saldo\n"
                 "04/07/2026;04/07/2026;TPV VENTA;;1.250,00;4.250,00\n"
                 "15/07/2026;15/07/2026;RECIBO TRANSPORTES;145,20;;4.104,80\n", encoding="latin-1")
    [e] = banco.cargar(tmp_path)
    assert [(m.fecha, m.importe) for m in e.movimientos] == [(date(2026, 7, 4), D("1250.00")), (date(2026, 7, 15), D("-145.20"))]
    assert e.saldo_final == D("4104.80")


def test_cookies_netscape_json_y_permisos(tmp_path):
    n = tmp_path / "cookies.txt"
    n.write_text("# Netscape HTTP Cookie File\n.banco-demo.es\tTRUE\t/\tTRUE\t0\tSESION\tabc\n"
                 "#HttpOnly_www.banco-demo.es\tFALSE\t/\tTRUE\t0\tCSRF\txyz\n.otro.es\tTRUE\t/\tTRUE\t0\tNO\t1\n")
    os.chmod(n, 0o600)
    cs = banco.cargar_cookies(n)
    assert banco.cabecera_cookies(cs, "https://www.banco-demo.es/extracto") == "SESION=abc; CSRF=xyz"
    j = tmp_path / "cookies.json"
    j.write_text('[{"name": "SESION", "value": "abc", "domain": ".banco-demo.es", "path": "/"}]')
    os.chmod(j, 0o600)
    assert banco.cabecera_cookies(banco.cargar_cookies(j), "https://banco-demo.es/x") == "SESION=abc"
    os.chmod(j, 0o644)
    with pytest.raises(PermissionError):
        banco.cargar_cookies(j)


def test_descargar_guarda_el_extracto_y_rechaza_una_pagina(tmp_path):
    c = tmp_path / "cookies.txt"
    c.write_text(".banco-demo.es\tTRUE\t/\tTRUE\t0\tSESION\tabc\n")
    os.chmod(c, 0o600)
    pf = mock.Mock(banco={"cookies": str(c), "url_descarga": "https://www.banco-demo.es/n43?d={desde_es}&h={hasta_es}"})
    n43 = (SL / "banco" / "extracto_demo.n43").read_bytes()

    class Respuesta(io.BytesIO):
        headers = {}
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    with mock.patch("urllib.request.urlopen", return_value=Respuesta(n43)) as abrir:
        f = banco.descargar(pf, tmp_path, date(2026, 7, 1), date(2026, 10, 13))
    req = abrir.call_args[0][0]
    assert req.full_url.endswith("d=01/07/2026&h=13/10/2026") and req.get_header("Cookie") == "SESION=abc"
    assert f.name == "extracto_20260701_20261013.n43" and banco.cargar(tmp_path)[0].saldo_final == D("6126.00")
    with mock.patch("urllib.request.urlopen", return_value=Respuesta(b"<!doctype html><title>Acceso</title>")):
        with pytest.raises(ValueError, match="sesión ha caducado"):
            banco.descargar(pf, tmp_path)
