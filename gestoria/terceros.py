"""Tus clientes y proveedores contra el censo de la AEAT: ¿existe ese NIF con ese nombre?

Usa el servicio web oficial de comprobación de NIF (VNifV2, «Calidad de datos
identificativos»), que pide certificado electrónico. Para cada pareja NIF + nombre responde
IDENTIFICADO o NO IDENTIFICADO; para una persona jurídica basta el NIF y devuelve su razón social
oficial, así que también se ven los nombres mal escritos en los libros.

Por qué importa: una factura recibida con el NIF del proveedor mal no es una factura completa y
su IVA no se deduce (art. 97 LIVA y art. 6.1.d RD 1619/2012), y un NIF mal en el 347 o el 349
es una declaración con errores. La propia AEAT advierte de que el servicio es para validar a
quien te factura o a quien facturas: usarlo para otra cosa puede bloquear el acceso.
"""
from __future__ import annotations

import re
import unicodedata
import urllib.request
from xml.sax.saxutils import escape

from gestoria import nif as nifmod

URL = "https://www1.agenciatributaria.gob.es/wlpl/BURT-JDIT/ws/VNifV2SOAP"
NS = ("http://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/"
      "burt/jdit/ws/VNifV2Ent.xsd")
LOTE = 100


def peticion(pares: list[tuple[str, str]]) -> str:
    cuerpo = "".join(f"<vnif:Contribuyente><vnif:Nif>{escape(n)}</vnif:Nif><vnif:Nombre>{escape(m[:80])}</vnif:Nombre>"
                     "</vnif:Contribuyente>" for n, m in pares)
    return ('<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
            f'xmlns:vnif="{NS}"><soapenv:Header/><soapenv:Body><vnif:VNifV2Ent>{cuerpo}</vnif:VNifV2Ent>'
            "</soapenv:Body></soapenv:Envelope>")


def respuesta(xml: str) -> list[dict]:
    out = []
    for bloque in re.findall(r"<(?:\w+:)?Contribuyente>(.*?)</(?:\w+:)?Contribuyente>", xml or "", re.S):
        def g(tag):
            m = re.search(rf"<(?:\w+:)?{tag}>(.*?)</(?:\w+:)?{tag}>", bloque, re.S)
            return m.group(1).strip() if m else ""
        out.append({"nif": g("Nif"), "nombre_censo": g("Nombre"), "resultado": g("Resultado")})
    if not out and "Fault" in (xml or ""):
        raise RuntimeError("la AEAT devolvió un error SOAP: " + re.sub(r"<[^>]+>", " ", xml)[:200])
    return out


def comprobar(pares: list[tuple[str, str]], contexto_tls) -> list[dict]:
    """[(nif, nombre)] → [{nif, nombre, nombre_censo, resultado}], de 100 en 100."""
    out = []
    for i in range(0, len(pares), LOTE):
        lote = pares[i:i + LOTE]
        req = urllib.request.Request(URL, data=peticion(lote).encode("utf-8"),
                                     headers={"Content-Type": "text/xml; charset=UTF-8", "SOAPAction": ""})
        with urllib.request.urlopen(req, context=contexto_tls, timeout=90) as r:
            filas = respuesta(r.read().decode("utf-8", "ignore"))
        for (n, nombre), f in zip(lote, filas):
            out.append({"nif": n, "nombre": nombre, "nombre_censo": f["nombre_censo"], "resultado": f["resultado"]})
    return out


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\b(S\.?\s?L\.?\s?U?|S\.?\s?A\.?\s?U?|SLU|SAU|SOCIEDAD LIMITADA|SOCIEDAD ANONIMA)\b\.?", " ", s)
    return re.sub(r"[^A-Z0-9Ñ]+", " ", s).strip()


def mismo_nombre(a: str, b: str) -> bool:
    return _norm(a) == _norm(b)


def de_los_libros(ventas, compras) -> list[tuple[str, str, str]]:
    """(nif, nombre, papel) únicos de clientes y proveedores con NIF español bien formado."""
    vistos: dict[str, tuple[str, str, str]] = {}
    for v in ventas:
        n = nifmod.normalizar(v.nif_cliente)
        if n and nifmod.es_espanol(n) and n not in vistos:
            vistos[n] = (n, v.cliente, "cliente")
    for c in compras:
        n = nifmod.normalizar(c.nif_proveedor)
        if n and nifmod.es_espanol(n) and n not in vistos:
            vistos[n] = (n, c.proveedor, "proveedor")
    return sorted(vistos.values())


def hallazgos(filas: list[dict], papeles: dict[str, str]) -> list[dict]:
    """🔴 NIF que no está en el censo · 🟡 razón social distinta de la del libro."""
    out = []
    for f in filas:
        papel = papeles.get(f["nif"], "tercero")
        if f["resultado"].upper().startswith("NO IDENTIFICADO"):
            out.append({"nivel": "🔴", "nif": f["nif"], "texto": f"{papel} {f['nombre']} ({f['nif']}): NO está en el censo con ese NIF y nombre"
                        + (" — sin factura completa su IVA no se deduce (art. 97 LIVA)" if papel == "proveedor" else
                           " — revisa la factura: un NIF mal no es factura completa (art. 6.1.d RD 1619/2012)")})
        elif f["resultado"].upper() == "IDENTIFICADO" and f["nombre_censo"] and not mismo_nombre(f["nombre"], f["nombre_censo"]) \
                and not nifmod.normalizar(f["nif"])[0].isdigit():
            out.append({"nivel": "🟡", "nif": f["nif"], "texto": f"{papel} {f['nif']}: en tus libros «{f['nombre']}», "
                        f"en el censo «{f['nombre_censo']}»"})
        elif f["resultado"] and f["resultado"].upper() not in ("IDENTIFICADO",):
            out.append({"nivel": "🟡", "nif": f["nif"], "texto": f"{papel} {f['nombre']} ({f['nif']}): {f['resultado']}"})
    return out
