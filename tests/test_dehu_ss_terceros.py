"""DEHú, Seguridad Social y comprobación de NIF, con respuestas inventadas de la misma forma que las
reales (21-oct-2026)."""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from gestoria import dehu, libros, navegador, seguridad_social, terceros

RAIZ = Path(__file__).parent.parent


def test_dehu_elementos():
    api = {"count": 1, "items": [{"emitterEntity": "Organismo Demo", "emitterSourceEntity": "Ministerio Demo",
                                  "identifier": "0000000000001", "concept": "Notificación administrativa",
                                  "postalDelivery": True, "availabilityDate": "2026-10-06T20:31:08+02:00",
                                  "expirationDate": "2026-10-16T23:59:59+02:00", "bondType": "TITULAR"}]}
    e = dehu.elementos(api)
    assert e[0]["organismo"] == "Organismo Demo" and e[0]["en_papel"] and e[0]["caduca"] == "2026-10-16T23:59"
    assert dehu.elementos({"items": []}) == [] and dehu.resumen({"pendientes": []}).startswith("✅")


AREA = """Hola, Ana
Número de la Seguridad Social (NUSS): 280000001234
Estás de alta en la Seguridad Social
Aquí puedes ver tu situación con la Seguridad Social, el régimen al que perteneces y fecha de alta en la Seguridad Social.
Trabajador Autónomo
Desde 1 jun 2026
EMPRESA DEMO,S.L.
Régimen General
Desde 4 abr 2025
Ver relación laboral
Tu vida laboral
1.200 días en alta
3 años, 3 meses y 15 días
900,00 € de base de cotización
Última cuota
300,00 €
Además, por regularización de cuotas anteriores, se cargarán: 25.50 €
Cargo a partir del 31 oct 2026
Tus documentos
Consulta aquí los documentos generados en los últimos trámites y actividades que has realizado en la Tesorería de la Seguridad Social.
Alta en RETA. Resolución
Ana Demo Perez
1 jun 2026
Ver todos tus documentos
"""


def test_area_personal_de_import_ass():
    d = seguridad_social.area_personal_de(AREA)
    assert d["de_alta"] and d["nuss"] == "********1234"
    assert d["altas"] == [{"regimen": "Trabajador Autónomo", "empresa": "", "desde": "2026-06-01"},
                          {"regimen": "Régimen General", "empresa": "EMPRESA DEMO,S.L.", "desde": "2025-04-04"}]
    assert (d["cuota_autonomo"], d["regularizacion"], d["cargo"]) == ("300,00 €", "25,50 €", "2026-10-31")
    assert d["dias_cotizados"] == "1.200" and d["documentos"] == [{"documento": "Alta en RETA. Resolución", "fecha": "2026-06-01"}]


def test_vnif_peticion_y_respuesta():
    x = terceros.peticion([("B00000026", "Transportes Demo SL")])
    assert "<vnif:Nif>B00000026</vnif:Nif>" in x and "VNifV2Ent" in x
    r = terceros.respuesta('<env:Envelope><env:Body><VNifV2Sal:VNifV2Sal xmlns:VNifV2Sal="x"><VNifV2Sal:Contribuyente>'
                           "<VNifV2Sal:Nif>B00000026</VNifV2Sal:Nif><VNifV2Sal:Nombre>TRANSPORTES DEMO SOCIEDAD LIMITADA"
                           "</VNifV2Sal:Nombre><VNifV2Sal:Resultado>IDENTIFICADO</VNifV2Sal:Resultado></VNifV2Sal:Contribuyente>"
                           "</VNifV2Sal:VNifV2Sal></env:Body></env:Envelope>")
    assert r == [{"nif": "B00000026", "nombre_censo": "TRANSPORTES DEMO SOCIEDAD LIMITADA", "resultado": "IDENTIFICADO"}]


def test_terceros_de_los_libros_y_hallazgos():
    v, c = libros.cargar(RAIZ / "ejemplos" / "sl-demo")
    pares = terceros.de_los_libros(v, c)
    assert [(n, p) for n, _, p in pares] == [("B00000018", "cliente"), ("B00000026", "proveedor"), ("B00000034", "proveedor")]
    filas = [{"nif": "B00000026", "nombre": "Transportes Demo SL", "nombre_censo": "TRANSPORTES DEMO SL", "resultado": "IDENTIFICADO"},
             {"nif": "B00000034", "nombre": "Recambios Demo SL", "nombre_censo": "OTRA RAZON DEMO SL", "resultado": "IDENTIFICADO"},
             {"nif": "B00000018", "nombre": "Club Ciclista Demo", "nombre_censo": "", "resultado": "NO IDENTIFICADO"}]
    h = terceros.hallazgos(filas, {n: p for n, _, p in pares})
    assert [x["nivel"] for x in h] == ["🟡", "🔴"]
    assert "OTRA RAZON DEMO SL" in h[0]["texto"] and "NO está en el censo" in h[1]["texto"]
    assert terceros.mismo_nombre("Transportes Demo, S.L.", "TRANSPORTES DEMO SL")


def test_el_navegador_no_pulsa_lo_que_cambia_cosas():
    import pytest

    for nombre in ("Buscar", "Consultar", "Aceptar", "Enviar", "Todos", "Desplegar", "Mi Situación Tributaria",
                   "Mis Socios / Partícipes", "DNIe o certificado", "Acceso DNIe / Certificado electrónico",
                   "Entrar en tu área personal", "Notificaciones pendientes", "Acceder a DEHú"):
        navegador.comprobar(nombre)
    for nombre in ("Firmar y enviar", "Presentar declaración", "Pagar todas mis deudas", "Comparecer", "Revocación masiva",
                   "Renuncia Masiva", "Confirmación masiva", "Prórroga masiva", "Modificar", "Alta de Domicilio de Notificaciones",
                   "Solicitar certificado", "Contestar requerimiento", "Aportar documentación", "Cambio de Domicilio Fiscal"):
        with pytest.raises(navegador.Prohibido):
            navegador.comprobar(nombre)
