from datetime import date
from decimal import Decimal as D
from pathlib import Path

from gestoria import libros, perfil, revisar, umbrales
from gestoria.libros import Compra, Venta

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
AU = RAIZ / "ejemplos" / "autonomo-demo"


def _venta(factura, fecha, **kw):
    base = dict(cliente="X", nif_cliente="", regimen="general", tipo=D("21"), base=D("100"), cuota=D("21"),
                total=D("121"), coste=None, rectifica="")
    base.update(kw)
    return Venta(fecha=date.fromisoformat(fecha), factura=factura, **base)


def test_los_ejemplos_estan_limpios_salvo_lo_que_avisan_a_proposito():
    v, c = libros.cargar(SL)
    h = revisar.revisar(v, c, hoy=date(2026, 12, 31))
    assert [x.nivel for x in h] == ["aviso"] and "2026/004" in h[0].donde     # margen ≤ 0, a propósito
    v, c = libros.cargar(AU)
    assert revisar.revisar(v, c, hoy=date(2026, 12, 31)) == []


def test_numeracion_repetida_huecos_y_fechas():
    v = [_venta("F1", "2026-01-05"), _venta("F1", "2026-01-06"), _venta("F4", "2026-01-04")]
    h = revisar.numeracion(v)
    textos = [str(x) for x in h]
    assert any("repetido" in t for t in textos)
    assert any("falta F2, F3" in t for t in textos)
    assert any("anterior a la de" in t for t in textos)


def test_rectificativas_en_serie_propia_y_apuntando_a_algo():
    v = [_venta("F1", "2026-01-05"), _venta("F2", "2026-02-05", rectifica="F9", base=D("-100"), cuota=D("-21"))]
    h = revisar.revisar(v, [])
    assert any(x.nivel == "error" and "F9" in x.texto for x in h)
    assert any("serie propia" in x.texto for x in h)


def test_nif_cuota_y_compras():
    v = [_venta("F1", "2026-01-05", nif_cliente="B00000001"), _venta("F2", "2026-01-06", cuota=D("20"))]
    c = [Compra(date(2026, 1, 1), "C1", "Prov", "", D("10"), D("21"), D("2.10"), "corriente", "interior", True),
         Compra(date(2026, 1, 1), "C1", "Prov", "", D("10"), D("21"), D("2.10"), "corriente", "interior", True),
         Compra(date(2026, 1, 1), "C2", "Irl", "IE0000000X", D("10"), D("21"), D("2.30"), "corriente", "intracomunitaria", True)]
    h = revisar.revisar(v, c)
    s = "\n".join(str(x) for x in h)
    assert "B00000001 con el control mal" in s and "cuota 20.00 ≠" in s
    assert "sin NIF del proveedor" in s and "compra repetida" in s and "se autoliquida" in s


def test_radar_347_y_cifra_de_negocios():
    v, c = libros.cargar(AU)
    t = umbrales.radar_347(v, c, 2026)
    assert [x.nombre for x in t] == ["Agencia Demo SL"] and t[0].entregas == D("6897.00") and t[0].nif == "B00000026"
    assert umbrales.cifra_negocios(v, 2026) == D("7250.00")
    u = umbrales.umbrales(perfil.cargar(AU), v, 2026)
    assert u[0].nombre.startswith("Estimación directa simplificada") and u[0].pct == 1
    assert umbrales.barra(37) == "▓▓▓▓░░░░░░"
    v, c = libros.cargar(SL)
    assert umbrales.radar_347(v, c, 2026) == []
    assert umbrales.cifra_negocios(v, 2026) == D("3062.89")
