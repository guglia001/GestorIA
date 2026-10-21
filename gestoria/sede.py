"""Validar ficheros en el SIMULADOR público de la AEAT (OPEN): no pide certificado y desde él
no se puede presentar. Pasos: abrir, «Importar», elegir el fichero y leer la tabla «Errores y
avisos» que el formulario abre solo al importar.
URL publicada en la ficha del procedimiento G414 (modelo 303), sede de la AEAT, 20-oct-2026.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

SIMULADOR = {"303": "https://www2.agenciatributaria.gob.es/wlpl/A303-FWME/E{ejercicio}/OPEN/index.zul"}
PROHIBIDO = ("Firmar", "Presentar", "Enviar")  # además de gestoria.navegador.PROHIBIDO: el simulador no envía nada
# El simulador coteja el NIF con el censo: con un NIF inventado (los ejemplos) sale siempre
# «E010072 Declarante no identificado» y el formulario no abre sus páginas, así que no se pueden
# leer las casillas; con un NIF real dado de alta, sí (20-oct-2026).
NO_IDENTIFICADO = "E010072"
# «E010541» (error), «31190» (aviso), «FRECH» (fichero rechazado). La línea va antes, con 1-3 cifras.
_CODIGO = re.compile(r"^(FRECH|[A-Z]\d{5,6}|\d{5})$")


def _pulsar(pg, nombre: str) -> None:
    from gestoria.navegador import comprobar

    comprobar(nombre)
    if any(p.lower() in nombre.lower() for p in PROHIBIDO):
        raise RuntimeError(f"GestorIA no pulsa «{nombre}»: solo prepara y valida")
    pg.get_by_text(nombre, exact=True).first.click()


def tabla_errores(texto: str) -> list[dict]:
    """Filas de la tabla «Errores y avisos» del formulario: código, línea y descripción.
    En el texto de la página cada celda va en su línea: … línea, código, descripción …"""
    i = texto.find("Errores y avisos")
    if i < 0:
        return []
    fin = texto.find("Volver a la página principal", i)
    celdas = [c.strip() for c in texto[i:fin if fin > 0 else None].splitlines() if c.strip()]
    filas = []
    for k, c in enumerate(celdas):
        if _CODIGO.match(c):
            linea = celdas[k - 1] if k and celdas[k - 1] not in ("-", "Código") else ""
            desc = celdas[k + 1] if k + 1 < len(celdas) else ""
            filas.append({"codigo": c, "linea": linea if linea.isdigit() else "", "descripcion": desc})
    return filas


CONFIRMACION = "00001"  # «No existen errores.», con el ✔ verde


def _clasificar(filas: list[dict]) -> tuple[list[str], list[str]]:
    errores, avisos = [], []
    for f in filas:
        if f["codigo"] == CONFIRMACION:
            continue
        txt = f"{f['codigo']}{' (línea ' + f['linea'] + ')' if f['linea'] else ''}: {f['descripcion']}"
        (errores if f["codigo"] == "FRECH" or f["codigo"].startswith("E") else avisos).append(txt)
    return errores, avisos


def sin_errores(filas: list[dict]) -> bool:
    return any(f["codigo"] == CONFIRMACION for f in filas)


def diferencias(fichero: dict[str, Decimal], aeat: dict[str, Decimal],
                constantes: set[str] = frozenset()) -> list[tuple[str, Decimal, Decimal]]:
    """Casillas en las que el formulario de la AEAT (que recalcula los totales) no da lo mismo
    que nuestro fichero. Una casilla que no aparece vale 0; los tipos fijos no cuentan."""
    cero = Decimal("0.00")
    out = []
    for k in sorted(set(fichero) | set(aeat), key=int):
        if k in constantes:
            continue
        a, b = fichero.get(k, cero), aeat.get(k, cero)
        if a != b:
            out.append((k, a, b))
    return out


# Los importes del formulario son <input> con la casilla en aria-label (« 01», «151»…).
_JS_CASILLAS = """() => Array.from(document.querySelectorAll('input'))
  .filter(i => i.type !== 'hidden' && /^\\s*\\d{1,3}\\s*$/.test(i.getAttribute('aria-label') || ''))
  .map(i => [i.getAttribute('aria-label').trim(), i.value])"""


def _casillas_del_formulario(pg, max_paginas: int = 12) -> dict[str, Decimal]:
    from gestoria.numeros import importe

    out: dict[str, Decimal] = {}
    for _ in range(max_paginas):
        nuevas = {k.zfill(2): importe(v) for k, v in pg.evaluate(_JS_CASILLAS) if v.strip()}
        if nuevas and set(nuevas) <= set(out):
            break  # ya no avanza: última página
        out.update({k: v for k, v in nuevas.items() if v is not None})
        siguiente = pg.get_by_title("Página siguiente [K]")
        if not siguiente.count():
            break
        siguiente.first.click()
        pg.wait_for_timeout(2000)
    return out


# ─── Sede con certificado: SOLO LECTURA ─────────────────────────────────────────────────────
# Las pantallas y sus lectores viven en gestoria.aeat; el navegador con certificado, en
# gestoria.navegador. Aquí queda la «foto» rápida que guarda `gestoria sede` para el panel.
from gestoria.aeat import no_leidas_de, notificaciones_de, obligaciones_de, presentados_de  # noqa: E402,F401


def vies(nif: str) -> dict:
    """¿NIF-IVA válido en el VIES? (servicio de la Comisión Europea, sin certificado)."""
    import json
    import urllib.request

    nif = nif.upper().replace(" ", "")
    # «ESB00000000» / «IE0000000X» llevan el país delante; un NIF español suelto (9) no
    pais, num = (nif[:2], nif[2:]) if len(nif) > 9 and nif[:2].isalpha() else ("ES", nif)
    req = urllib.request.Request(
        "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number",
        data=json.dumps({"countryCode": pais, "vatNumber": num}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return {"nif": pais + num, "valido": bool(d.get("valid")), "nombre": d.get("name"),
            "consulta": d.get("requestDate")}


def foto(pfx: Path, clave: str, modelos: tuple[str, ...] = ("303", "390", "200", "036")) -> dict:
    """Notificaciones (sin abrirlas), obligaciones de alta y lo presentado de cada modelo."""
    from gestoria import aeat
    from gestoria.navegador import Navegador

    with Navegador(pfx, clave, sitios=("aeat",)) as nav:
        d = aeat.consultar(nav, ("notificaciones", "obligaciones", "presentados"), modelos=modelos)
    d.setdefault("presentados", {})
    return d


def validar(modelo: str, ejercicio: int, fichero: Path, capturas: Path) -> dict:
    from playwright.sync_api import sync_playwright

    capturas.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%dT%H%M%S")
    out: dict = {"errores": [], "avisos": [], "texto": "", "capturas": [], "importado": False,
                 "sin_errores": False, "casillas_aeat": {}}
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True)
        pg = nav.new_page(locale="es-ES")
        pg.goto(SIMULADOR[modelo].format(ejercicio=ejercicio), timeout=90000, wait_until="networkidle")
        with pg.expect_file_chooser(timeout=30000) as fc:
            _pulsar(pg, "Importar")
        fc.value.set_files(str(fichero))
        pg.wait_for_timeout(6000)
        foto = capturas / f"{sello}_{modelo}_importado.png"
        pg.screenshot(path=str(foto), full_page=True)
        out["capturas"].append(str(foto))
        # Al importar, el formulario valida solo y abre «Errores y avisos» (20-oct-2026): no
        # hace falta pulsar «Validar», que además queda tapado por ese panel.
        texto = pg.inner_text("body")
        filas = tabla_errores(texto)
        out["importado"] = not any(f["codigo"] == "FRECH" for f in filas)
        out["sin_errores"] = sin_errores(filas)
        out["texto"] = texto
        if out["importado"]:
            out["casillas_aeat"] = _casillas_del_formulario(pg)
        nav.close()
    out["errores"], out["avisos"] = _clasificar(filas)
    return out
