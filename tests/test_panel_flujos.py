from datetime import date
from decimal import Decimal as D
from pathlib import Path

from gestoria import calendario, flujos, panel
from gestoria.numeros import eur

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
AU = RAIZ / "ejemplos" / "autonomo-demo"
ICS = {k: "" for k in calendario.FEEDS}
ICS["iva"] = (RAIZ / "tests" / "datos" / "aeat_iva.ics").read_text(encoding="utf-8")
SEDE_LIMPIA = {"actualizado": "2026-10-02T08:00:00", "no_leidas": 0, "notificaciones": [], "obligaciones": [],
               "presentados": {"303": [], "036": []}}
SEDE_CON_AVISO = {"actualizado": "2026-10-02T08:00:00", "no_leidas": 1,
                  "notificaciones": [{"concepto": "REQUERIMIENTO", "emitida": "01/10/2026", "leida": False}],
                  "obligaciones": [], "presentados": {"303": [{"ejercicio": "2026", "periodo": "3T", "estado": "ALTA", "presentada": "x"}]}}


def test_eur():
    assert eur(D("1234.5")) == "1.234,50 €" and eur(D("-45.67")) == "-45,67 €"


def test_panel_sl_a_dos_dias_del_303_esta_en_rojo():
    d = panel.construir(SL, date(2026, 10, 18), ICS, SEDE_LIMPIA, certificados=[], chequeo=None)
    assert d["nivel"] == panel.ROJO
    p303 = next(p for p in d["plazos"] if p["modelo"] == "303")
    assert p303["dias"] == 2 and p303["nivel"] == panel.ROJO and not p303["presentado"]
    t = panel.render(d)
    assert "💰 Hucha: aparta" in t and "🧾 Libros registro: 6 facturas emitidas, 3 recibidas" in t and "✅ sin notificaciones" in t
    assert "2026/004" in t                       # el aviso del margen REBU
    assert "347: ningún tercero" in t


def test_panel_con_el_303_presentado_y_una_notificacion_sin_leer():
    d = panel.construir(SL, date(2026, 10, 18), ICS, SEDE_CON_AVISO, certificados=[], chequeo=None)
    p303 = next(p for p in d["plazos"] if p["modelo"] == "303")
    assert p303["presentado"] and p303["nivel"] == "✅"
    assert d["nivel"] == panel.ROJO              # por la notificación
    assert "REQUERIMIENTO" in panel.render(d)
    assert [x.periodo for x in d["hucha"] if x.modelo == "303"] == ["2026-4T"]


def test_panel_sin_calendario_cae_a_los_plazos_por_norma():
    d = panel.construir(AU, date(2026, 10, 2), {}, SEDE_LIMPIA, certificados=[], chequeo=None)
    assert d["plazos"] == [] and d["plazos_error"] is None
    assert any(x.modelo == "130" for x in d["hucha"])
    t = panel.render(d)
    assert "Agencia Demo SL" in t and "347" in t  # el radar del 347 del autónomo
    assert "Estimación directa simplificada" in t


def test_semana_escribe_el_informe_con_tareas(tmp_path):
    r = flujos.semana(SL, date(2026, 10, 18), tmp_path, ICS, SEDE_LIMPIA)
    md = Path(r["resumen"]).read_text(encoding="utf-8")
    assert r["resumen"].endswith("semana_2026-W42.md")
    assert "## Esta semana" in md and "Presentar el 303" in md and "Tener apartados" in md


def test_anual_sl_y_autonomo(tmp_path):
    r = flujos.anual(SL, 2026, tmp_path)
    md = Path(r["resumen"]).read_text(encoding="utf-8")
    assert "| 3T |" in md and "Impuesto sobre Sociedades estimado: 72,43 €" in md
    assert "formular las cuentas anuales" in md and r["ingresos"] == D("3062.89")
    r = flujos.anual(AU, 2026, tmp_path)
    md = Path(r["resumen"]).read_text(encoding="utf-8")
    assert "Agencia Demo SL" in md and "renta (modelo 100)" in md and "Rendimiento neto estimado: 7.040,00 €" in md
