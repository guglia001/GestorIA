"""El chequeo convierte lo leído en las sedes en hallazgos con su fuente. Datos inventados."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from gestoria import chequeo, cotejo, libros, perfil
from gestoria.modelos import m303

RAIZ = Path(__file__).parent.parent
SL = RAIZ / "ejemplos" / "sl-demo"
HOY = date(2026, 10, 21)


def _datos():
    return {
        "fecha": HOY.isoformat(),
        "certificados": {"principal": {"tipo": "representante", "entidad": "BICIS DEMO SL", "titular": "ANA DEMO PEREZ",
                                       "nif": "B00000000", "hasta": "2026-11-30"}, "personal": None},
        "aeat": {
            "no_leidas": 1,
            "resumen": [{"numero": "1234567890123", "seccion": "notificada", "concepto": "", "emitida": "15-10-2026"}],
            "censo": {"nif": "B00000000", "neo_obligado": True, "neo_desde": "01/06/2026", "neo_voluntario": False},
            "avisos": {"correo": "d***@example.com", "movil": "*** *** 123", "app": False, "estado": "Alta"},
            "obligaciones": [{"obligacion": "IMP. SOBRE EL VALOR AÑADIDO.", "periodicidad": "TRIMESTRAL", "alta": "01/06/2026", "baja": None, "estado": "ALTA"},
                             {"obligacion": "IS/ IRNR CON EP. DECLARACIÓN ANUAL", "periodicidad": "ANUAL", "alta": "01/06/2026", "baja": None, "estado": "ALTA"},
                             {"obligacion": "RETENC. E INGR. A CTA. RENDIM. TRABAJO/ACTIVIDADES PROFESIONALES", "periodicidad": "TRIMESTRAL",
                              "alta": "01/06/2026", "baja": None, "estado": "ALTA"}],
            "estado_censal": "ACTIVO",
            "situacion": {"regimenes_iva": ["general", "REBU (operación por operación)", "criterio de caja"]},
            "socios": [{"nif": "00000000T", "nombre": "DEMO PEREZ ANA", "estado": "Alta", "participacion": "100", "tipo": "Socio"}],
            "poderes_otorgados": [{"referencia": "1", "nif": "B00000026", "nombre": "GESTORIA DEMO SL", "tramite": "GENERALNOT",
                                   "descripcion": "PODER GENERAL PARA RECEPCIÓN DE NOTIFICACIONES", "estado": "Confirmado",
                                   "baja": "01-06-2031", "vigente": True}],
            "poderes_recibidos": [],
            "deudas": {"estado": "sin_deudas", "deudas": [], "texto": "no existen deudas"},
            "alertas": ["Invitación a suscripción a avisos informativos de la AEAT"],
            "accesos": [{"fecha": "2026-10-21 08:00:00", "modo": "Certificado digital", "canal": "Navegador"}],
            "presentados": {"303": [], "036": [{"expediente": "2026C000000000001", "periodo": "0A", "estado": "ALTA",
                                                "presentada": "01/06/2026 10:00:00", "ejercicio": "2026"}]},
            "roi": {"en_roi": False, "csv": "DEMOCSV0000000001", "fecha": "21-10-2026 08:00:00"},
            "errores": {},
        },
        "cotejos": [{"ejercicio": 2026, "periodo": "2T", "presentador": "GESTORIA DEMO SL", "en_calidad_de": "Colaborador",
                     "presentada": "15-07-2026", "difs": [{"casilla": "45", "nombre": "total a deducir", "presentado": D("100.00"),
                                                           "libros": D("80.00"), "diferencia": D("20.00")}]}],
        "dehu": {"pendientes": [{"organismo": "Ayuntamiento Demo", "identificador": "N1", "concepto": "Notificación",
                                 "puesta": "2026-10-19T10:00", "caduca": "2026-10-29T23:59", "en_papel": False}],
                 "comunicaciones": [], "leidas": ["pendientes"]},
        "terceros": {"filas": [{"nif": "B00000026", "nombre": "Transportes Demo SL", "nombre_censo": "", "resultado": "NO IDENTIFICADO"}],
                     "hallazgos": [{"nivel": "🔴", "nif": "B00000026", "texto": "proveedor Transportes Demo SL (B00000026): NO está en el censo"}]},
        "personal": {"seguridad_social": {"de_alta": True, "altas": [
            {"regimen": "Trabajador Autónomo", "empresa": "", "desde": "2026-06-01"},
            {"regimen": "Régimen General", "empresa": "EMPRESA DEMO,S.L.", "desde": "2025-04-04"}],
            "cuota_autonomo": "300,00 €", "regularizacion": "", "cargo": "2026-10-31", "dias_cotizados": "1.200"}},
    }


def test_evaluar_saca_cada_cosa_con_su_nivel():
    pf = perfil.cargar(SL)
    v, c = libros.cargar(SL)
    h = chequeo.evaluar(_datos(), pf, v, c, HOY)
    textos = {(x.nivel, x.area): x for x in h}
    rojos = [x for x in h if x.nivel == "🔴"]
    assert h == sorted(h, key=lambda x: chequeo.ORDEN[x.nivel])
    # notificación notificada sin abrir, obligado a la vía electrónica: el rechazo tácito se calcula
    notif = next(x for x in rojos if x.area == "AEAT")
    assert "1234567890123" in notif.texto and "2026-10-25" in notif.texto
    assert any(x.area == "DEHú" and "Ayuntamiento Demo" in x.texto and "2026-10-29" in x.texto for x in rojos)
    assert any(x.area == "terceros" for x in rojos)
    # el certificado caduca en 40 días → amarillo
    assert ("🟡", "certificado") in textos and "en 40 días" in textos[("🟡", "certificado")].texto
    amarillos = " | ".join(x.texto for x in h if x.nivel == "🟡")
    assert "GESTORIA DEMO SL (B00000026) puede recibir y ABRIR" in amarillos
    assert "la sede te tiene de alta en el 111" in amarillos                 # retenciones en el censo, no en el perfil
    assert "criterio de caja" in amarillos and "SL unipersonal" in amarillos
    assert "no coincide con tus libros" in amarillos and "20,00 €" in amarillos
    assert "pluriactividad" in amarillos and "Invitación" in amarillos
    assert any(x.area == "cotejo" or x.area == "presentado" for x in h)
    verdes = [x.texto for x in h if x.nivel == "🟢"]
    assert "sin deudas con la AEAT" in verdes
    assert chequeo.nivel_general(h) == "🔴"


def test_303_no_presentado_se_ve():
    pf = perfil.cargar(SL)
    v, c = libros.cargar(SL)
    d = _datos()
    h = chequeo.evaluar(d, pf, v, c, HOY)
    # alta el 1-jun-2026: se deben el 2T (venció el 20-jul) y el 3T (20-oct), y no constan
    faltan = [x.texto for x in h if x.area == "presentado" and x.nivel == "🔴"]
    assert any("303 del 2T 2026" in t for t in faltan) and any("303 del 3T 2026" in t for t in faltan)
    d["aeat"]["presentados"]["303"] = [{"expediente": "x", "periodo": p, "estado": "ALTA", "presentada": "16/10/2026 10:00:00",
                                        "ejercicio": "2026"} for p in ("2T", "3T")]
    assert not [x for x in chequeo.evaluar(d, pf, v, c, HOY) if x.area == "presentado" and x.nivel == "🔴"]


def test_vigia_solo_lo_urgente_y_markdown():
    pf = perfil.cargar(SL)
    v, c = libros.cargar(SL)
    h = chequeo.evaluar_vigia(_datos(), pf, HOY)
    assert h and all(x.nivel in ("🔴", "🟡", "🟢") for x in h)
    assert not any(x.area == "censo" for x in h)
    md = chequeo.markdown(_datos(), chequeo.evaluar(_datos(), pf, v, c, HOY), pf)
    assert md.startswith("# 🔴 Chequeo con certificado · BICIS DEMO SL") and "Solo lectura" in md and "## 🔴 Lo urgente" in md


def test_cotejo_del_fichero_presentado_con_los_libros(tmp_path):
    pf = perfil.cargar(SL)
    v, c = libros.cargar(SL)
    cas, _ = m303.casillas(v, c, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    f = tmp_path / "303.txt"
    f.write_text(m303.generar_fichero(pf, 2026, "3T", cas), encoding="latin-1")
    presentado = cotejo.leer_presentado(f)
    assert cotejo.cotejar_303(presentado, cas) == []
    # una gestoría que dedujo 20 € de más
    otro = dict(cas, **{"29": cas["29"] + 20, "45": cas["45"] + 20, "46": cas["46"] - 20, "71": cas["71"] - 20})
    difs = cotejo.cotejar_303(presentado, otro)
    assert [d["casilla"] for d in difs] == ["29", "45", "46", "71"]
    lineas = cotejo.explicar(cotejo.cotejar_303(otro, cas))
    assert any("se dedujo 20,00 € MÁS" in x for x in lineas)
    # lo que queda por compensar para el siguiente: [87] + lo que este salió a compensar
    assert cotejo.compensar_siguiente({"87": D("10.00"), "71": D("-45.67")}, "3T") == D("55.67")
    assert cotejo.compensar_siguiente({"87": D("10.00"), "71": D("-45.67")}, "4T") == D("10.00")
    assert cotejo.compensar_siguiente({"87": D("0.00"), "71": D("67.60")}, "3T") == D("0.00")
