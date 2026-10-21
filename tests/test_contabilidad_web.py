"""La contabilidad que sale de los libros y del banco cuadra por todos lados, y el panel web la
enseña entera. Con la empresa de ejemplo (inventada) y sin red."""
import json
import re
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from gestoria import banco, calendario, contabilidad as ct, libros, perfil, web
from gestoria.modelos import m303

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
AU = RAIZ / "ejemplos" / "autonomo-demo"
HOY = date(2026, 10, 14)
ICS = {k: "" for k in calendario.FEEDS}
ICS["iva"] = (RAIZ / "tests" / "datos" / "aeat_iva.ics").read_text(encoding="utf-8")


def _k(c=SL, hoy=HOY):
    pf = perfil.cargar(c)
    v, co = libros.cargar(c)
    return ct.generar(pf, v, co, libros.ajustes(c), 2026, hoy, banco.cargar(c)), v, co


def test_todo_cuadra_y_cada_asiento_tiene_su_documento():
    k, v, co = _k()
    assert k.asientos and all(a.cuadra and a.fuente for a in k.asientos)
    s = ct.sumas_y_saldos(k)
    assert sum(x["debe"] for x in s) == sum(x["haber"] for x in s)
    b = ct.balance(k)
    assert b["cuadra"] and b["total_activo"] == D("6126.00")              # el banco es todo el activo
    assert k.saldo(("572",)) == banco.cargar(SL)[0].saldo_final           # la 572 es el extracto


def test_la_liquidacion_del_iva_es_el_303_y_la_cifra_la_de_la_hucha():
    from gestoria import hucha

    k, v, co = _k()
    liq = next(a for a in k.asientos if a.concepto == "Liquidación del IVA del 3T 2026")
    cas, _ = m303.casillas(v, co, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    por_cuenta = {p.cuenta: p.debe or p.haber for p in liq.apuntes}
    assert (por_cuenta["477"], por_cuenta["472"], por_cuenta["4750"]) == (cas["27"], cas["45"], cas["71"])
    ingresos, gastos, _ = hucha.ingresos_gastos(v, co, date(2026, 1, 1), date(2027, 1, 1))
    pyg = dict(ct.perdidas_y_ganancias(k))
    assert pyg["1. Importe neto de la cifra de negocios"] == ingresos
    # la diferencia con los gastos de la hucha es la comisión del banco, que la hucha no ve
    assert -(pyg["4. Aprovisionamientos"] + pyg["7. Otros gastos de explotación"]) == gastos + D("4.50")
    assert not [x for x in k.avisos if "303 de los libros" in x]


def test_rebu_rectificativa_e_intracomunitaria():
    k, _, _ = _k()
    por = {a.concepto: {p.cuenta: (p.debe, p.haber) for p in a.apuntes} for a in k.asientos}
    rebu = por["Factura 2026/001 · Cliente Uno"]
    assert rebu == {"430": (D("1250.00"), D("0")), "700": (D("0"), D("1171.90")), "477": (D("0"), D("78.10"))}
    devuelta = por["Factura R2026/001 (rectifica 2026/002) · Cliente Dos"]
    assert devuelta["708"][0] == D("922.73") and devuelta["430"][1] == D("980.00")
    isp = por["Factura SAAS-09 de Software Demo Ltd"]                      # inversión del sujeto pasivo
    assert isp["472"][0] == isp["477"][1] == D("4.20") and isp["410"][1] == D("20.00")
    assert por["Factura R-0820 de Recambios Demo SL"]["600"][0] == D("180.00")   # [cuentas] de ajustes.toml
    assert por["Factura T-0715 de Transportes Demo SL"]["624"][0] == D("120.00")  # por el nombre del proveedor


def test_la_555_es_lo_que_falta_por_explicar():
    k, _, _ = _k()
    assert k.saldo(("555",), -1) == D("2521.00")                           # 2.260 de bicis + 350 de Bizum − 89 de tarjeta
    assert any("555" in x and "2.521,00 €" in x for x in k.avisos)


def test_autonomo_con_retenciones_tambien_cuadra():
    k, _, _ = _k(AU, date(2026, 12, 31))
    assert all(a.cuadra for a in k.asientos) and ct.balance(k)["cuadra"]
    primera = next(a for a in k.asientos if a.concepto.startswith("Factura 2026-001"))
    assert {p.cuenta for p in primera.apuntes} == {"430", "705", "477", "473"}  # el cliente retiene: 473


def test_el_panel_web_lleva_todo_dentro():
    d = web.datos(SL, HOY, calendario_ics=ICS, sede={"actualizado": "2026-10-14T07:30:00", "no_leidas": 0,
                                                       "notificaciones": [], "presentados": {}, "dehu_pendientes": 1})
    assert {"diario", "sumas", "pyg", "balance", "iva", "facturas", "trimestres", "banco", "plazos", "hucha",
            "radares", "nombres_303", "libros", "chequeo"} <= set(d)
    assert d["balance"]["cuadra"] and d["kpis"]["saldo"] == 6126.0 and len(d["diario"]) == len(_k()[0].asientos)
    assert any(f["estado"] == "cobrada" for f in d["facturas"]["emitidas"])
    assert [m["estado"] for m in d["banco"]["movimientos"]].count("por explicar") == 2
    # los radares del panel de la terminal, el nombre de cada casilla del 303 y la salud de los libros
    assert [u["nombre"] for u in d["radares"]["umbrales"]][:1] == ["Liquidación mensual del IVA y SII"] and d["radares"]["terceros_347"] == []
    assert d["nombres_303"]["27"] == "total cuota devengada" and d["libros"] == {"ventas": 6, "compras": 3, "errores": 0, "avisos": 1}
    h = web.html(d)
    assert h.startswith("<!doctype html>") and "BICIS DEMO SL" in h
    assert not re.search(r"<(script|link)[^>]+(src|href)=[\"']https?://", h)   # nada de internet: son tus cuentas
    assert "⬇ CSV" in h and '"terceros", "🤝", "Terceros"' in h                  # cada tabla se baja en CSV; vista de terceros
    datos = json.loads(re.search(r"const D = (.*?);\n", h, re.S).group(1))
    assert datos["empresa"]["nif"] == "B00000000"
