"""DEHú (Dirección Electrónica Habilitada única): las notificaciones de TODAS las
administraciones adheridas en un solo sitio (AEAT, DGT, Seguridad Social, comunidades
autónomas, ayuntamientos…). SOLO LECTURA: se lee la lista, nunca se comparece.

Comparecer (abrir) una notificación la da por practicada ese día y arranca los plazos (art.
43.2 Ley 39/2015). GestorIA no lo hace nunca: avisa de la que está pendiente, de quién es, desde
cuándo y si llega también en papel.

Cómo entra (comprobado el 21-oct-2026): dehu.redsara.es → «Acceder a DEHú» → Cl@ve →
«Acceso DNIe / Certificado electrónico» (el certificado se presenta en
pasarela-ident.clave.gob.es). Las pantallas de la DEHú piden sus datos a su propia API
(/api/v1/notifications, /api/v1/realized_notifications, /api/v1/communications): se leen esas
respuestas, que ya vienen en JSON.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

INICIO = "https://dehu.redsara.es/es/public"
LISTAS = {"pendientes": ("https://dehu.redsara.es/es/notifications", "/api/v1/notifications"),
          "realizadas": ("https://dehu.redsara.es/es/notifications", "/api/v1/realized_notifications"),
          "comunicaciones": ("https://dehu.redsara.es/es/communications", "/api/v1/communications")}


def elementos(respuesta: dict | list | None) -> list[dict]:
    """Los elementos de una respuesta de la API de la DEHú, con nombres en castellano."""
    items = (respuesta or {}).get("items", []) if isinstance(respuesta, dict) else (respuesta or [])
    out = []
    for i in items:
        out.append({"organismo": i.get("emitterEntity") or "", "origen": i.get("emitterSourceEntity") or "",
                    "identificador": i.get("identifier") or "", "concepto": i.get("concept") or "",
                    "descripcion": i.get("description") or "", "puesta": (i.get("availabilityDate") or "")[:16],
                    "caduca": (i.get("expirationDate") or "")[:16] or None, "realizada": (i.get("finalDate") or "")[:16] or None,
                    "estado": i.get("state") or "", "en_papel": bool(i.get("postalDelivery")),
                    "vinculo": i.get("bondType") or ""})
    return out


def _entrar(nav):
    from gestoria.navegador import comprobar

    pg = nav.abrir(INICIO, espera=3000)
    acceso = pg.locator("button:visible, a:visible").filter(has_text=re.compile("Acceder", re.I))
    acceso.first.wait_for(state="visible", timeout=30000)
    comprobar("Acceder a DEHú")
    acceso.first.click()
    pg.wait_for_url(re.compile(r"clave\.gob\.es"), timeout=60000)
    certificado = pg.locator("button:visible, a:visible").filter(has_text=re.compile("Acceso DNIe", re.I))
    try:
        certificado.first.wait_for(state="visible", timeout=30000)
    except Exception:
        raise RuntimeError("no encuentro «Acceso DNIe / Certificado electrónico» en Cl@ve") from None
    certificado.first.click()
    try:
        pg.wait_for_url(re.compile(r"dehu\.redsara\.es/es/home"), timeout=90000)
    except Exception:
        texto = pg.inner_text("body")
        raise RuntimeError("Cl@ve no ha aceptado el certificado" + (": no se envió" if "No se ha seleccionado" in texto else "")) from None
    pg.wait_for_timeout(3000)
    return pg


def consultar(nav, espera_max: int = 45) -> dict:
    """{"pendientes": [...], "realizadas": [...], "comunicaciones": [...], "titular": "..."}.
    Si no llega a leer la lista de pendientes, falla: nunca dice «ninguna» sin haberla leído."""
    vistas: list = []                      # las respuestas se guardan aquí y se leen después:
    oir = lambda r: vistas.append(r) if "/api/v1/" in r.url else None   # leerlas dentro del evento a veces falla
    nav.ctx.on("response", oir)
    respuestas: dict[str, dict] = {}
    try:
        pg = _entrar(nav)
        for url in dict.fromkeys(u for u, _ in LISTAS.values()):
            pg.goto(url, timeout=90000, wait_until="networkidle")
            faltan = [n for n, (u, _) in LISTAS.items() if u == url]
            for _ in range(espera_max):
                for r in list(vistas):
                    for nombre, (_, api) in LISTAS.items():
                        if nombre not in respuestas and (api + "?" in r.url or r.url.endswith(api)) and r.request.method == "GET":
                            try:
                                respuestas[nombre] = r.json()
                            except Exception:
                                pass
                    if "/api/v1/user/" in r.url and "usuario" not in respuestas:
                        try:
                            respuestas["usuario"] = r.json()
                        except Exception:
                            pass
                if all(n in respuestas for n in faltan):
                    break
                pg.wait_for_timeout(1000)
    finally:
        nav.ctx.remove_listener("response", oir)
        for p in list(nav.ctx.pages):
            p.close()
    if "pendientes" not in respuestas:
        raise RuntimeError("he entrado en la DEHú pero no he podido leer la lista de notificaciones pendientes: mírala a mano")
    persona = (respuestas.get("usuario") or {}).get("person") or {}
    return {"titular": persona.get("fullName", ""), "consultado": datetime.now().isoformat(timespec="seconds"),
            **{n: elementos(respuestas.get(n)) for n in LISTAS},
            "leidas": sorted(n for n in LISTAS if n in respuestas)}


def resumen(d: dict) -> str:
    p = d.get("pendientes") or []
    return "✅ ninguna notificación pendiente" if not p else f"🔴 {len(p)} notificación(es) pendiente(s) de comparecer"


def a_json(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=1)
