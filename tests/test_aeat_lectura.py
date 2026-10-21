"""Los lectores de las pantallas de la AEAT, con textos inventados que tienen la misma forma que los
reales (21-oct-2026: así salen de `inner_text`, con las celdas separadas por tabuladores)."""
from datetime import date

from gestoria import aeat

CENSO_SL = """Consulta de Datos Identificativos y Censales
Datos Identificativos del Contribuyente
NIF\tB00000000
Razón Social\tBICIS DEMO SL
Anagrama comercial\t
Administración de su domicilio fiscal\t28000 - DEMO
Forma Jurídica\tSOCIEDAD DE RESPONSABILIDAD LIMITADA
Fecha de Constitución\t01/06/2026
Obligado a notificaciones electrónicas\tSI - Fecha de alta: 01/06/2026
Suscrito voluntariamente a notificaciones electrónicas\tNo

Domicilio Fiscal

Tipo Vía\tNombre Vía\tTipo de Número\tNúmero de Casa
CALLE\tDEMO\tNUM\t1


Calificación de Número\tBloque\tPortal\tEscalera\tPlanta\tPuerta
\t\t2\t\t3\tB


Referencia Catastral\tIndicador de referencia catastral
\tInmueble sin RC asignada, situado en cualquier punto del territorio común


Código Postal\tMunicipio\tProvincia
28000\t28079 - MADRID\tMADRID


Domicilio Social
"""
CENSO_PERSONA = """Datos Identificativos del Contribuyente
NIF\t00000000T
Apellidos y Nombre\tDEMO PEREZ ANA
Administración de su domicilio fiscal\t28000 - DEMO
Obligado a notificaciones electrónicas\tNo
Suscrito voluntariamente a notificaciones electrónicas\tNo
Domicilio Fiscal
Tipo Vía\tNombre Vía\tTipo de Número\tNúmero de Casa
CALLE\tEJEMPLO\tNUM\t9
Código Postal\tMunicipio\tProvincia
28000\t28079 - MADRID\tMADRID
Agencia Tributaria
Accesibilidad
Aviso legal
"""
OBLIGACIONES = """Estado Sit. Trib.: ACTIVO
Descripción de la obligación\tPeriodicidad\tF. Alta Efec.\tF. Baja Efec.\tF. Ult. Modif.\tEstado

IS/ IRNR CON EP. DECLARACIÓN ANUAL\tANUAL\t02/06/2026\t \t02/06/2026\tALTA
IMP. SOBRE EL VALOR AÑADIDO.\tTRIMESTRAL\t01/06/2026\t \t01/06/2026\tALTA
IRPF PAGO FRACCIONADO (PROF.-EMPRES.)\tTRIMESTRAL\t01/01/2024\t31/12/2024\t31/12/2024\tBAJA
"""
SITUACION_HTML = """<ul class="AEAT_form"><li class="ancho_5 texto_cen">510</li><li class="ancho_4 texto_cen fondo_medio">
<script> if ("A"=="A") document.write('<strong>X</strong>'); else document.write('&nbsp;'); </script></li>
<li class="ancho_5 texto_cen">512</li><li class="ancho_9"><script> if ("01/06/2026".trim()!="") document.write('x'); </script></li></ul>
<ul class="AEAT_form"><li class="ancho_5 texto_cen">514</li><li class="ancho_4"><script> if (" "=="A") document.write('X'); </script></li></ul>
<ul class="AEAT_form"><li class="ancho_5 texto_cen">518</li><li class="ancho_4"><script> if ("A"=="A") document.write('X'); </script></li></ul>
<ul class="AEAT_form"><li class="ancho_5 texto_cen">525</li><li class="ancho_9"><script> if ("          ".trim()!="") document.write(''); </script></li></ul>
<ul class="AEAT_form"><li class="ancho_5 texto_cen">641</li><li class="ancho_9"><script> if ("02/06/2026".trim()!="") document.write(''); </script></li></ul>
"""
PODERES = """Núm. Referencia\tNIF / CIF Apoderado\tTrámite\tDescripción trámite\tProcedimiento\tEstado Actual\tFecha Baja\tVigente
20260601000000000001\tB00000026 - GESTORIA DEMO SL\tGENERALNOT\tPODER GENERAL PARA RECEPCIÓN DE NOTIFICACIONES\tZN01\tConfirmado\t01-06-2031\tSi
\t\t\t\t\t\t\t
Mostrados los registros 1 a 1 de un total de 1
"""
RESUMEN_PERSONA = """Resumen de notificaciones y comunicaciones no leídas
Notificaciones pendientes de notificar no leídas
Nº de certificado\tTitular\tDestinatario\tFecha de emisión
  1234567890123\t00000000T DEMO PEREZ ANA\t00000000T DEMO PEREZ ANA\t06-10-2026
No tiene notificaciones notificadas no leídas
Comunicaciones no leídas
Nº de certificado\tConcepto\tTitular\tFecha de emisión
  1234567890124\tAVISO DEMO\t00000000T DEMO PEREZ ANA\t15-06-2026
"""


def test_censo_de_una_sociedad():
    c = aeat.censo_de(CENSO_SL)
    assert (c["nif"], c["nombre"], c["neo_obligado"], c["neo_desde"], c["neo_voluntario"]) == \
        ("B00000000", "BICIS DEMO SL", True, "01/06/2026", False)
    assert c["domicilio_fiscal"] == "CALLE DEMO 1, portal 2, planta 3, puerta B, 28000 MADRID"
    assert "sin RC" in c["referencia_catastral"]


def test_censo_de_una_persona_sin_pie_de_pagina():
    c = aeat.censo_de(CENSO_PERSONA)
    assert c["nombre"] == "DEMO PEREZ ANA" and c["neo_obligado"] is False
    assert c["domicilio_fiscal"] == "CALLE EJEMPLO 9, 28000 MADRID" and "Accesibilidad" not in c["domicilio_fiscal"]


def test_obligaciones_y_sus_modelos():
    o = aeat.obligaciones_de(OBLIGACIONES)
    assert [x["estado"] for x in o] == ["ALTA", "ALTA", "BAJA"] and aeat.situacion_estado_de(OBLIGACIONES) == "ACTIVO"
    assert aeat.modelos_de_obligaciones(o) == {"200", "303", "390"}     # el 130 está de baja


def test_situacion_tributaria_regimenes():
    s = aeat.situacion_de(SITUACION_HTML)
    assert s["regimenes_iva"] == ["general", "REBU (operación por operación)"]
    assert s["otras"] == ["Impuesto sobre Sociedades desde 02/06/2026"]


def test_tablas_de_actividades_representantes_socios_y_avisos():
    act = aeat.actividades_de("Sección\tEpígrafe\tDenominación\tEstado\tF.Inicio\tF.Baja\tLocales\tNum.Ref.\n"
                              "Empresarial\t659.9\tComercio menor otros productos\tAlta\t01-06-2026\t\t\t\n")
    assert act[0]["epigrafe"] == "659.9" and act[0]["estado"] == "Alta"
    rep = aeat.representantes_de("\tNIF\tApellidos y Nombre\tSituación\tTipo de Representación\tFecha Última modificación\n\n"
                                 "1\t  00000000T\tDEMO PEREZ ANA\tALTA\tINDIVIDUAL\t01-06-2026 10.00\n")
    assert rep == [{"nif": "00000000T", "nombre": "DEMO PEREZ ANA", "situacion": "ALTA", "tipo": "INDIVIDUAL"}]
    soc = aeat.socios_de("NIF\n Apellidos y Nombre\nEstado\n%Part\n%Atrib\nTipo\n1\n00000000T\nDEMO PEREZ ANA\nAlta\n100\n0,00\nSocio\n")
    assert soc[0]["participacion"] == "100" and soc[0]["tipo"] == "Socio"
    av = aeat.avisos_de("Teléfono móvil: 600000123\nCorreo electrónico: demo@example.com\nApp Agencia Tributaria: No. Para...\nEstado: Alta\n")
    assert av == {"movil": "*** *** 123", "correo": "d***@example.com", "app": False, "estado": "Alta"}


def test_poderes():
    p = aeat.poderes_de(PODERES)
    assert len(p) == 1 and p[0]["nif"] == "B00000026" and p[0]["tramite"] == "GENERALNOT" and p[0]["vigente"]
    assert aeat.poderes_de("No se han obtenido resultados para estos datos") == []


def test_deudas_tres_casos():
    assert aeat.deudas_de("Pagar / Consultar deudas\nAvisos\nNo existen deudas para mostrar")["estado"] == "sin_deudas"
    b = aeat.deudas_de("DEMO tiene notificaciones pendientes.\nAntes de continuar acceda al enlace")
    assert b["estado"] == "bloqueado"
    c = aeat.deudas_de("Clave liquidación\tConcepto\tImporte\tPeriodo\nA0000000000000001\tIVA 2T\t120,50\tejecutivo\n")
    assert c["estado"] == "con_deudas" and c["deudas"][0]["Importe"] == "120,50"


def test_expedientes_alertas_accesos_y_roi():
    e = aeat.expedientes_de("Desplegar   Contraer   Actualizar\n\nAgencia Estatal de Administración Tributaria   (1)\n"
                            "Censales   (1)\n\nAdemás, le pueden interesar")
    assert e == [{"nombre": "Agencia Estatal de Administración Tributaria", "n": 1}, {"nombre": "Censales", "n": 1}]
    assert aeat.alertas_de("No existen Alertas para la Persona Consultada.") == []
    assert aeat.alertas_de("Mis Alertas(1)\n  Invitación demo\nPulse en cada alerta") == ["Invitación demo"]
    acc = aeat.accesos_de("Fecha y hora\tModo de autenticación\tCanal\n2026-10-21 08:00:00\tCertificado digital *\tNavegador\n")
    assert acc == [{"fecha": "2026-10-21 08:00:00", "modo": "Certificado digital", "canal": "Navegador"}]
    no = aeat.roi_de("Código Seguro de Verificación : DEMOCSV0000000001 A FECHA 21-10-2026 08:00:00 NO CONSTA NINGÚN OPERADOR "
                     "INTRACOMUNITARIO EN ESPAÑA CON EL NÚMERO DE IVA ESB00000000")
    si = aeat.roi_de("A FECHA 21-10-2026 08:00:00 CONSTA  UN OPERADOR INTRACOMUNITARIO EN ESPAÑA CON EL NÚMERO DE IVA ESB00000000")
    assert (no["en_roi"], no["csv"], no["fecha"], si["en_roi"]) == (False, "DEMOCSV0000000001", "21-10-2026 08:00:00", True)


def test_justificante_y_presentados():
    j = aeat.justificante_de("INFORMACIÓN DE LA PRESENTACIÓN DE LA DECLARACIÓN\nModelo 303\nPresentación realizada el: 16-10-2026 a las 11:00:00\n"
                             "Expediente/Referencia (nº registro asignado): 202630300000001X\nCódigo Seguro de Verificación: DEMOCSV0000000002\n"
                             "Número de justificante: 3030000000001\nVía de entrada: Presentación por Internet\nPresentador\n"
                             "NIF Presentador: B00000026\nApellidos y Nombre / Razón social: GESTORIA DEMO SL\nEn calidad de: Colaborador\n"
                             "A INGRESAR\nLa autenticidad de este documento…")
    assert (j["presentador_nif"], j["presentador"], j["en_calidad_de"], j["resultado"], j["csv"]) == \
        ("B00000026", "GESTORIA DEMO SL", "Colaborador", "A INGRESAR", "DEMOCSV0000000002")
    p = aeat.presentados_de("Expediente Periodo Estado 202630300000001X 3T ALTA 16/10/2026 11:00:00 Ver Ver")
    assert p[0]["ejercicio"] == "2026" and p[0]["periodo"] == "3T"


def test_datos_fiscales():
    t = ("DATOS IDENTIFICATIVOS\nNIF:\n00000000T\n\nRENDIMIENTOS DE TRABAJO\n\n"
         "Código\tNIF Pagador\tNombre Pagador\tClave\tRetribuciones Dinerarias\tRetenciones\n"
         "RTA0001\tB00000034\tEMPRESA DEMO SL\tEmpleado\t20.000,00\t3.000,00\n"
         "\tTOTAL\t20.000,00\t3.000,00\n\nCOTIZACIONES A REGÍMENES ESPECIALES\nCódigo\tNúmero Afiliación\tImporte Cotizado\n"
         "CT00001\t280000000000\t300,00\n")
    b = aeat.datos_fiscales_de(t)
    assert [x["seccion"] for x in b] == ["RENDIMIENTOS DE TRABAJO", "COTIZACIONES A REGÍMENES ESPECIALES"]
    assert b[0]["filas"][0]["Retenciones"] == "3.000,00" and b[0]["total"] is not None


def test_resumen_de_una_persona_y_el_plazo():
    r = aeat.resumen_de(RESUMEN_PERSONA)
    assert [(x["seccion"], x["concepto"], x["emitida"]) for x in r] == [("pendiente", "", "06-10-2026"),
                                                                         ("comunicacion", "AVISO DEMO", "15-06-2026")]
    assert aeat.no_leidas_de(RESUMEN_PERSONA) == 2
    # obligado a la vía electrónica: rechazo tácito a los 10 días naturales (art. 43.2 Ley 39/2015)
    p = aeat.plazo_notificacion("06-10-2026", True, date(2026, 10, 10))
    assert p["rechazo"] == date(2026, 10, 16) and "en 6 días" in p["texto"]
    assert "ya se entendió rechazada" in aeat.plazo_notificacion("06-10-2026", True, date(2026, 10, 20))["texto"]
    # no obligado: llega en papel y no hay rechazo a los 10 días (arts. 41.7, 42.1 y 43.2)
    n = aeat.plazo_notificacion("06-10-2026", False, date(2026, 10, 20))
    assert n["rechazo"] is None and "papel" in n["texto"]
    assert "si estás obligado" in aeat.plazo_notificacion("06-10-2026", None, date(2026, 10, 10))["texto"]
