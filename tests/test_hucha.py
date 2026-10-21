from datetime import date
from decimal import Decimal as D
from pathlib import Path

from gestoria import hucha, libros, perfil

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
AU = RAIZ / "ejemplos" / "autonomo-demo"


def _partidas(carpeta, hoy, **kw):
    pf = perfil.cargar(carpeta)
    v, c = libros.cargar(carpeta)
    return pf, hucha.calcular(pf, v, c, libros.ajustes(carpeta), hoy, **kw)


def test_sl_el_2_de_octubre_tiene_el_3t_pendiente_y_el_4t_en_curso():
    pf, p = _partidas(SL, date(2026, 10, 2))
    por = {x.periodo: x for x in p if x.modelo == "303"}
    assert por["2026-3T"].importe == D("67.60")          # [71] del 3T
    assert por["2026-3T"].vence == date(2026, 10, 20)
    assert por["2026-4T"].vence == date(2027, 2, 1)


def test_sl_el_21_de_octubre_ya_no_cuenta_el_3t():
    _, p = _partidas(SL, date(2026, 10, 21))
    assert [x.periodo for x in p if x.modelo == "303"] == ["2026-4T"]


def test_sl_presentado_segun_la_sede_no_se_cuenta():
    _, p = _partidas(SL, date(2026, 10, 2), presentados={(2026, "3T")})
    assert [x.periodo for x in p if x.modelo == "303"] == ["2026-4T"]


def test_sl_sociedades_estimado_con_tipo_de_nueva_creacion():
    pf, p = _partidas(SL, date(2026, 10, 2))
    is_ = next(x for x in p if x.modelo == "200")
    # ingresos: 2026/001 1.250−78,10 · 2026/002 980−57,27 · 2026/003 250 · 2026/004 600 (margen < 0) · R2026/001 −922,73
    # costes REBU: 800+650+700−650 = 1.500 · compras corrientes: 120+180+20 = 320 → base 2.021,90 − 1.820 = 201,90
    assert is_.detalle["ingresos"] == D("2021.90") and is_.detalle["gastos"] == D("1820.00")
    assert is_.importe == D("30.29") and "15 %" in is_.nota            # nueva creación: 15 % de 201,90
    assert is_.vence == date(2027, 7, 26)
    _, p21 = _partidas(SL, date(2026, 10, 21))                       # con la venta 2026/005 del 4T
    assert next(x for x in p21 if x.modelo == "200").importe == D("72.43")
    p202 = next(x for x in p if x.modelo == "202")
    assert p202.importe == D("0") and "no aplica" in p202.nota


def test_tipo_is_por_articulo_29():
    class P:
        is_tipo = None; is_nueva_creacion = False; cifra_negocios_anterior = None; ejercicio_inicio = None
    pf = P()
    assert hucha.tipo_is(pf, 2026, D("100000"))[0] == D("25000.00")
    pf.cifra_negocios_anterior = D("500000")
    assert hucha.tipo_is(pf, 2026, D("100000"))[0] == D("20000.00")   # 19 % de 50.000 + 21 % de 50.000
    assert hucha.tipo_is(pf, 2025, D("100000"))[0] == D("21500.00")   # 21 % + 22 %
    assert hucha.tipo_is(pf, 2027, D("100000"))[0] == D("18500.00")   # 17 % + 20 %
    pf.cifra_negocios_anterior = D("5000000")
    assert hucha.tipo_is(pf, 2026, D("100000"))[0] == D("23000.00")
    pf.is_nueva_creacion = True
    assert hucha.tipo_is(pf, 2026, D("100000"))[0] == D("15000.00")
    pf.is_tipo = D("10")
    assert hucha.tipo_is(pf, 2026, D("100000"))[0] == D("10000.00")
    assert hucha.tipo_is(pf, 2026, D("-5"))[0] == D("0.00")


def test_autonomo_130_del_3t_pendiente_el_2_de_octubre():
    pf, p = _partidas(AU, date(2026, 10, 2))
    t3 = next(x for x in p if x.modelo == "130" and x.periodo == "2026-3T")
    # rendimiento neto 1-ene→30-sep: ingresos 7.000 − gastos (30+30+60+90; el PC es inversión) 210 = 6.790
    # 20 % = 1.358 − retenciones 855 − pagado 0 − minoración 100 (año anterior 8.500 ≤ 9.000) = 403
    assert t3.detalle["rn"] == D("6790.00") and t3.detalle["retenciones"] == D("855.00")
    assert t3.importe == D("403.00") and t3.vence == date(2026, 10, 20)
    t4 = next(x for x in p if x.modelo == "130" and x.periodo == "2026-4T")
    assert t4.importe == D("0.00")      # el 2 de octubre aún no hay facturas del 4T: 1.358 − 855 − 403 − 100 < 0
    # el 21 de octubre el 3T ya venció (y hay que apuntar su pago en ajustes.toml): rn 7.250 − 210 = 7.040
    # → 1.408 − 855 − 0 pagado − 100 = 453
    _, p21 = _partidas(AU, date(2026, 10, 21))
    assert [x.periodo for x in p21 if x.modelo == "130"] == ["2026-4T"]
    assert next(x for x in p21 if x.modelo == "130").importe == D("453.00")
    reta = next(x for x in p if x.modelo == "RETA")
    assert reta.importe == D("300.00") and reta.vence == date(2026, 10, 31)
    assert hucha.total(p) == sum(x.importe for x in p)


def test_minoracion_130():
    assert hucha.minoracion_130(None) == D("0")
    assert hucha.minoracion_130(D("9000")) == D("100")
    assert hucha.minoracion_130(D("11500")) == D("25")
    assert hucha.minoracion_130(D("12000.01")) == D("0")
