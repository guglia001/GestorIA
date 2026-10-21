"""La sede de la AEAT con tu certificado, en SOLO LECTURA: todo lo que Hacienda sabe de ti.

Cada consulta es una pantalla de la sede (dirección comprobada el 21-oct-2026) y un lector
del texto que muestra. Los lectores son funciones puras: los tests les pasan textos inventados
con la misma forma que los reales. Lo único que se pulsa es el botón de consulta de cada
pantalla («Buscar», «Consultar», «Aceptar», «Enviar» en los formularios de búsqueda).

| consulta | pantalla de la sede |
|---|---|
| notificaciones | resumen de no leídas y listado (sin abrir ninguna) |
| censo | «Mis datos censales»: identificación, domicilio fiscal, notificaciones electrónicas obligatorias |
| obligaciones | «Mis obligaciones»: lo que tienes dado de alta y desde cuándo |
| situacion | «Mi situación tributaria»: regímenes de IVA (general, REBU, recargo, caja…), IS, IRPF, retenciones |
| actividades | epígrafes del IAE de alta |
| representantes · socios | quién te representa · socios y participaciones (SL) |
| avisos | a qué correo y móvil te avisa Hacienda |
| poderes | apoderamientos otorgados y recibidos (quién puede actuar por ti) |
| deudas | deudas pendientes con la AEAT |
| expedientes | «Mis expedientes»: procedimientos abiertos |
| alertas · accesos | «Mis alertas» · «Mis últimos accesos» a la sede |
| presentados | lo presentado de cada modelo; justificante (PDF) y fichero presentado |
| roi | si un NIF consta en el registro de operadores intracomunitarios (certificado con CSV) |
| datos_fiscales | lo que tus pagadores y bancos han declarado de ti (renta o sociedades) |
| domiciliaciones | cargos domiciliados de cada modelo |
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

W1 = "https://www1.agenciatributaria.gob.es/wlpl"
W2 = "https://www2.agenciatributaria.gob.es/wlpl"
URL = {
    "resumen": W1 + "/GNNO-JDIT/ResumenInteresados",
    "notificaciones": W1 + "/GNNO-JDIT/SvInteresadosQuery?VEZ=BUSCAR1",
    "censo": W1 + "/BUGC-JDIT/MdcAcceso",
    "obligaciones": W1 + "/BUGC-JDIT/ConsultaObligaciones",
    "representantes": W1 + "/BUGC-JDIT/ConsultaRepresentantes",
    "avisos": W1 + "/TOAG-JDIT/Identificacion?COD_SERVICIO=CSAPL",
    "poderes_otorgados": W1 + "/ITTI-APOD/SvApodPoderQuery",
    "poderes_recibidos": W1 + "/ITTI-APOD/SvApodApodeQuery",
    "deudas": W1 + "/SRVO-JDIT/ConsultaDdas?faccion=CONS_DDAS",
    "expedientes": W1 + "/TEWV-CORE/ResumenVlt",
    "alertas": W1 + "/IIIC-ALER/SvObtAlertas",
    "accesos": W1 + "/ADHT-AUTH/UltimasConexionesW",
    "presentados": W1 + "/SCEJ-MANT/CONSUL/index.zul?MODELO={modelo}&EJERCICIO=0",
    "roi": W2 + "/GROI-JDIT/ConsultaOperadorSedeGroiServlet",
    "datos_fiscales_renta": W1 + "/DFPA-D182/SvVisDF{aa}Net",
    "datos_fiscales_sociedades": W1 + "/IIIC-DFIS/VisuSocDF{aa}Net",
    "domiciliaciones": W1 + "/ECDM-MANT/DomQueryN",
}
MODELOS_PRESENTADOS = ("303", "390", "200", "202", "130", "111", "115", "180", "190", "347", "349", "036", "037", "100")


# ─── lectores genéricos ─────────────────────────────────────────────────────────────────────

def _limpio(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def tabla(texto: str, columnas: tuple[str, ...]) -> list[dict]:
    """Las filas de la tabla cuya cabecera (celdas separadas por tabuladores) contiene esas
    columnas. Así sacan las tablas de la sede `inner_text`: una línea por fila."""
    lineas = (texto or "").splitlines()
    for i, linea in enumerate(lineas):
        if "\t" in linea and all(c in linea for c in columnas):
            cab = [_limpio(c) for c in linea.split("\t")]
            filas: list[dict] = []
            for l in lineas[i + 1:]:
                if "\t" not in l:
                    if filas and l.strip():
                        break
                    continue
                celdas = [_limpio(c) for c in l.split("\t")]
                if not any(celdas):
                    continue
                celdas += [""] * (len(cab) - len(celdas))
                filas.append({cab[k] or f"col{k}": celdas[k] for k in range(len(cab))})
            return filas
    return []


def clave_valor(texto: str, claves: tuple[str, ...]) -> dict[str, str]:
    """«Clave<TAB>valor» o «Clave: valor» en una línea."""
    out = {}
    for linea in (texto or "").splitlines():
        for k in claves:
            if linea.strip().startswith(k):
                resto = linea.strip()[len(k):]
                if resto[:1] in ("\t", ":"):
                    out[k] = _limpio(resto.lstrip("\t:"))
    return out


def ocultar_correo(c: str) -> str:
    u, _, d = (c or "").partition("@")
    return f"{u[:1]}***@{d}" if d else c


def ocultar_telefono(t: str) -> str:
    t = re.sub(r"\D", "", t or "")
    return f"*** *** {t[-3:]}" if len(t) >= 6 else t


def _fecha(s: str) -> date | None:
    for f in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime((s or "").strip()[:10], f).date()
        except ValueError:
            continue
    return None


# ─── notificaciones ─────────────────────────────────────────────────────────────────────────

def notificaciones_de(texto_listado: str) -> list[dict]:
    """Filas de «Consulta de notificaciones y comunicaciones» (celdas separadas por tabuladores)."""
    out = []
    for linea in (texto_listado or "").splitlines():
        c = [x.strip() for x in linea.split("\t")]
        if len(c) >= 9 and re.fullmatch(r"\d{10,16}", c[0]):
            out.append({"numero": c[0], "concepto": c[1], "tipo": c[2], "titular": c[3],
                        "destinatario": c[4], "emitida": c[5], "notificada": c[6],
                        "modo": c[7], "leida": c[8].lower().startswith("s")})
    return out


FRASES_SIN_NADA = ("No tiene notificaciones pendientes de notificar no leídas",
                   "No tiene notificaciones notificadas no leídas", "No tiene comunicaciones no leídas")


def no_leidas_de(texto_resumen: str) -> int | None:
    """0 si el resumen dice las tres frases «No tiene … no leídas»; si no, cuántas secciones
    tienen algo sin leer; None si la página no es el resumen."""
    t = _limpio(texto_resumen)
    if all(f in t for f in FRASES_SIN_NADA):
        return 0
    if "Resumen de notificaciones" in t:
        return sum(1 for f in FRASES_SIN_NADA if f not in t)
    return None


def resumen_de(texto_resumen: str) -> list[dict]:
    """Lo que el resumen enseña sin leer: número, sección (notificación pendiente de notificar,
    notificada o comunicación), concepto si lo trae y fecha de emisión."""
    out, seccion = [], ""
    for linea in (texto_resumen or "").splitlines():
        l = linea.strip()
        if l.startswith("Notificaciones pendientes de notificar"):
            seccion = "pendiente"
        elif l.startswith("Notificaciones notificadas"):
            seccion = "notificada"
        elif l.startswith("Comunicaciones no leídas"):
            seccion = "comunicacion"
        c = [x.strip() for x in linea.split("\t")]
        if len(c) >= 3 and re.fullmatch(r"\d{10,16}", c[0]):
            emitida = c[-1]
            concepto = c[1] if seccion == "comunicacion" or not re.match(r"[A-Z]?\d{7,8}[A-Z]?\b", c[1]) else ""
            out.append({"numero": c[0], "seccion": seccion, "concepto": concepto, "emitida": emitida})
    return out


def plazo_notificacion(emitida: str | date, obligado: bool | None, hoy: date | None = None) -> dict:
    """Qué pasa si nadie la abre (Ley 39/2015, leída en el BOE el 21-oct-2026):
    - si la vía electrónica es obligatoria o la elegiste, se entiende rechazada a los 10 días
      naturales de la puesta a disposición (art. 43.2) y el trámite se da por efectuado (art. 41.5);
    - si no, te llega también en papel y cuenta la primera de las dos (arts. 41.7 y 42.1): abrirla
      en la sede te da por notificado ese mismo día."""
    hoy = hoy or date.today()
    d = emitida if isinstance(emitida, date) else _fecha(str(emitida))
    if obligado is False:
        return {"rechazo": None, "texto": "llega también en papel; abrirla aquí te da por notificado hoy "
                "(arts. 41.7 y 42.1 Ley 39/2015). No hay rechazo a los 10 días: no estás obligado a la vía electrónica"}
    if d is None:
        return {"rechazo": None, "texto": "sin fecha de puesta a disposición legible"}
    rechazo = d + timedelta(days=10)
    quedan = (rechazo - hoy).days
    cuando = (f"se entenderá rechazada y notificada el {rechazo.isoformat()} (en {quedan} días)" if quedan >= 0
              else f"ya se entendió rechazada el {rechazo.isoformat()}: el trámite siguió y los plazos corren")
    duda = "" if obligado else " (si estás obligado a la vía electrónica o la elegiste)"
    return {"rechazo": rechazo, "texto": cuando + duda + " (arts. 43.2 y 41.5 Ley 39/2015)"}


# ─── censo ──────────────────────────────────────────────────────────────────────────────────

CLAVES_CENSO = ("NIF", "Razón Social", "Apellidos y Nombre", "Administración de su domicilio fiscal",
                "Forma Jurídica", "Fecha de Constitución", "Obligado a notificaciones electrónicas",
                "Suscrito voluntariamente a notificaciones electrónicas")


def censo_de(texto: str) -> dict:
    """«Mis datos censales»: identificación, domicilio fiscal y notificaciones electrónicas."""
    i = (texto or "").find("Datos Identificativos del Contribuyente")
    cuerpo = texto[i:] if i >= 0 else (texto or "")
    datos = clave_valor(cuerpo.split("Domicilio Fiscal")[0], CLAVES_CENSO)
    neo = datos.get("Obligado a notificaciones electrónicas", "")
    domicilio, rc = "", ""
    j = cuerpo.find("Domicilio Fiscal")
    if j >= 0:
        bloque = re.split(r"Domicilio Social|\nAgencia Tributaria\n|\nAccesibilidad\n", cuerpo[j:])[0]
        campos: dict[str, str] = {}
        lineas = [l for l in bloque.splitlines()[1:] if l.strip() or "\t" in l]
        for cab, val in zip(lineas[::2], lineas[1::2]):
            for k, v in zip(cab.split("\t"), val.split("\t")):
                campos[_limpio(k)] = _limpio(v)
        rc = " · ".join(x for x in (campos.get("Referencia Catastral"), campos.get("Indicador de referencia catastral")) if x)
        domicilio = formatear_domicilio(campos)
    return {"nif": datos.get("NIF", ""), "nombre": datos.get("Razón Social") or datos.get("Apellidos y Nombre", ""),
            "administracion": datos.get("Administración de su domicilio fiscal", ""),
            "forma_juridica": datos.get("Forma Jurídica", ""), "constitucion": datos.get("Fecha de Constitución", ""),
            "neo_obligado": neo.upper().startswith("SI") if neo else None,
            "neo_desde": (re.search(r"\d{2}/\d{2}/\d{4}", neo) or [None])[0] if neo else None,
            "neo_voluntario": datos.get("Suscrito voluntariamente a notificaciones electrónicas", "").lower().startswith("s"),
            "domicilio_fiscal": domicilio, "referencia_catastral": rc}


def formatear_domicilio(c: dict[str, str]) -> str:
    """«CALLE MAYOR 1, portal 2, planta 3, puerta B, 28000 MADRID»."""
    via = " ".join(x for x in (c.get("Tipo Vía"), c.get("Nombre Vía"), c.get("Número de Casa")) if x)
    extra = ", ".join(f"{n.lower()} {c[n]}" for n in ("Bloque", "Portal", "Escalera", "Planta", "Puerta") if c.get(n))
    muni = re.sub(r"^\d{5}\s*-\s*", "", c.get("Municipio", ""))
    lugar = " ".join(x for x in (c.get("Código Postal"), c.get("Localidad/Población"), muni) if x)
    prov = f" ({c['Provincia']})" if c.get("Provincia") and c.get("Provincia") != muni else ""
    return ", ".join(x for x in (via, extra, lugar + prov) if x)


def obligaciones_de(texto: str) -> list[dict]:
    out = []
    for linea in (texto or "").splitlines():
        c = [x.strip() for x in linea.split("\t")]
        if len(c) >= 6 and re.match(r"\d{2}/\d{2}/\d{4}", c[2] or ""):
            out.append({"obligacion": c[0], "periodicidad": c[1], "alta": c[2],
                        "baja": c[3] or None, "estado": c[5]})
    return out


def situacion_estado_de(texto: str) -> str:
    m = re.search(r"Estado Sit\. Trib\.:?\s*(\w+)", texto or "")
    return m.group(1).upper() if m else ""


# Obligación de la sede → modelos que trae consigo (orden de los modelos y art. 71 RIVA)
_MODELOS_DE = (
    (r"VALOR A[ÑN]ADIDO.*MENSUAL", ("303", "390")), (r"VALOR A[ÑN]ADIDO", ("303", "390")),
    (r"SOCIEDADES|IS/", ("200",)), (r"IRPF.*PAGO FRACC.*OBJETIV|M[ÓO]DULOS", ("131",)),
    (r"IRPF.*PAGO FRACC", ("130",)), (r"ARRENDAMIENTO", ("115", "180")),
    (r"RETENC.*(TRABAJO|PROFESION|ACTIVIDADES)", ("111", "190")), (r"INTRACOMUNITARI", ("349",)),
)


def modelos_de_obligaciones(obligaciones: list[dict]) -> set[str]:
    out: set[str] = set()
    for o in obligaciones:
        if (o.get("estado") or "").upper() != "ALTA":
            continue
        for patron, modelos in _MODELOS_DE:
            if re.search(patron, o.get("obligacion", ""), re.I):
                out.update(modelos)
                break
    return out


# «Mi situación tributaria» es una ficha con las casillas del 036: cada valor va en un script
# («if ("A"=="A")…» = alta; una fecha en la casilla siguiente). Se lee del HTML.
_CASILLA_HTML = re.compile(r'>\s*(\d{3})\s*</li>\s*<li[^>]*>\s*<script>\s*if\s*\(\s*"([^"]*)"')
REGIMENES_IVA = {"510": "general", "514": "recargo de equivalencia", "518": "REBU (operación por operación)",
                 "522": "REBU (margen de beneficio global)", "526": "agencias de viajes"}
FECHAS_IVA = {"536": "agricultura, ganadería y pesca", "552": "simplificado", "525": "criterio de caja"}
OTRAS = {"641": "Impuesto sobre Sociedades", "602": "pagos fraccionados del IRPF (130)",
         "720": "retenciones del trabajo (111)", "721": "retenciones de profesionales (111)",
         "722": "retenciones de alquileres (115)", "503": "inicio de actividad"}


def situacion_de(html: str) -> dict:
    """{"regimenes_iva": [...], "otras": [...], "casillas": {...}} de «Mi situación tributaria»."""
    cas = {k: v.strip() for k, v in _CASILLA_HTML.findall(html or "")}
    reg = [n for k, n in REGIMENES_IVA.items() if cas.get(k) == "A"]
    reg += [n for k, n in FECHAS_IVA.items() if _fecha(cas.get(k, ""))]
    otras = [f"{n} desde {cas[k]}" for k, n in OTRAS.items() if _fecha(cas.get(k, ""))]
    return {"regimenes_iva": reg, "otras": otras, "casillas": cas}


def actividades_de(texto: str) -> list[dict]:
    return [{"seccion": f.get("Sección", ""), "epigrafe": f.get("Epígrafe", ""), "denominacion": f.get("Denominación", ""),
             "estado": f.get("Estado", ""), "inicio": f.get("F.Inicio", ""), "baja": f.get("F.Baja", "")}
            for f in tabla(texto, ("Epígrafe", "Denominación"))]


def representantes_de(texto: str) -> list[dict]:
    return [{"nif": f.get("NIF", ""), "nombre": f.get("Apellidos y Nombre", ""), "situacion": f.get("Situación", ""),
             "tipo": f.get("Tipo de Representación", "")}
            for f in tabla(texto, ("NIF", "Apellidos y Nombre", "Tipo de Representación")) if f.get("NIF")]


_NIF = re.compile(r"^(?:[A-HJ-NP-SUVW]\d{7}[0-9A-J]|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])$")


def socios_de(texto: str) -> list[dict]:
    """«Mis socios / partícipes»: la pantalla pone una celda por línea (NIF, nombre, estado, %…)."""
    l = [x.strip() for x in (texto or "").splitlines()]
    out = []
    for i, x in enumerate(l):
        if _NIF.match(x) and i + 4 < len(l):
            out.append({"nif": x, "nombre": l[i + 1], "estado": l[i + 2], "participacion": l[i + 3],
                        "tipo": l[i + 5] if i + 5 < len(l) else ""})
    return out


def avisos_de(texto: str) -> dict:
    """«Canales de contacto para recibir avisos» (ocultos: solo el principio del correo y el
    final del móvil)."""
    d = clave_valor(texto, ("Teléfono móvil", "Correo electrónico", "App Agencia Tributaria", "Estado"))
    return {"movil": ocultar_telefono(d.get("Teléfono móvil", "")), "correo": ocultar_correo(d.get("Correo electrónico", "")),
            "app": d.get("App Agencia Tributaria", "").lower().startswith("s"), "estado": d.get("Estado", "")}


# ─── poderes, deudas, expedientes, alertas, accesos ─────────────────────────────────────────

def poderes_de(texto: str) -> list[dict]:
    filas = tabla(texto, ("Núm. Referencia", "Trámite"))
    out = []
    for f in filas:
        otro = f.get("NIF / CIF Apoderado") or f.get("NIF / CIF Poderdante") or ""
        nif, _, nombre = otro.partition(" - ")
        out.append({"referencia": f.get("Núm. Referencia", ""), "nif": nif.strip(), "nombre": nombre.strip(),
                    "tramite": f.get("Trámite", ""), "descripcion": f.get("Descripción trámite", ""),
                    "estado": f.get("Estado Actual", ""), "baja": f.get("Fecha Baja", ""),
                    "vigente": f.get("Vigente", "").lower().startswith("s")})
    return out


def deudas_de(texto: str) -> dict:
    t = _limpio(texto)
    if "notificaciones pendientes" in t and "Antes de continuar" in t:
        return {"estado": "bloqueado", "deudas": [],
                "texto": "la sede no enseña las deudas hasta que mires las notificaciones pendientes (no la abro)"}
    if re.search(r"No existen deudas", t, re.I):
        return {"estado": "sin_deudas", "deudas": [], "texto": "no existen deudas"}
    filas = [f for f in tabla(texto, ("Importe",)) if any(re.search(r"\d+,\d{2}", v) for v in f.values())]
    return {"estado": "con_deudas" if filas else "ilegible", "deudas": filas,
            "texto": f"{len(filas)} deuda(s)" if filas else "no entiendo la pantalla de deudas (mírala a mano)"}


def expedientes_de(texto: str) -> list[dict]:
    """Las ramas de «Mis expedientes» con su número: «Censales (1)»…"""
    i = (texto or "").find("Desplegar")
    fin = (texto or "").find("Además, le pueden interesar")
    out = []
    for linea in (texto or "")[i if i >= 0 else 0:fin if fin > 0 else None].splitlines():
        m = re.match(r"^\s*(.+?)\s+\((\d+)\)\s*$", linea)
        if m:
            out.append({"nombre": m.group(1), "n": int(m.group(2))})
    return out


def alertas_de(texto: str) -> list[str]:
    if re.search(r"No existen Alertas", texto or "", re.I):
        return []
    m = re.search(r"Mis Alertas\s*\(\d+\)(.*?)(Pulse en cada alerta|$)", texto or "", re.S)
    return [_limpio(l) for l in (m.group(1).splitlines() if m else []) if _limpio(l)]


def accesos_de(texto: str) -> list[dict]:
    return [{"fecha": f.get("Fecha y hora", ""), "modo": f.get("Modo de autenticación", "").rstrip(" *"),
             "canal": f.get("Canal", "")} for f in tabla(texto, ("Fecha y hora", "Modo de autenticación"))]


# ─── presentado, ROI, datos fiscales, domiciliaciones ───────────────────────────────────────

_FILA_PRESENTADO = re.compile(
    r"(\d{4}[0-9A-Z]{8,14})\s+([0-9A-Z]{1,3})\s+([A-ZÁÉÍÓÚÑ]+)\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})")


def presentados_de(texto: str) -> list[dict]:
    return [{"expediente": e, "periodo": p, "estado": s, "presentada": c, "ejercicio": e[:4]}
            for e, p, s, c in _FILA_PRESENTADO.findall(_limpio(texto))]


def justificante_de(texto_pagina_1: str) -> dict:
    """Primera página del justificante: quién lo presentó, cuándo, con qué CSV y qué salió."""
    t = texto_pagina_1 or ""
    def g(patron):
        m = re.search(patron, t)
        return _limpio(m.group(1)) if m else ""
    return {"presentada": g(r"Presentación realizada el:\s*(.+)"), "expediente": g(r"Expediente/Referencia[^:]*:\s*(\S+)"),
            "csv": g(r"Código Seguro de Verificación:\s*(\S+)"), "justificante": g(r"Número de justificante:\s*(\S+)"),
            "via": g(r"Vía de entrada:\s*(.+)"), "presentador_nif": g(r"NIF Presentador:\s*(\S+)"),
            "presentador": g(r"Apellidos y Nombre / Razón social:\s*(.+)"), "en_calidad_de": g(r"En calidad de:\s*(.+)"),
            "resultado": g(r"\n(A INGRESAR|A COMPENSAR|A DEVOLVER|SIN ACTIVIDAD|NEGATIVA|CUOTA CERO|DOMICILIACI[ÓO]N[^\n]*)\s*\n")}


def roi_de(texto: str) -> dict:
    t = _limpio(texto)
    csv = re.search(r"Código Seguro de Verificación\s*:\s*(\S+)", t)
    fecha = re.search(r"A FECHA (\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})", t)
    if "NO CONSTA NINGÚN OPERADOR" in t:
        en = False
    elif "CONSTA UN OPERADOR" in t or "CONSTA  UN OPERADOR" in t:
        en = True
    else:
        en = None
    return {"en_roi": en, "csv": csv.group(1) if csv else "", "fecha": fecha.group(1) if fecha else ""}


def datos_fiscales_de(texto: str) -> list[dict]:
    """Bloques de «Datos fiscales»: título en mayúsculas y su tabla (Código…), con el total."""
    out, lineas = [], (texto or "").splitlines()
    for i, l in enumerate(lineas):
        titulo = l.strip()
        if not (len(titulo) > 8 and titulo.upper() == titulo and "\t" not in l and re.search(r"[A-ZÁÉÍÓÚ]{4}", titulo)):
            continue
        siguiente = next((x for x in lineas[i + 1:i + 5] if x.strip()), "")
        if not siguiente.strip().startswith("Código"):
            continue
        filas = tabla("\n".join(lineas[i + 1:i + 80]), ("Código",))
        datos = [f for f in filas if re.match(r"[A-Z]{2,4}\d{3,5}$", f.get("Código", ""))]
        total = next((f for f in filas if "TOTAL" in f.values()), None)
        out.append({"seccion": titulo, "filas": datos, "total": total})
    return out


def domiciliaciones_de(texto: str) -> list[dict]:
    if re.search(r"No se han obtenido resultados", texto or ""):
        return []
    return [f for f in tabla(texto, ("Modelo", "Importe")) if any(f.values())]


# ─── consultas (con el navegador) ───────────────────────────────────────────────────────────

def consultar(nav, que: tuple[str, ...], nif: str = "", modelos: tuple[str, ...] = MODELOS_PRESENTADOS,
              ejercicio_datos_fiscales: int | None = None, es_sociedad: bool = True) -> dict:
    """Ejecuta las consultas pedidas en una sola sesión. Una pantalla que falla no tumba las
    demás: su error queda en `errores`."""
    from gestoria.navegador import Prohibido

    d: dict = {"errores": {}, "consultado": datetime.now().isoformat(timespec="seconds")}

    def paso(nombre, fn):
        try:
            d[nombre] = fn()
        except Prohibido as e:
            d["errores"][nombre] = str(e)
        except Exception as e:  # una pantalla lenta o cambiada no tumba el resto
            d["errores"][nombre] = f"{type(e).__name__}: {(str(e).strip().splitlines() or [''])[0][:200]}"

    t = nav.texto
    if "notificaciones" in que:
        def _resumen():
            texto = t(URL["resumen"], etiqueta="resumen")
            d["no_leidas"] = no_leidas_de(texto)
            return resumen_de(texto)
        paso("resumen", _resumen)
        paso("notificaciones", lambda: notificaciones_de(t(URL["notificaciones"], etiqueta="notificaciones")))
    if "censo" in que:
        paso("censo", lambda: censo_de(t(URL["censo"], etiqueta="censo")))
        paso("situacion", lambda: situacion_de(nav.html(URL["censo"], enlaces=("Mi Situación Tributaria",))))
        paso("actividades", lambda: actividades_de(t(URL["censo"], enlaces=("Mis Actividades Económicas",))))
        paso("representantes", lambda: representantes_de(t(URL["representantes"])))
        if es_sociedad:
            paso("socios", lambda: socios_de(t(URL["censo"], enlaces=("Mis Socios / Partícipes",))))
        paso("avisos", lambda: avisos_de(t(URL["avisos"])))
    if "obligaciones" in que or "censo" in que:
        # sin pasar antes por «Mis datos censales», «Mis obligaciones» sale vacía (20-oct-2026)
        def _obl():
            t(URL["censo"])
            texto = t(URL["obligaciones"], etiqueta="obligaciones")
            d["estado_censal"] = situacion_estado_de(texto)
            return obligaciones_de(texto)
        paso("obligaciones", _obl)
    if "poderes" in que:
        paso("poderes_otorgados", lambda: poderes_de(t(URL["poderes_otorgados"], pulsar=("Buscar",), etiqueta="poderes")))
        paso("poderes_recibidos", lambda: poderes_de(t(URL["poderes_recibidos"], pulsar=("Buscar",))))
    if "deudas" in que:
        def _deudas():
            previo = deudas_de(t(URL["deudas"]))
            if previo["estado"] == "bloqueado":  # la sede pide mirar antes las notificaciones: no se sigue
                return previo
            return deudas_de(t(URL["deudas"], pulsar=("Aceptar",), etiqueta="deudas"))
        paso("deudas", _deudas)
    if "expedientes" in que:
        paso("expedientes", lambda: expedientes_de(t(URL["expedientes"], enlaces=("Todos", "Desplegar"))))
    if "alertas" in que:
        paso("alertas", lambda: alertas_de(t(URL["alertas"])))
    if "accesos" in que:
        paso("accesos", lambda: accesos_de(t(URL["accesos"])))
    if "presentados" in que:
        d["presentados"] = {}
        for m in modelos:
            paso(f"presentados_{m}", lambda m=m: presentados_de(
                t(URL["presentados"].format(modelo=m), pulsar=("Buscar",), etiqueta=f"presentados_{m}")))
            if f"presentados_{m}" in d:
                d["presentados"][m] = d.pop(f"presentados_{m}")
    if "roi" in que and nif:
        paso("roi", lambda: roi_de(t(URL["roi"], rellenar={"#nif": nif}, pulsar=("Enviar",), etiqueta="roi")))
    if "datos_fiscales" in que:
        aa = f"{(ejercicio_datos_fiscales or date.today().year - 1) % 100:02d}"
        url = URL["datos_fiscales_sociedades" if es_sociedad else "datos_fiscales_renta"].format(aa=aa)
        paso("datos_fiscales", lambda: datos_fiscales_de(t(url, etiqueta="datos_fiscales")))
    if "domiciliaciones" in que:
        paso("domiciliaciones", lambda: domiciliaciones_de(t(URL["domiciliaciones"], pulsar=("Buscar",))))
    return d


def descargar_presentado(nav, modelo: str, ejercicio: int, periodo: str, destino) -> dict:
    """El justificante (PDF) y el fichero presentado de una declaración: copias de lo que ya
    está presentado, no cambian nada. Columnas «Obtención de Justificante» y «Descarga fichero
    presentado» del listado (21-oct-2026). Si hay varias del mismo periodo, la última."""
    from pathlib import Path

    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    pg = nav.abrir(URL["presentados"].format(modelo=modelo))
    try:
        pg = nav.pulsar(pg, "Buscar")
        filas = pg.locator("tr:has-text('Ver')")
        elegida = None
        for i in range(filas.count()):
            f = presentados_de(filas.nth(i).inner_text())
            if f and f[0]["ejercicio"] == str(ejercicio) and f[0]["periodo"] == periodo and f[0]["estado"] != "BAJA":
                elegida = (filas.nth(i), f[0])
        if elegida is None:
            return {"encontrado": False}
        fila, info = elegida
        out = {"encontrado": True, **info}
        exp = info["expediente"]
        vers = fila.get_by_text("Ver", exact=True)
        # 2.º «Ver»: el fichero presentado, se descarga tal cual
        with pg.expect_download(timeout=30000) as dl:
            vers.nth(1).click()
        f = destino / f"{modelo}_{exp}.txt"
        dl.value.save_as(f)
        out["fichero"] = str(f)
        # 1.er «Ver»: el justificante, en una pestaña con el PDF dentro de un iframe del cotejo
        n = len(nav.ctx.pages)
        vers.nth(0).click()
        pg.wait_for_timeout(6000)
        for extra in nav.ctx.pages[n:]:
            extra.wait_for_load_state("networkidle")
            src = next((x.get_attribute("src") for x in extra.locator("iframe").all()
                        if "Cotejo" in (x.get_attribute("src") or "")), None)
            pdf = destino / f"{modelo}_{exp}_justificante.pdf"
            pdf.write_bytes(nav.ctx.request.get(src or extra.url).body())
            out["justificante"] = str(pdf)
        return out
    finally:
        for p in list(nav.ctx.pages):
            p.close()


def leer_justificante(pdf) -> dict:
    """La primera página del PDF del justificante → justificante_de()."""
    import io
    import logging

    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    r = PdfReader(io.BytesIO(open(pdf, "rb").read()))
    return justificante_de(r.pages[0].extract_text() or "")
