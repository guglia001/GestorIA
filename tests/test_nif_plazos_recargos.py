from datetime import date
from decimal import Decimal as D

from gestoria import nif, plazos, recargos


def test_nif_dni_nie_y_juridicas():
    assert nif.valido("12345678Z") and not nif.valido("12345678A")
    assert nif.valido("X1234567L") and not nif.valido("X1234567A")
    assert nif.valido("B12345674") and not nif.valido("B12345670")      # B: control numérico
    assert nif.valido("Q1234567D") and not nif.valido("Q12345674")      # Q: control alfabético (4 → D)
    assert nif.valido("B00000000") and nif.valido("00000000T")          # los de los ejemplos
    assert nif.valido("b-00000000") and not nif.valido("IE0000000X") and not nif.es_espanol("IE0000000X")


def test_plazos_por_norma_y_fin_de_semana():
    assert plazos.vence("303", 2026, "3T") == date(2026, 10, 20)
    assert plazos.vence("303", 2026, "4T") == date(2027, 2, 1)      # 30-ene-2027 es sábado → lunes
    assert plazos.vence("130", 2026, "1T") == date(2026, 4, 20)
    assert plazos.vence("200", 2026) == date(2027, 7, 26)           # 25-jul-2027 es domingo
    assert plazos.vence("347", 2026) == date(2027, 3, 1)            # 28-feb-2027 es domingo
    assert [m for m, _ in plazos.plazos_202(2026)] == ["abril", "octubre", "diciembre"]
    assert plazos.trimestre_de(date(2026, 10, 20)) == (2026, "4T")
    assert plazos.trimestre_anterior(2026, "1T") == (2025, "4T")


def test_recargo_por_meses_completos():
    r = recargos.calcular(D("1000"), date(2026, 10, 20), date(2026, 10, 25))
    assert (r.meses_completos, r.porcentaje, r.recargo, r.recargo_reducido) == (0, D("1"), D("10.00"), D("7.50"))
    r = recargos.calcular(D("1000"), date(2026, 10, 20), date(2027, 2, 19))
    assert (r.meses_completos, r.porcentaje) == (3, D("4"))
    r = recargos.calcular(D("1000"), date(2026, 10, 20), date(2027, 2, 20))
    assert (r.meses_completos, r.porcentaje) == (4, D("5"))


def test_recargo_pasados_doce_meses_lleva_intereses():
    r = recargos.calcular(D("1000"), date(2026, 10, 20), date(2027, 11, 19))
    assert r.porcentaje == D("15") and r.dias_interes == 30
    assert r.intereses == D("3.34")          # 1000 × 4,0625 % × 30/365
    assert r.total == D("1153.34")


def test_sin_recargo_en_plazo_o_a_compensar():
    assert recargos.calcular(D("1000"), date(2026, 10, 20), date(2026, 10, 20)).recargo == D("0")
    assert recargos.calcular(D("-45.67"), date(2026, 10, 20), date(2026, 12, 1)).recargo == D("0")
