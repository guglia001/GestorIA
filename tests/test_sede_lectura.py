"""Parsers de las pantallas de la sede con textos inventados con la misma forma que los reales."""
from gestoria import sede

LISTADO = ("Nº Certificado\tConcepto\tTipo\tTitular\tDestinatario\tEmitida\tNotificada\tModo\tLeída\n"
           "1234567890123\tREQUERIMIENTO DE DOCUMENTACION\tNotificación\tB00000000\tB00000000\t"
           "02/11/2026\t\tElectrónica\tNo\n")
RESUMEN_VACIO = ("Resumen de notificaciones No tiene notificaciones pendientes de notificar no leídas "
                 "No tiene notificaciones notificadas no leídas No tiene comunicaciones no leídas")
PRESENTADOS = "Expediente Periodo Estado 202630300000001X 3T ACEPTADA 16/10/2026 12:00:00"
OBLIGACIONES = "IVA. Autoliquidación\tTrimestral\t01/06/2026\t\t\tAlta\n"


def test_notificacion_sin_leer():
    n = sede.notificaciones_de(LISTADO)
    assert len(n) == 1 and n[0]["concepto"].startswith("REQUERIMIENTO") and n[0]["leida"] is False


def test_resumen():
    assert sede.no_leidas_de(RESUMEN_VACIO) == 0
    assert sede.no_leidas_de("Resumen de notificaciones No tiene comunicaciones no leídas") == 2
    assert sede.no_leidas_de("página de error") is None


def test_presentados_y_obligaciones():
    p = sede.presentados_de(PRESENTADOS)
    assert p == [{"expediente": "202630300000001X", "periodo": "3T", "estado": "ACEPTADA",
                  "presentada": "16/10/2026 12:00:00", "ejercicio": "2026"}]
    o = sede.obligaciones_de(OBLIGACIONES)
    assert o[0]["periodicidad"] == "Trimestral" and o[0]["baja"] is None
