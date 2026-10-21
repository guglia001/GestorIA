"""Las capturas del README: un octubre inventado de BICIS DEMO SL, con las órdenes de verdad.

    pip install -e '.[docs]'
    python docs/capturas.py          # todas, a docs/img/
    python docs/capturas.py --html   # deja también el HTML de cada una, para retocar el diseño

Cada captura es lo que imprime GestorIA (las mismas órdenes, el mismo código) sobre una copia de
`ejemplos/sl-demo` en una carpeta temporal. Solo se cambian el reloj y las sedes: lo que «leen» la
AEAT, la DEHú y la Seguridad Social está inventado aquí abajo y los certificados no existen, así
que ninguna captura puede llevar datos reales. Las dibuja Playwright y las comprime Pillow; a la
red solo salen las fuentes tipográficas y el calendario público de la AEAT.

El mes que se simula:
  01-oct 08:00  gestoria chequeo   el mensual: es el «último chequeo» que enseña el panel
  13-oct 07:30  gestoria vigia     la Diputación ha puesto una notificación en la DEHú
  14-oct 07:30  gestoria vigia     el Ayuntamiento pone otra: 🆕 y código 2       → img/vigia.webp
  14-oct 09:00  gestoria hoy       el panel                                       → img/hoy.webp
  14-oct 09:30  gestoria presentar la revisión antes de presentar el 303 del 3T     → img/presentar.webp
  14-oct 09:40  gestoria banco     el extracto conciliado con las facturas          → img/banco.webp
  14-oct 09:50  gestoria web       el panel contable: resumen y libro diario        → img/web.webp, img/web_diario.webp
  14-oct 09:55  gestoria deducciones  qué deduce y qué no, contra los libros        → img/deducciones.webp
  14-oct 10:00  gestoria ayudas    la Base de Datos Nacional de Subvenciones (inventada) → img/ayudas.webp
  20-oct        la gestoría presenta el 303 del 3T con 20,00 € de IVA deducido de más
  21-oct 08:00  gestoria chequeo   el informe que deja en salida/                 → img/chequeo.webp
  21-oct 08:10  gestoria cotejar   lo presentado contra los libros               → img/cotejar.webp
"""
from __future__ import annotations

import argparse
import contextlib
import html
import io
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
IMG = RAIZ / "docs" / "img"
VISIBLE = "~/.gestoria/bicis-demo"        # así se ve la carpeta de datos en las capturas
RELOJ = {"ahora": datetime(2026, 10, 1, 8, 0)}

# ─── el mundo inventado ─────────────────────────────────────────────────────────────────────

GESTORIA, NIF_GESTORIA = "GESTORIA DEMO SL", "B00000067"
IBAN = "ES" + "91" + "0000" * 5           # inventado, a trozos: el test de privacidad busca IBAN enteros
EXPEDIENTE = "2026303000000017"            # el 303 del 3T que presenta la gestoría
PRESENTADO = datetime(2026, 10, 20, 18, 42, 10)
DE_MAS = {"28": D("95.24"), "29": D("20.00")}   # una factura recibida que no está en los libros

CERTIFICADOS = {
    "principal": {"ruta": "~/certs/bicis-demo.p12", "tipo": "representante", "titular": "ANA DEMO PEREZ",
                  "nif_titular": "00000000T", "entidad": "BICIS DEMO SL", "nif_entidad": "B00000000",
                  "cargo": "ADMINISTRADOR UNICO", "emisor": "AC Representación", "desde": "2024-12-01",
                  "hasta": "2026-12-01", "nif": "B00000000"},
    "personal": {"ruta": "~/certs/ana-demo.p12", "tipo": "persona", "titular": "ANA DEMO PEREZ", "nif_titular": "00000000T",
                 "entidad": "", "nif_entidad": "", "cargo": "", "emisor": "AC FNMT Usuarios", "desde": "2024-03-15",
                 "hasta": "2028-03-15", "nif": "00000000T"},
}

# DEHú de la sociedad: organismo, identificador, concepto, puesta a disposición, caducidad, abierta el
DEHU = [("Diputación Demo", "NDEMO-2026-0147", "Liquidación del impuesto de vehículos 2026",
         "2026-10-12T09:14", "2026-10-22T23:59", date(2026, 10, 15)),
        ("Ayuntamiento Demo", "NDEMO-2026-0152", "Requerimiento: licencia de actividad",
         "2026-10-13T11:02", "2026-10-23T23:59", None)]

OBLIGACIONES = [
    {"obligacion": "IMP. SOBRE EL VALOR AÑADIDO.", "periodicidad": "TRIMESTRAL", "alta": "01/07/2026", "baja": None, "estado": "ALTA"},
    {"obligacion": "IS/ IRNR CON EP. DECLARACIÓN ANUAL", "periodicidad": "ANUAL", "alta": "01/07/2026", "baja": None, "estado": "ALTA"},
    {"obligacion": "RETENC. E INGR. A CTA. RENDIM. TRABAJO/ACTIVIDADES PROFESIONALES", "periodicidad": "TRIMESTRAL",
     "alta": "01/07/2026", "baja": None, "estado": "ALTA"},
]

JUSTIFICANTE = {"presentada": f"{PRESENTADO:%d-%m-%Y %H:%M:%S}", "expediente": EXPEDIENTE, "csv": "DEMOCSV0000000002",
                "justificante": "3030000000017", "via": "Internet", "presentador_nif": NIF_GESTORIA,
                "presentador": GESTORIA, "en_calidad_de": "Colaborador social", "resultado": "A INGRESAR"}


# La Base de Datos Nacional de Subvenciones: cuatro convocatorias inventadas, como las de verdad
BDNS_PYME = [{"descripcion": "PYME Y PERSONAS FÍSICAS QUE DESARROLLAN ACTIVIDAD ECONÓMICA"}]
BDNS = {
    "900001": {"codigoBDNS": "900001", "organo": {"nivel1": "LOCAL", "nivel2": "VILLADEMO", "nivel3": "AYUNTAMIENTO DEMO"},
               "descripcion": "Ayudas a la modernización y digitalización del comercio local 2026", "fechaRecepcion": "2026-10-09",
               "abierto": True, "fechaInicioSolicitud": "2026-10-10", "fechaFinSolicitud": "2026-11-15", "presupuestoTotal": 84177.81,
               "tiposBeneficiarios": BDNS_PYME, "regiones": [{"descripcion": "ES532 - Mallorca"}], "descripcionFinalidad": "Comercio, Turismo y Pymes",
               "urlBasesReguladoras": "https://villademo.example/ayudas/bases-2026", "sedeElectronica": "https://sede.villademo.example"},
    "900002": {"codigoBDNS": "900002", "organo": {"nivel1": "AUTONOMICA", "nivel2": "ILLES BALEARS", "nivel3": "DIRECCIÓN GENERAL DEMO DE INDUSTRIA"},
               "descripcion": "Subvenciones para la compra de bicicletas eléctricas de reparto por pymes y autónomos 2026", "fechaRecepcion": "2026-09-22",
               "abierto": True, "fechaInicioSolicitud": "2026-09-23", "fechaFinSolicitud": "2026-12-31", "presupuestoTotal": 400000,
               "tiposBeneficiarios": BDNS_PYME, "regiones": [{"descripcion": "ES53 - ILLES BALEARS"}], "descripcionFinalidad": "Industria y Energía",
               "urlBasesReguladoras": "https://demo.example/boib/2026/bicicletas", "sedeElectronica": "https://sede.demo.example/bicicletas"},
    "900003": {"codigoBDNS": "900003", "organo": {"nivel1": "AUTONOMICA", "nivel2": "ILLES BALEARS", "nivel3": "CONSELL DEMO"},
               "descripcion": "Bonos de compra para el comercio de proximidad «Bonos Demo» 2026", "fechaRecepcion": "2026-10-06",
               "abierto": False, "fechaInicioSolicitud": None, "fechaFinSolicitud": None, "textFin": "15 días hábiles desde la publicación en el BOIB",
               "presupuestoTotal": 800000, "tiposBeneficiarios": BDNS_PYME, "regiones": [{"descripcion": "ES53 - ILLES BALEARS"}],
               "urlBasesReguladoras": "https://demo.example/boib/2026/bonos"},
    "900004": {"codigoBDNS": "900004", "organo": {"nivel1": "ESTATAL", "nivel2": "ESTADO", "nivel3": "MINISTERIO DEMO"},
               "descripcion": "Programa de ayudas a la contratación indefinida en pymes 2026", "fechaRecepcion": "2026-07-01",
               "abierto": False, "fechaInicioSolicitud": "01/08/2026", "fechaFinSolicitud": "30/09/2026", "presupuestoTotal": 1000000,
               "tiposBeneficiarios": BDNS_PYME, "regiones": [{"descripcion": "ES - ESPAÑA"}], "urlBasesReguladoras": "https://demo.example/boe/2026/contratacion"},
}
BDNS_ARBOL = [{"id": 1, "descripcion": "ES - ESPAÑA", "children": [{"id": 48, "descripcion": "ES5 - ESTE", "children": [
    {"id": 58, "descripcion": "ES53 - ILLES BALEARS", "children": [{"id": 60, "descripcion": "ES532 - Mallorca", "children": []}]}]}]}]


def _bdns(ruta: str, **p):
    """La API de la BDNS sin red: el árbol de regiones, el buscador por texto y el detalle."""
    from gestoria import ayudas

    if ruta == "regiones":
        return BDNS_ARBOL
    if ruta == "convocatorias/busqueda":
        texto = ayudas._norm(p.get("descripcion", ""))
        filas = [{"numeroConvocatoria": n, "descripcion": d["descripcion"], "fechaRecepcion": d["fechaRecepcion"], **d["organo"]}
                 for n, d in BDNS.items() if texto in ayudas._norm(d["descripcion"])]
        return {"content": filas, "totalElements": len(filas)}
    return BDNS[p["numConv"]]


def _quien(pfx) -> str:
    return "personal" if "ana-demo" in str(pfx) else "sl"


class SinNavegador:
    """En lugar del navegador con certificado: no abre nada, solo sabe de quién es el certificado."""

    def __init__(self, pfx, clave=None, capturas=None, sitios=()):
        self.quien = _quien(pfx)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _aeat(nav, que, nif="", modelos=(), es_sociedad=True, **_) -> dict:
    """Lo que devolvería aeat.consultar con cada parte pedida (y solo esas), a la hora del reloj."""
    ahora, sl = RELOJ["ahora"], nav.quien == "sl"
    accesos = [{"fecha": f"{ahora - timedelta(days=i):%Y-%m-%d %H:%M}:0{i}", "modo": "Certificado electrónico", "canal": "Internet"}
               for i in range(3)]
    censo = {"nif": "B00000000", "nombre": "BICIS DEMO SL", "administracion": "Villademo",
             "forma_juridica": "Sociedad de responsabilidad limitada", "constitucion": "16/06/2026",
             "neo_obligado": True, "neo_desde": "01/07/2026", "neo_voluntario": False,
             "domicilio_fiscal": "CL DEMO 1, 00000 VILLADEMO (DEMO)", "referencia_catastral": ""} if sl else \
            {"nif": "00000000T", "nombre": "DEMO PEREZ ANA", "administracion": "Villademo", "forma_juridica": "",
             "constitucion": "", "neo_obligado": False, "neo_desde": None, "neo_voluntario": False,
             "domicilio_fiscal": "", "referencia_catastral": ""}
    partes = {
        "notificaciones": {"no_leidas": 0, "resumen": [], "notificaciones": []},
        "censo": {"censo": censo, "situacion": {"regimenes_iva": ["general", "REBU (operación por operación)"] if sl else [],
                                                "otras": [], "casillas": {}},
                  "actividades": [], "avisos": {"correo": "a***@example.com", "movil": "*** *** 000", "app": False,
                                                "estado": "Alta"} if sl else {},
                  "representantes": [{"nif": "00000000T", "nombre": "DEMO PEREZ ANA", "situacion": "Alta",
                                      "tipo": "ADMINISTRADOR UNICO"}] if sl else [],
                  **({"socios": [{"nif": "00000000T", "nombre": "DEMO PEREZ ANA", "estado": "Alta", "participacion": "100",
                                  "tipo": "Socio"}]} if sl and es_sociedad else {})},
        "obligaciones": {"estado_censal": "ACTIVO", "obligaciones": OBLIGACIONES if sl else []},
        "poderes": {"poderes_otorgados": [{"referencia": "2026000123", "nif": NIF_GESTORIA, "nombre": GESTORIA, "tramite": "GENERALNOT",
                                           "descripcion": "PODER GENERAL PARA RECEPCIÓN DE NOTIFICACIONES", "estado": "Confirmado",
                                           "baja": "30-06-2031", "vigente": True}] if sl else [],
                    "poderes_recibidos": []},
        "deudas": {"deudas": {"estado": "sin_deudas", "deudas": [], "texto": "no existen deudas"}},
        "expedientes": {"expedientes": []},
        "alertas": {"alertas": []},
        "accesos": {"accesos": accesos},
        "presentados": {"presentados": {m: _presentados(m) for m in modelos}},
        "roi": {"roi": {"en_roi": False, "csv": "DEMOCSV0000000001", "fecha": f"{ahora:%d-%m-%Y} 08:01:12"}} if nif else {},
        "datos_fiscales": {"datos_fiscales": []},
        "domiciliaciones": {"domiciliaciones": []},
    }
    d = {"errores": {}, "consultado": ahora.isoformat(timespec="seconds")}
    for p in que:
        d.update(partes[p])
    if "censo" in que:  # como la de verdad: con el censo vienen también las obligaciones
        d.update(partes["obligaciones"])
    return d


def _presentados(modelo: str) -> list[dict]:
    if modelo == "036":
        return [{"expediente": "2026036000000011", "periodo": "0A", "estado": "ALTA", "presentada": "01/07/2026 10:12:31",
                 "ejercicio": "2026"}]
    if modelo == "303" and RELOJ["ahora"] > PRESENTADO:
        return [{"expediente": EXPEDIENTE, "periodo": "3T", "estado": "ALTA", "presentada": f"{PRESENTADO:%d/%m/%Y %H:%M:%S}",
                 "ejercicio": "2026"}]
    return []


def _dehu(pfx, clave=None) -> dict:
    from gestoria import dehu

    ahora, items = RELOJ["ahora"], []
    if _quien(pfx) == "sl":
        for organismo, ident, concepto, puesta, caduca, abierta in DEHU:
            if datetime.fromisoformat(puesta) <= ahora and (abierta is None or ahora.date() < abierta):
                items.append({"emitterEntity": organismo, "identifier": ident, "concept": concepto, "availabilityDate": puesta + ":00",
                              "expirationDate": caduca + ":59", "state": "Pendiente", "postalDelivery": False, "bondType": "Titular"})
    return {"titular": "BICIS DEMO SL" if _quien(pfx) == "sl" else "ANA DEMO PEREZ", "consultado": ahora.isoformat(timespec="seconds"),
            "pendientes": dehu.elementos({"items": items}), "realizadas": [], "comunicaciones": [],
            "leidas": ["comunicaciones", "pendientes", "realizadas"]}


def _seguridad_social(nav) -> dict:
    return {"de_alta": True, "altas": [{"regimen": "Trabajador Autónomo", "empresa": "", "desde": "2026-07-01"},
                                       {"regimen": "Régimen General", "empresa": "TALLERES DEMO SL", "desde": "2023-02-01"}],
            "nuss": "********0000", "dias_cotizados": "1.358", "tiempo_cotizado": "3 años, 8 meses y 20 días",
            "base_cotizacion": "1.000,00 €", "cuota_autonomo": "300,00 €", "regularizacion": "", "cargo": "2026-10-30",
            "documentos": [], "consultado": RELOJ["ahora"].isoformat(timespec="seconds")}


def _comprobar_nif(pares, contexto_tls) -> list[dict]:
    """El servicio de comprobación de NIF: el proveedor de transportes no está en el censo."""
    malo = "B00000026"
    return [{"nif": n, "nombre": m, "nombre_censo": "" if n == malo else m.upper(),
             "resultado": "NO IDENTIFICADO" if n == malo else "IDENTIFICADO"} for n, m in pares]


def _descargar_presentado(nav, modelo, ejercicio, periodo, destino) -> dict:
    """La copia del 303 que presentó la gestoría: el de los libros con una factura recibida de más."""
    from gestoria import libros, perfil
    from gestoria.modelos import m303

    if (modelo, ejercicio, periodo) != ("303", 2026, "3T") or RELOJ["ahora"] <= PRESENTADO:
        return {"encontrado": False}
    carpeta = Path(destino).parent.parent
    ventas, compras = libros.cargar(carpeta)
    cas, _ = m303.casillas(ventas, compras, date(2026, 7, 1), date(2026, 10, 1), D("0"))
    for k, v in DE_MAS.items():
        cas[k] += v
    cas["45"] += DE_MAS["29"]
    for k in ("46", "64", "66", "69", "71"):
        cas[k] -= DE_MAS["29"]
    Path(destino).mkdir(parents=True, exist_ok=True)
    f = Path(destino) / f"303_{EXPEDIENTE}.txt"
    f.write_text(m303.generar_fichero(perfil.cargar(carpeta), 2026, "3T", cas), encoding="latin-1")
    return {"encontrado": True, **_presentados("303")[0], "fichero": str(f),
            "justificante": str(Path(destino) / f"303_{EXPEDIENTE}_justificante.pdf")}


def _simulador(modelo, ejercicio, fichero, capturas) -> dict:
    """El simulador del 303 de la AEAT: sin errores, y recalcula lo mismo que el fichero."""
    from gestoria import cotejo

    cas = cotejo.leer_presentado(Path(fichero))
    return {"errores": [], "avisos": [], "texto": "", "capturas": [], "importado": True, "sin_errores": True,
            "casillas_aeat": {k: cas[k] for k in ("27", "45", "71") if k in cas}}


def _fecha(dia: date):
    class Hoy(date):
        @classmethod
        def today(cls):
            return dia
    return Hoy


@contextlib.contextmanager
def a_las(ahora: datetime):
    """Corre lo de dentro como si fuera `ahora`, con las sedes inventadas en lugar de las de verdad."""
    from gestoria import (aeat, ayudas, certificado, chequeo, flujos, navegador, ordenes, ordenes_sede, panel, presentar, sede,
                          seguridad_social, terceros)

    RELOJ["ahora"] = ahora
    with contextlib.ExitStack() as pila:
        for modulo in (ordenes, ordenes_sede, flujos, chequeo, panel, presentar):
            pila.enter_context(mock.patch.object(modulo, "date", _fecha(ahora.date())))
        for modulo, nombre, otro in (
                (navegador, "Navegador", SinNavegador), (aeat, "consultar", _aeat), (ayudas, "_get", _bdns),
                (aeat, "descargar_presentado", _descargar_presentado), (aeat, "leer_justificante", lambda pdf: dict(JUSTIFICANTE)),
                (chequeo, "dehu_aparte", _dehu), (chequeo, "_cert_info", lambda pf, cual: dict(CERTIFICADOS[cual])),
                (certificado, "contexto_tls", lambda pfx, clave: None), (terceros, "comprobar", _comprobar_nif),
                (seguridad_social, "consultar", _seguridad_social), (sede, "validar", _simulador),
                (ordenes_sede, "_nav", lambda c, pf, cual: SinNavegador(pf.ruta_certificado(cual)))):
            pila.enter_context(mock.patch.object(modulo, nombre, otro))
        yield


def orden(carpeta: Path, *argv: str) -> tuple[str, int]:
    """`gestoria <argv>` con la carpeta de ejemplo: lo que imprime y su código de salida."""
    from gestoria.__main__ import main

    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        rc = main(["--carpeta", str(carpeta), *argv])
    return salida.getvalue().replace(str(carpeta), VISIBLE).rstrip("\n"), rc


def simular(tmp: Path, red: bool = True) -> dict[str, tuple]:
    """El octubre de la empresa de ejemplo. Devuelve lo que se dibuja. Sin `red`, el calendario de
    la AEAT es el de los tests (así lo corre tests/test_capturas.py)."""
    from gestoria import calendario

    feed = calendario._feed

    def calendario_aeat(nombre, *a, **k) -> str:  # el público de la AEAT o, sin red, el de los tests
        try:
            if red:
                return feed(nombre)
        except Exception:
            pass
        return (RAIZ / "tests" / "datos" / "aeat_iva.ics").read_text(encoding="utf-8") if nombre == "iva" else ""

    c = tmp / "bicis-demo"
    shutil.copytree(RAIZ / "ejemplos" / "sl-demo", c, ignore=shutil.ignore_patterns("salida"))
    perfil_toml = (c / "perfil.toml").read_text(encoding="utf-8").replace('forma_pago = "I"', 'forma_pago = "U"')
    (c / "perfil.toml").write_text(perfil_toml + f'\n[pago]\niban = "{IBAN}"\n'
                                   f'\n[sede]\ncertificado = "{CERTIFICADOS["principal"]["ruta"]}"\n\n'
                                   f'[sede.personal]\ncertificado = "{CERTIFICADOS["personal"]["ruta"]}"\n', encoding="utf-8")
    out = {}
    # los certificados no existen: la «clave» solo hace falta para que el perfil no la eche en falta
    entorno = {"GESTORIA_DEPURAR": "1", "GESTORIA_CERT_CLAVE": "demo", "GESTORIA_CERT_CLAVE_PERSONAL": "demo"}
    with mock.patch.object(calendario, "_feed", calendario_aeat), mock.patch.dict(os.environ, entorno):
        with a_las(datetime(2026, 10, 1, 8, 0)):
            orden(c, "chequeo")
        with a_las(datetime(2026, 10, 13, 7, 30)):
            orden(c, "vigia")
        with a_las(datetime(2026, 10, 14, 7, 30)):
            out["vigia"] = ("gestoria vigia",) + orden(c, "vigia")
        foto = c / "salida" / "sede.json"   # la hora de la foto, la del vigía (no la de quien genera las capturas)
        foto.write_text(re.sub(r'"actualizado": "[^"]+"', '"actualizado": "2026-10-14T07:30:12"', foto.read_text(encoding="utf-8")),
                        encoding="utf-8")
        with a_las(datetime(2026, 10, 14, 9, 0)):
            out["hoy"] = ("gestoria hoy",) + orden(c, "hoy")
        with a_las(datetime(2026, 10, 14, 9, 30)):
            out["presentar"] = ("gestoria presentar 303 --ejercicio 2026 --periodo 3T",) + orden(
                c, "presentar", "303", "--ejercicio", "2026", "--periodo", "3T", *([] if red else ["--sin-investigar"]))
        with a_las(datetime(2026, 10, 14, 9, 40)):
            out["banco"] = ("gestoria banco",) + orden(c, "banco")
        with a_las(datetime(2026, 10, 14, 9, 50)):
            from gestoria import web
            out["web"] = web.html(web.datos(c, RELOJ["ahora"].date()))
        with a_las(datetime(2026, 10, 14, 9, 55)):
            out["deducciones"] = ("gestoria deducciones",) + orden(c, "deducciones")
        with a_las(datetime(2026, 10, 14, 10, 0)):
            out["ayudas"] = ("gestoria ayudas",) + orden(c, "ayudas")
        with a_las(datetime(2026, 10, 21, 8, 0)):
            orden(c, "chequeo")
            informe = c / "salida" / "chequeo_2026-10-21.md"
            out["chequeo"] = (f"{VISIBLE}/salida/{informe.name}", informe.read_text(encoding="utf-8"))
        with a_las(datetime(2026, 10, 21, 8, 10)):
            out["cotejar"] = ("gestoria cotejar 303 --ejercicio 2026 --periodo 3T",) + orden(
                c, "cotejar", "303", "--ejercicio", "2026", "--periodo", "3T")
    return out


# ─── dibujo ─────────────────────────────────────────────────────────────────────────────────

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&'
           'family=JetBrains+Mono:wght@400;700&display=block" rel="stylesheet">')
MONO = '"JetBrains Mono", "Noto Color Emoji", "DejaVu Sans Mono", monospace'
SANS = 'Inter, "Noto Color Emoji", "Segoe UI", system-ui, sans-serif'

BASE = """
* { box-sizing: border-box }
html, body { margin: 0; background: transparent }
.marco { display: inline-block; padding: 26px 34px 44px }
.ventana { border-radius: 12px; overflow: hidden; border: 1px solid rgba(240,246,252,.12);
  box-shadow: 0 26px 50px -14px rgba(1,4,9,.55), 0 10px 18px -10px rgba(1,4,9,.45) }
.barra { height: 40px; display: flex; align-items: center; padding: 0 16px; position: relative }
.barra i { width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; display: inline-block }
.barra i:nth-child(1) { background: #ff5f57 } .barra i:nth-child(2) { background: #febc2e } .barra i:nth-child(3) { background: #28c840 }
.barra b { position: absolute; left: 90px; right: 90px; text-align: center; font: 500 13px SANS; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis }
"""

TERMINAL = BASE + """
.ventana { background: #0d1117 }
.barra { background: #161b22; border-bottom: 1px solid rgba(240,246,252,.08) }
.barra b { color: #8b949e }
pre { margin: 0; padding: 18px 24px 24px; width: calc(var(--cols) * 1ch + 48px); font: 14px/1.62 MONO; color: #d1d7e0;
  white-space: pre-wrap; overflow-wrap: anywhere; font-variant-ligatures: none }
.p { color: #3fb950; font-weight: 700 } .c { color: #f0f6fc; font-weight: 700 }
"""

DOCUMENTO = BASE + """
.ventana { background: #ffffff; border-color: rgba(31,35,40,.18) }
.barra { background: #f6f8fa; border-bottom: 1px solid #d1d9e0 }
.barra b { color: #59636e }
article { width: 900px; max-height: var(--alto); overflow: hidden; position: relative; padding: 26px 38px 30px;
  font: 15px/1.62 SANS; color: #1f2328 }
article::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 150px;
  background: linear-gradient(rgba(255,255,255,0), #fff 85%) }
h1 { font-size: 23px; line-height: 1.3; font-weight: 700; margin: 0 0 14px; padding-bottom: 12px; border-bottom: 1px solid #d1d9e0 }
h2 { font-size: 18px; font-weight: 650; margin: 24px 0 8px; padding-bottom: 6px; border-bottom: 1px solid #d1d9e0 }
p { margin: 0 0 10px } ul { margin: 0; padding-left: 24px } li { margin: 5px 0 }
code { font: 13px MONO; background: rgba(129,139,152,.14); padding: 2px 6px; border-radius: 6px }
em { color: #59636e } strong { font-weight: 650 } hr { border: 0; border-top: 1px solid #d1d9e0; margin: 20px 0 }
"""

NAVEGADOR = BASE + """
.ventana { background: #f5f6fa; border-color: rgba(31,35,40,.18) }
.barra { background: #e9ecf2; border-bottom: 1px solid #d5dae3; height: 46px }
.url { position: absolute; left: 50%; transform: translateX(-50%); width: 520px; height: 28px; border-radius: 8px;
  background: #fff; border: 1px solid #d5dae3; font: 500 13px SANS; color: #475467; display: flex; align-items: center;
  justify-content: center; gap: 6px }
iframe { display: block; width: 1360px; height: 860px; border: 0; background: #f5f6fa }
"""

LOGO = """<svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38bdf8"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs>
<rect width="64" height="64" rx="17" fill="url(#g)"/>
<path d="M23 15h13l9 9v23a3 3 0 0 1-3 3H23a3 3 0 0 1-3-3V18a3 3 0 0 1 3-3z" fill="rgba(255,255,255,.16)" stroke="#fff" stroke-width="3" stroke-linejoin="round"/>
<path d="M36 15v9h9" fill="none" stroke="#fff" stroke-width="3" stroke-linejoin="round"/>
<path d="M26 35.5l5 5 9.5-10.5" fill="none" stroke="#fff" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

PORTADA = """
* { box-sizing: border-box }
html, body { margin: 0; background: transparent }
.marco { display: inline-block; padding: 0 }
.tarjeta { width: 1280px; height: 430px; border-radius: 24px; overflow: hidden; position: relative; display: flex;
  align-items: center; gap: 48px; padding: 0 64px; font-family: SANS; color: #e6edf3;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.09);
  background: radial-gradient(640px 360px at 8% -10%, rgba(56,189,248,.28), transparent 62%),
              radial-gradient(560px 380px at 104% 112%, rgba(139,92,246,.32), transparent 60%),
              radial-gradient(420px 260px at 62% 50%, rgba(251,191,36,.07), transparent 70%),
              linear-gradient(135deg, #0a1020 0%, #0f1830 55%, #0c1226 100%) }
.social .tarjeta { height: 640px; border-radius: 0; padding: 0 70px; gap: 40px }
.social .izq, .social .der { zoom: 1.2 }
.rejilla { position: absolute; inset: 0; pointer-events: none;
  background-image: linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
  background-size: 34px 34px; -webkit-mask-image: radial-gradient(900px 420px at 30% 40%, #000 20%, transparent 75%) }
.izq { position: relative; flex: 1 }
.marca { display: flex; align-items: center; gap: 18px; font-size: 64px; font-weight: 800; letter-spacing: -0.035em; line-height: 1 }
.ia { background: linear-gradient(95deg, #fbbf24, #fb7185 70%); -webkit-background-clip: text; background-clip: text; color: transparent }
h1 { margin: 26px 0 12px; font-size: 33px; line-height: 1.15; font-weight: 700; letter-spacing: -0.02em; color: #f8fafc; text-wrap: balance }
p { margin: 0; max-width: 690px; font-size: 17.5px; line-height: 1.55; color: #9fb0c8; text-wrap: pretty }
.chips { display: flex; gap: 10px; margin-top: 24px; flex-wrap: wrap }
.chips span { font-size: 13.5px; font-weight: 600; color: #cbd5e1; padding: 7px 13px; border-radius: 999px;
  border: 1px solid rgba(148,163,184,.28); background: rgba(15,23,42,.55) }
.der { position: relative; width: 410px; display: flex; flex-direction: column; gap: 12px }
.aviso { display: flex; align-items: center; gap: 14px; padding: 14px 18px 14px 16px; border-radius: 14px;
  background: rgba(255,255,255,.055); border: 1px solid rgba(255,255,255,.10); box-shadow: 0 12px 30px -12px rgba(0,0,0,.6) }
.aviso .e { font-size: 22px; line-height: 1 }
.aviso b { display: block; font-size: 15px; font-weight: 650; color: #f1f5f9 }
.aviso small { display: block; margin-top: 2px; font-size: 13px; color: #94a3b8 }
.aviso:nth-child(2) { margin-left: 22px } .aviso:nth-child(3) { margin-left: 44px } .aviso:nth-child(4) { margin-left: 22px }
"""

PORTADA_HTML = """<div class="tarjeta"><div class="rejilla"></div>
<div class="izq">
  <div class="marca">LOGO<span>Gestor<span class="ia">IA</span></span></div>
  <h1>Un gestor con un solo cliente: tú.</h1>
  <p>Tu agente de IA repasa cada factura, te dice qué deducir, te busca ayudas, lleva tus cuentas y
  presenta tus impuestos cuando le dices que sí. Con tu certificado, vigila tu buzón de Hacienda y
  de la DEHú.</p>
  <div class="chips"><span>SL y autónomos en España</span><span>cada cifra, con su artículo</span><span>nada se presenta sin tu sí</span></div>
</div>
<div class="der">
  <div class="aviso"><span class="e">🔴</span><div><b>DEHú · Ayuntamiento Demo</b><small>notificación sin abrir: caduca el 23-oct</small></div></div>
  <div class="aviso"><span class="e">⚠️</span><div><b>Deducciones · 1 por mirar</b><small>el alquiler del local no está en tus compras</small></div></div>
  <div class="aviso"><span class="e">🟢</span><div><b>Ayudas · 2 abiertas para ti</b><small>digitalización del comercio: hasta el 15-nov</small></div></div>
  <div class="aviso"><span class="e">✅</span><div><b>303 del 3T · revisado y ensayado</b><small>se presenta cuando tú digas que sí</small></div></div>
</div></div>"""


def _pagina(css: str, cuerpo: str, clase: str = "") -> str:
    css = css.replace("MONO", MONO).replace("SANS", SANS)
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8">{FUENTES}<style>{css}</style></head>'
            f'<body class="{clase}"><div class="marco">{cuerpo}</div></body></html>')


def _barra(titulo: str) -> str:
    return f'<div class="barra"><i></i><i></i><i></i><b>{html.escape(titulo)}</b></div>'


def terminal(titulo: str, pasos: list[tuple[str, str]], columnas: int = 104) -> str:
    """Una ventana de terminal: cada paso es (orden, lo que imprimió)."""
    trozos = []
    for comando, salida in pasos:
        trozos.append(f'<span class="p">$</span> <span class="c">{html.escape(comando)}</span>')
        if salida:
            trozos.append(html.escape(salida))
    cuerpo = f'<div class="ventana">{_barra(titulo)}<pre style="--cols:{columnas}">' + "\n".join(trozos) + "</pre></div>"
    return _pagina(TERMINAL, cuerpo)


def _en_linea(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(?<!\w)_\((.+?)\)_(?!\w)", r"<em>(\1)</em>", s)


def markdown_a_html(md: str) -> str:
    """Lo justo para los informes de GestorIA: títulos, listas, negrita, cursiva, código y la raya."""
    out, en_lista = [], False
    for linea in md.splitlines():
        if linea.startswith("- "):
            if not en_lista:
                out.append("<ul>")
                en_lista = True
            out.append(f"<li>{_en_linea(linea[2:])}</li>")
            continue
        if en_lista:
            out.append("</ul>")
            en_lista = False
        if linea.startswith("## "):
            out.append(f"<h2>{_en_linea(linea[3:])}</h2>")
        elif linea.startswith("# "):
            out.append(f"<h1>{_en_linea(linea[2:])}</h1>")
        elif linea.strip() == "---":
            out.append("<hr>")
        elif linea.strip():
            out.append(f"<p>{_en_linea(linea)}</p>")
    return "\n".join(out + (["</ul>"] if en_lista else []))


def documento(titulo: str, md: str, alto: int = 1180) -> str:
    cuerpo = f'<div class="ventana">{_barra(titulo)}<article style="--alto:{alto}px">{markdown_a_html(md)}</article></div>'
    return _pagina(DOCUMENTO, cuerpo)


def navegador(app: str, vista: str = "resumen") -> str:
    """El panel web (`gestoria web`) en una ventana de navegador, abierto en `vista`."""
    app = app.replace('|| "resumen")', f'|| "{vista}")')
    cuerpo = (f'<div class="ventana"><div class="barra"><i></i><i></i><i></i><span class="url">🔒 127.0.0.1:8640/#{vista}</span></div>'
              f'<iframe srcdoc="{html.escape(app, quote=True)}"></iframe></div>')
    return _pagina(NAVEGADOR, cuerpo)


def portada(clase: str = "") -> str:
    return _pagina(PORTADA, PORTADA_HTML.replace("LOGO", LOGO), clase)


def dibujar(paginas: dict[str, tuple[str, str]], con_html: bool = False) -> None:
    """Cada página a docs/img/: WebP sin pérdida (con pérdida mínima la portada, por sus degradados)
    y la vista previa social en PNG, el formato que pide GitHub."""
    from PIL import Image
    from playwright.sync_api import sync_playwright

    IMG.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        b = p.chromium.launch()
        for nombre, (h, formato) in paginas.items():
            pg = b.new_page(device_scale_factor=1 if formato == "png" else 2, viewport={"width": 1500, "height": 1000})
            pg.set_content(h, wait_until="networkidle")
            pg.evaluate("document.fonts.ready.then(() => true)")
            pg.wait_for_timeout(600)          # el iframe del panel web pinta después
            png = Path(tmp) / f"{nombre}.png"
            pg.locator(".marco").screenshot(path=str(png), omit_background=formato != "png")
            pg.close()
            destino = IMG / f"{nombre}.{formato}"
            im = Image.open(png)
            destino = IMG / f"{nombre}.{formato.rstrip('9')}" if formato == "webp9" else destino
            if formato == "png":
                im.convert("RGB").save(destino, optimize=True)
            elif formato == "webp9":         # degradados y pantallas grandes: con pérdida mínima
                im.save(destino, "WEBP", quality=90, method=6)
            else:
                im.save(destino, "WEBP", lossless=True, quality=100, method=6)
            if con_html:
                (IMG / f"{nombre}.html").write_text(h, encoding="utf-8")
            print(f"  docs/img/{destino.name} ({destino.stat().st_size // 1024} KB)")
        b.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--html", action="store_true", help="deja también el HTML de cada captura en docs/img/")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="gestoria-capturas-") as tmp:
        s = simular(Path(tmp).resolve())
    paginas = {
        "portada": (portada(), "webp9"),
        "social": (portada("social"), "png"),
        "hoy": (terminal("gestoria hoy", [s["hoy"][:2]], columnas=110), "webp"),
        "vigia": (terminal("cron · 07:30 · gestoria vigia", [s["vigia"][:2], ("echo $?", str(s["vigia"][2]))]), "webp"),
        "chequeo": (documento(*s["chequeo"]), "webp"),
        "cotejar": (terminal("gestoria cotejar 303", [s["cotejar"][:2], ("echo $?", str(s["cotejar"][2]))]), "webp"),
        "presentar": (terminal("gestoria presentar 303", [s["presentar"][:2]], columnas=112), "webp"),
        "banco": (terminal("gestoria banco", [s["banco"][:2]], columnas=108), "webp"),
        "web": (navegador(s["web"], "resumen"), "webp9"),
        "web_diario": (navegador(s["web"], "diario"), "webp9"),
        "deducciones": (terminal("gestoria deducciones", [s["deducciones"][:2]], columnas=118), "webp"),
        "ayudas": (terminal("gestoria ayudas", [s["ayudas"][:2]], columnas=118), "webp"),
    }
    print("Capturas (datos inventados):")
    dibujar(paginas, a.html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
