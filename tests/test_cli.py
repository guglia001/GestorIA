import pytest

from gestoria.__main__ import main


def test_sin_orden_falla_con_ayuda(capsys):
    with pytest.raises(SystemExit):
        main([])


def test_303_del_ejemplo(tmp_path, capsys):
    from pathlib import Path
    demo = Path(__file__).parent.parent / "ejemplos" / "sl-demo"
    f = tmp_path / "303.txt"
    assert main(["--carpeta", str(demo), "303", "--ejercicio", "2026", "--periodo", "3T",
                 "--fichero", str(f)]) == 0
    out = capsys.readouterr().out
    assert f"[ 71] {'67.60':>12}" in out and "2026/004" in out
    assert f.read_text(encoding="latin-1").startswith("<T303020263T0000>")


def test_ordenes_de_lectura_sobre_los_ejemplos(capsys):
    from pathlib import Path
    sl = str(Path(__file__).parent.parent / "ejemplos" / "sl-demo")
    au = str(Path(__file__).parent.parent / "ejemplos" / "autonomo-demo")
    assert main(["--carpeta", au, "hucha", "--saldo", "1000"]) == 0
    assert "Cuota de autónomos" in capsys.readouterr().out
    assert main(["--carpeta", sl, "revisar"]) == 0          # solo avisos
    assert "2026/004" in capsys.readouterr().out
    assert main(["--carpeta", au, "umbrales", "--ejercicio", "2026"]) == 0
    assert "Agencia Demo SL" in capsys.readouterr().out
    assert main(["recargo", "1000", "--vencio", "2026-10-20", "--presentas", "2026-12-01"]) == 0
    assert "recargo 2 % = 20,00 €" in capsys.readouterr().out
