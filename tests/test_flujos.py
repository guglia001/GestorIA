from datetime import date
from pathlib import Path

import pytest

from gestoria import flujos

DEMO = Path(__file__).parent.parent / "ejemplos" / "sl-demo"


@pytest.mark.parametrize("hoy, esperado", [
    (date(2026, 10, 2), (2026, "3T")),
    (date(2026, 1, 15), (2025, "4T")),
    (date(2026, 4, 1), (2026, "1T")),
    (date(2026, 12, 31), (2026, "3T")),
])
def test_ultimo_trimestre_cerrado(hoy, esperado):
    assert flujos.ultimo_trimestre_cerrado(hoy) == esperado


def test_trimestre_sin_validar_deja_fichero_y_resumen(tmp_path):
    r = flujos.trimestre(DEMO, 2026, "3T", validar=False, salida=tmp_path, calendario_ics={})
    assert Path(r["fichero"]).read_text(encoding="latin-1").startswith("<T303020263T0000>")
    md = Path(r["resumen"]).read_text(encoding="utf-8")
    assert "BICIS DEMO SL" in md and "| [71] | 67.60 |" in md
    assert "2026/004" in md                     # el aviso del margen negativo
    assert "no validado" in md.lower()
    assert "no presenta" in md.lower()
