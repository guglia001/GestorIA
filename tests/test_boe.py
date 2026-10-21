from pathlib import Path

from gestoria import boe

HTML = (Path(__file__).parent / "datos" / "boe_lgt_201bis.html").read_text(encoding="utf-8")


def test_articulo_con_bis_y_su_texto():
    a = boe.extraer(HTML, "201 bis")
    assert a.startswith("Artículo 201 bis. Infracción tributaria por fabricación")
    assert "150.000 euros" in a
    assert "Artículo 202" not in a


def test_espacio_duro_entre_articulo_y_numero():
    # así viene la Ley 39/2015 en el BOE (20-oct-2026): «Artículo\xa043.»
    h = ('<h5 class="articulo">Artículo\xa043. Práctica de las notificaciones.</h5><p>2. Diez días.</p>'
         '<h5 class="articulo">Artículo\xa044. Otra.</h5>')
    a = boe.extraer(h, "43")
    assert a.startswith("Artículo 43. Práctica") and "Diez días" in a and "44" not in a


def test_articulo_que_no_esta():
    assert boe.extraer(HTML, "999") is None


def test_url():
    assert boe.url("BOE-A-2003-23186") == "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186&tn=0"
