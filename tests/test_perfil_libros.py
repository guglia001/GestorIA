from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from gestoria import libros, perfil

DEMO = Path(__file__).parent.parent / "ejemplos" / "sl-demo"


def test_perfil_demo():
    p = perfil.cargar(DEMO)
    assert (p.nif, p.tipo, p.iva_regimen, p.forma_pago) == ("B00000000", "sl", "rebu", "I")


def test_libros_demo():
    v, c = libros.cargar(DEMO)
    assert len(v) == 6 and len(c) == 3
    assert v[0].fecha == date(2026, 7, 4) and v[0].total == Decimal("1250.00")
    assert v[4].rectifica == "2026/002"
    assert c[2].origen == "intracomunitaria" and c[2].cuota is None


def test_regimen_desconocido_falla(tmp_path):
    (tmp_path / "libros").mkdir()
    (tmp_path / "libros" / "ventas.csv").write_text(
        "fecha;factura;cliente;nif_cliente;regimen;tipo;base;cuota;total;coste;rectifica\n"
        "2026-07-01;F1;X;;inventado;21;10;2,1;;;\n")
    (tmp_path / "libros" / "compras.csv").write_text(
        "fecha;factura;proveedor;nif_proveedor;base;tipo;cuota;gasto;origen;deducible\n")
    with pytest.raises(ValueError, match="régimen"):
        libros.cargar(tmp_path)
