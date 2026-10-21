"""`gestoria ayudas` (con una BDNS inventada) y `gestoria deducciones` (las reglas contra los libros de
ejemplo), sin red. Los tests `live` salen a la BDNS y al BOE: son los que avisan si Hacienda cambia una cifra."""
import re
import shutil
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from gestoria import ayudas, banco, deducciones, libros, perfil
from gestoria.__main__ import main

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
AU = RAIZ / "ejemplos" / "autonomo-demo"
HOY = date(2026, 10, 21)

# ─── una BDNS inventada ─────────────────────────────────────────────────────────────────────
ARBOL = [{"id": 1, "descripcion": "ES - ESPAÑA", "children": [
    {"id": 48, "descripcion": "ES5 - ESTE", "children": [
        {"id": 58, "descripcion": "ES53 - ILLES BALEARS", "children": [{"id": 60, "descripcion": "ES532 - Mallorca", "children": []}]}]},
    {"id": 25, "descripcion": "ES3 - COMUNIDAD DE MADRID", "children": [
        {"id": 26, "descripcion": "ES30 - COMUNIDAD DE MADRID", "children": [{"id": 27, "descripcion": "ES300 - Madrid", "children": []}]}]}]},
    {"id": 227, "descripcion": "FR - FRANCE", "children": []}]
FILAS = [
    {"id": 1, "numeroConvocatoria": "900001", "descripcion": "Ayudas a la digitalización del comercio local 2026", "fechaRecepcion": "2026-10-16",
     "nivel1": "LOCAL", "nivel2": "VILLADEMO", "nivel3": "AYUNTAMIENTO DEMO"},
    {"id": 2, "numeroConvocatoria": "900002", "descripcion": "Bonos de compra para el comercio de proximidad", "fechaRecepcion": "2026-10-08",
     "nivel1": "AUTONOMICA", "nivel2": "ILLES BALEARS", "nivel3": "CONSELL DEMO"},
    {"id": 3, "numeroConvocatoria": "900003", "descripcion": "Subvenciones a la contratación indefinida 2026", "fechaRecepcion": "2026-07-01",
     "nivel1": "ESTATAL", "nivel2": "ESTADO", "nivel3": "MINISTERIO DEMO"}]
PYME = [{"descripcion": "PYME Y PERSONAS FÍSICAS QUE DESARROLLAN ACTIVIDAD ECONÓMICA"}]
DETALLES = {
    "900001": {"codigoBDNS": "900001", "organo": {"nivel1": "LOCAL", "nivel2": "VILLADEMO", "nivel3": "AYUNTAMIENTO DEMO"},
               "descripcion": FILAS[0]["descripcion"], "fechaRecepcion": "2026-10-16", "abierto": True, "fechaInicioSolicitud": "2026-10-17",
               "fechaFinSolicitud": "2026-11-15", "presupuestoTotal": 84177.81, "tiposBeneficiarios": PYME,
               "regiones": [{"descripcion": "ES532 - Mallorca"}], "descripcionFinalidad": "Comercio, Turismo y Pymes",
               "urlBasesReguladoras": "https://villademo.example/bases", "sedeElectronica": "https://sede.villademo.example",
               "instrumentos": [{"descripcion": "SUBVENCIÓN Y ENTREGA DINERARIA SIN CONTRAPRESTACIÓN "}]},
    "900002": {"codigoBDNS": "900002", "organo": {"nivel1": "AUTONOMICA", "nivel2": "ILLES BALEARS", "nivel3": "CONSELL DEMO"},
               "descripcion": FILAS[1]["descripcion"], "fechaRecepcion": "2026-10-08", "abierto": False, "fechaInicioSolicitud": None,
               "fechaFinSolicitud": None, "textFin": "15 días hábiles desde la publicación en el BOIB", "presupuestoTotal": 800000,
               "tiposBeneficiarios": PYME, "regiones": [{"descripcion": "ES53 - ILLES BALEARS"}]},
    "900003": {"codigoBDNS": "900003", "organo": {"nivel1": "ESTATAL", "nivel2": "ESTADO", "nivel3": "MINISTERIO DEMO"},
               "descripcion": FILAS[2]["descripcion"], "fechaRecepcion": "2026-07-01", "abierto": False, "fechaInicioSolicitud": "01/08/2026",
               "fechaFinSolicitud": "30/09/2026", "presupuestoTotal": 1000000, "tiposBeneficiarios": PYME, "regiones": [{"descripcion": "ES - ESPAÑA"}]},
}


def bdns_falsa(peticiones: list | None = None):
    def _get(ruta, **p):
        if peticiones is not None:
            peticiones.append((ruta, p))
        if ruta == "regiones":
            return ARBOL
        if ruta == "convocatorias/busqueda":
            texto = ayudas._norm(p.get("descripcion", ""))
            return {"content": [f for f in FILAS if texto in ayudas._norm(f["descripcion"])], "totalElements": 3}
        if ruta == "convocatorias":
            return DETALLES[p["numConv"]]
        raise AssertionError(ruta)
    return _get


def test_la_region_y_sus_padres(monkeypatch):
    monkeypatch.setattr(ayudas, "_get", bdns_falsa())
    assert [r["nombre"] for r in ayudas.regiones()][:3] == ["ESPAÑA", "ESTE", "ILLES BALEARS"]     # Francia no entra
    plano = []

    def andar(n, padres):   # la lista plana que sale del árbol inventado
        cod, _, nombre = n["descripcion"].partition(" - ")
        plano.append({"id": n["id"], "codigo": cod, "nombre": nombre, "padres": padres})
        for h in n["children"]:
            andar(h, padres + [n["id"]])
    andar(ARBOL[0], [])
    assert ayudas.ids_region("Mallorca", plano) == [60, 58, 48, 1]
    assert ayudas.ids_region("madrid", plano) == [27, 26, 25, 1]           # la provincia antes que la comunidad
    assert ayudas.ids_region("ES53", plano) == [58, 48, 1]
    with pytest.raises(ValueError, match="ninguna región"):
        ayudas.ids_region("Villademo", plano)


def test_buscar_ordena_por_estado_y_cuenta_las_palabras(monkeypatch):
    peticiones = []
    monkeypatch.setattr(ayudas, "_get", bdns_falsa(peticiones))
    r = ayudas.buscar("Mallorca", ["comercio", "digitalización"], HOY, dias=120, maximo=10)
    assert [c.numero for c in r["convocatorias"]] == ["900001", "900002", "900003"]     # abierta · sin fecha · cerrada
    a, b, c = r["convocatorias"]
    assert ayudas.estado(a, HOY) == ("🟢", "abierta hasta el dom 15-nov-2026") and a.palabras == ["comercio", "digitalización"]
    assert ayudas.estado(b, HOY)[0] == "⚪" and "15 días hábiles" in ayudas.estado(b, HOY)[1] and b.palabras == ["comercio"]
    assert ayudas.estado(c, HOY) == ("🔴", "cerrada el mié 30-sep-2026") and c.fin == date(2026, 9, 30)    # fecha en dd/mm/aaaa
    assert a.presupuesto == D("84177.81") and a.url.endswith("/convocatoria/900001") and r["total_encontradas"] == 3
    busquedas = [p for ruta, p in peticiones if ruta == "convocatorias/busqueda"]
    assert len(busquedas) == 3 and all(p["tiposBeneficiario"] == 3 and p["regiones"] == "60,58,48,1" and p["fechaDesde"] == "23/06/2026" for p in busquedas)
    pf = perfil.cargar(SL)
    t = ayudas.texto(r, pf, HOY)
    assert "desde el mar 23-jun-2026 en España y Mallorca, y las que hablan de comercio, digitalización" in t
    assert "🟢 abierta hasta el dom 15-nov-2026 · AYUNTAMIENTO DEMO (local)" in t and "presupuesto 84.177,81 €" in t
    assert "BDNS 900001" in t and "bases: https://villademo.example/bases" in t and "art. 20 Ley 38/2003" in t
    assert "3 convocatoria(s) con detalle de 3 encontradas: 1 abiertas, 0 por abrir, 1 sin fecha estructurada, 1 cerradas" in t
    assert "`gestoria deducciones`" in t                                           # lo que no está en la BDNS


def test_cli_ayudas_guarda_el_informe(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ayudas, "_get", bdns_falsa())
    c = tmp_path / "sl"
    shutil.copytree(SL, c, ignore=shutil.ignore_patterns("salida"))
    assert main(["--carpeta", str(c), "ayudas", "--max", "5"]) == 0
    out = capsys.readouterr().out
    assert "AYUNTAMIENTO DEMO" in out and "guardado en" in out
    assert (c / "salida" / "ayudas.json").is_file() and list((c / "salida").glob("ayudas_*.md"))
    # --region y --palabras mandan sobre perfil.toml
    assert main(["--carpeta", str(c), "ayudas", "--region", "Madrid", "--palabras", "contratación"]) == 0
    assert "en España y Madrid, y las que hablan de contratación" in capsys.readouterr().out


# ─── deducciones ────────────────────────────────────────────────────────────────────────────

def _hallazgos(carpeta, hoy=HOY):
    pf = perfil.cargar(carpeta)
    v, co = libros.cargar(carpeta)
    hs = deducciones.revisar(pf, v, co, libros.ajustes(carpeta), banco.cargar(carpeta), hoy)
    return {h.regla.clave: h for h in hs}


def test_las_reglas_estan_bien_formadas():
    claves = [r.clave for r in deducciones.REGLAS]
    assert len(claves) == len(set(claves))
    for r in deducciones.REGLAS:
        assert set(r.aplica) <= {"autonomo", "sl"} and r.tipo in deducciones.TIPOS and r.boe[0].startswith("BOE-A-") and r.cifra
        if r.patron:
            re.compile(r.patron)


def test_sl_demo():
    h = _hallazgos(SL)
    assert set(h) == {r.clave for r in deducciones.REGLAS if "sl" in r.aplica}
    assert h["nueva_creacion"].estado == "✅" and h["reducida"].estado == "✅"
    assert h["nivelacion"].estado == "ℹ️" and "15 %" in h["nivelacion"].texto
    assert h["atenciones"].estado == "ℹ️" and "30,63 €" in h["atenciones"].texto          # 1 % de 3.062,89
    assert h["capitalizacion"].estado == "ℹ️" and "96,58 €" in h["capitalizacion"].texto   # 20 % de 482,89
    assert h["servicios"].estado == "✅" and h["servicios"].importe == D("140.00")           # transportes + software
    assert h["sin_factura"].estado == "✅" and h["no_deducibles"].estado == "✅"
    assert h["alquiler"].estado == "⚠️" and "no consta" in h["alquiler"].texto
    assert not any(x.estado == "⛔" for x in h.values())


def test_autonomo_demo():
    h = _hallazgos(AU, date(2026, 12, 31))
    assert set(h) == {r.clave for r in deducciones.REGLAS if "autonomo" in r.aplica}
    assert h["reta"].estado == "✅" and "300,00 € al mes" in h["reta"].texto and h["reta"].importe == D("3600.00")
    assert h["suministros"].estado == "✅" and h["suministros"].importe == D("60.00")       # las dos de telefonía
    assert h["inversiones"].estado == "✅" and "1 inversión(es) por 1.200,00 €" in h["inversiones"].texto
    assert h["servicios"].importe == D("150.00")                                             # la inversión no cuenta aquí
    assert h["dificil"].estado == "ℹ️" and h["dificil"].importe == D("352.00")              # 5 % de 7.040
    assert h["inicio"].estado == "ℹ️" and h["plan_pensiones"].estado == "ℹ️"
    assert h["seguro_salud"].estado == "⚠️" and h["manutencion"].estado == "⚠️"


def test_lo_que_no_deduce_sale_con_prohibido(tmp_path, capsys):
    c = tmp_path / "au"
    shutil.copytree(AU, c, ignore=shutil.ignore_patterns("salida"))
    with (c / "libros" / "compras.csv").open("a", encoding="utf-8") as f:
        f.write("2026-10-02;M-1;Multa DGT;Q1234567D;100,00;0;0,00;corriente;interior;no\n"
                "2026-10-03;S-1;Bar Demo;;20,00;10;2,00;corriente;interior;si\n"
                "2026-10-04;G-1;Gasolinera Demo SL;B00000034;50,00;21;10,50;corriente;interior;si\n")
    h = _hallazgos(c, date(2026, 12, 31))
    assert h["no_deducibles"].estado == "⛔" and "Multa DGT" in h["no_deducibles"].texto
    assert h["sin_factura"].estado == "⛔" and "sin NIF" in h["sin_factura"].texto and "no deducibles" in h["sin_factura"].texto
    assert h["vehiculo"].estado == "⚠️" and "50 %" in h["vehiculo"].texto
    assert h["manutencion"].estado == "✅" and "Bar Demo" in h["manutencion"].texto
    assert main(["--carpeta", str(c), "deducciones"]) == 1                                  # hay ⛔
    out = capsys.readouterr().out
    assert "## Lo que no deduce" in out and "⛔ Multas, sanciones" in out and list((c / "salida").glob("deducciones_*.md"))


def test_comprobar_busca_la_cifra_en_el_boe(monkeypatch):
    from gestoria import boe

    def articulo(id_boe, numero):
        return {"texto": f"Artículo {numero}.\nUna cifra: 500 euros, 30 por ciento, 26,67, 5 por ciento, 20 por ciento, 1.500 euros, "
                         "gratuito, 1 por ciento, 15 por ciento, 10 por ciento, 25 por ciento, 9.000 euros, 40 %, arrendamiento o "
                         "subarrendamiento de bienes inmuebles urbanos, 50 por 100, 300 euros, factura original, multas y sanciones, joyas, "
                         "normas del Impuesto sobre Sociedades, factura.", "url": f"https://www.boe.es/{id_boe}", "consultado": "2026-10-21"}

    monkeypatch.setattr(boe, "articulo", articulo)
    c = deducciones.comprobar()
    assert set(c) == {r.clave for r in deducciones.REGLAS} and all(x["ok"] for x in c.values())
    monkeypatch.setattr(boe, "articulo", lambda i, n: {"texto": f"Artículo {n}.\nOtra cosa.", "url": "u", "consultado": "2026-10-21"})
    c = deducciones.comprobar()
    assert not any(x["ok"] for x in c.values())
    pf = perfil.cargar(SL)
    t = deducciones.texto(_hallazgos(SL).values(), pf, HOY, 3, 12, c)
    assert "no encuentro «15 por ciento» en el art. 29" in t and "leídos en el BOE ahora mismo" in t


@pytest.mark.live
def test_las_cifras_de_las_reglas_siguen_en_el_boe():
    """Si Hacienda cambia un límite (los 500 € del seguro, el 1 % de atenciones…), esto falla esa noche."""
    c = deducciones.comprobar()
    assert all(x["ok"] for x in c.values()), {k: v["url"] for k, v in c.items() if not v["ok"]}


@pytest.mark.live
def test_la_bdns_responde():
    r = ayudas.buscar("Madrid", ["autónomos"], date.today(), dias=180, maximo=2)
    assert r["total_encontradas"] > 0 and r["ids"][-1] == ayudas.ESPANA
    assert all(c.numero and c.titulo and c.url for c in r["convocatorias"])
