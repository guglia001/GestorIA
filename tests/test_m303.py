from datetime import date
from decimal import Decimal as D
from pathlib import Path

from gestoria import libros, perfil
from gestoria.modelos import m303

DEMO = Path(__file__).parent.parent / "ejemplos" / "sl-demo"


def test_periodo():
    assert m303.periodo_fechas(2026, "3T") == (date(2026, 7, 1), date(2026, 10, 1))
    assert m303.periodo_fechas(2026, "4T") == (date(2026, 10, 1), date(2027, 1, 1))


def test_rebu_margen_con_iva_dentro():
    assert m303.rebu(D("1250.00"), D("800.00"), D("21")) == (D("371.90"), D("78.10"))   # 450 × 21/121
    assert m303.rebu(D("600.00"), D("700.00"), D("21")) == (D("0.00"), D("0.00"))
    assert m303.rebu(D("50.00"), D("24.00"), D("4")) == (D("25.00"), D("1.00"))         # 26 × 4/104


def test_casillas_demo_3t():
    v, c = libros.cargar(DEMO)
    cas, avisos = m303.casillas(v, c, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    # REBU 2026/001 371,90/78,10 + 2026/002 272,73/57,27 + 2026/004 0 ; general 2026/003 250,00/52,50
    assert cas["07"] == D("894.63") and cas["09"] == D("187.87")
    # R2026/001 rectifica 2026/002 (REBU): −272,73 / −57,27
    assert cas["14"] == D("-272.73") and cas["15"] == D("-57.27")
    # intracomunitaria 20,00 al 21 %: devengo y deducción
    assert cas["10"] == D("20.00") and cas["11"] == D("4.20")
    assert cas["36"] == D("20.00") and cas["37"] == D("4.20")
    assert cas["28"] == D("300.00") and cas["29"] == D("63.00")
    assert cas["27"] == D("134.80")  # 187,87 + 4,20 − 57,27
    assert cas["45"] == D("67.20")   # 63,00 + 4,20
    assert cas["46"] == D("67.60") and cas["71"] == D("67.60")
    assert any("2026/004" in a for a in avisos)  # margen negativo, avisado


def test_tipo_declaracion():
    assert m303.tipo_declaracion(D("-12.34"), "3T", "I", True) == "C"
    assert m303.tipo_declaracion(D("-12.34"), "4T", "I", True) == "D"
    assert m303.tipo_declaracion(D("10"), "3T", "U", True) == "U"
    assert m303.tipo_declaracion(D("0"), "3T", "I", False) == "N"


def test_fichero_demo_mide_lo_que_dice_el_diseno():
    v, c = libros.cargar(DEMO)
    cas, _ = m303.casillas(v, c, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    f = m303.generar_fichero(perfil.cargar(DEMO), 2026, "3T", cas)
    assert f.startswith("<T303020263T0000><AUX>") and f.endswith("</T303020263T0000>")
    # el simulador rechaza el fichero sin página DID (E060010, 20-oct-2026)
    assert len(f) == 328 + 1581 + 1017 + 823 + 18
    assert "<T30301000> IB00000000BICIS DEMO SL" in f
    assert "<T303DID00>" in f


def test_prorrata_especial_vale_2():
    # el simulador solo admite 1 o 2 (E010171 y E010181, 20-oct-2026)
    from gestoria import dr
    v, c = libros.cargar(DEMO)
    cas, _ = m303.casillas(v, c, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    f = m303.generar_fichero(perfil.cargar(DEMO), 2026, "3T", cas)
    p1 = dr.cargar(dr.DISENOS / "DR303e26v101.xlsx")["01000"]
    pag = f[328:328 + 1581]
    for texto in ("- Opción por la aplicación de la prorrata especial", "Revocación de la opción"):
        c = p1.buscar(texto)
        assert pag[c.pos - 1:c.pos - 1 + c.lon] == "2"


def test_bien_de_menos_de_3005_euros_no_es_inversion_para_el_iva():
    au = Path(__file__).parent.parent / "ejemplos" / "autonomo-demo"
    v, c = libros.cargar(au)
    cas, avisos = m303.casillas(v, c, date(2026, 1, 1), date(2026, 4, 1), D("0"))
    # el ordenador de 1.200 € va con los corrientes (art. 108.Dos.5.º LIVA), junto al teléfono de enero
    assert cas["28"] == D("1230.00") and cas["29"] == D("258.30") and cas.get("30", D("0")) == D("0")
    assert any("PC-2026" in a and "108" in a for a in avisos)
