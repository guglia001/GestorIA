import json

from gestoria import manuales


def test_buscar_sin_acentos_y_frase_primero(tmp_path):
    paginas = [
        {"pag": 1, "url": "x.pdf", "texto": "Régimen general del impuesto."},
        {"pag": 2, "url": "x.pdf", "texto": "En el régimen especial de bienes usados, la base es el margen."},
        {"pag": 3, "url": "x.pdf", "texto": "Margen y bienes; usados en otra parte. Régimen."},
    ]
    (tmp_path / "iva.jsonl").write_text("\n".join(json.dumps(p) for p in paginas), encoding="utf-8")
    r = manuales.buscar("regimen especial de bienes usados", ["iva"], cache=tmp_path)
    assert [x["pagina"] for x in r] == [2]
    r = manuales.buscar("bienes usados margen", ["iva"], cache=tmp_path)
    assert {x["pagina"] for x in r} == {2, 3}
