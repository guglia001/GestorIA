from decimal import Decimal

from gestoria import D2
from gestoria.numeros import importe


def test_formatos_espanol_e_ingles():
    assert importe("1.234,56") == Decimal("1234.56")
    assert importe("12,5") == Decimal("12.50")
    assert importe("12.5") == Decimal("12.50")
    assert importe("-3,00 €") == Decimal("-3.00")
    assert importe("") is None and importe(None) is None


def test_d2_redondea_medio_arriba():
    assert D2("0.125") == Decimal("0.13")
