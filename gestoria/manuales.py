"""Copia local y buscador de los manuales prácticos oficiales de la AEAT.

Descarga los manuales (PDF) y las guías que solo existen en HTML (guía del 036, manual de
actividades económicas), guarda el texto página a página en ~/.cache/gestoria/manuales/ y busca
sin acentos ni mayúsculas. Cada resultado lleva la página (PDF) o la URL exacta (HTML): es lo
que se cita. Los manuales salen una vez al año; `al_dia()` comprueba la versión del servidor
como mucho una vez al día. Lo que cambia a diario (BOE, consultas de la DGT) no se copia: se lee
en vivo. Al cambiar de ejercicio, actualizar las URL con el índice
https://sede.agenciatributaria.gob.es/Sede/manuales-practicos.html
"""
from __future__ import annotations

import html
import io
import json
import re
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

CACHE = Path.home() / ".cache" / "gestoria" / "manuales"
SEDE = "https://sede.agenciatributaria.gob.es"
PDFS = SEDE + "/static_files/Sede/Biblioteca/Manual/Practicos"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) gestoria/0.1"}

MANUALES = {
    "iva": {"titulo": "Manual práctico de IVA 2026", "pdf": PDFS + "/IVA/Manual_IVA_2026.pdf"},
    "sociedades": {"titulo": "Manual práctico de Sociedades 2025",
                   "pdf": PDFS + "/Sociedades/Manual_Sociedades_2025.pdf"},
    "renta": {"titulo": "Manual práctico de Renta 2025, parte 1",
              "pdf": PDFS + "/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf"},
    "censal": {
        "titulo": "Guía práctica para cumplimentar el modelo censal 036",
        "indice": SEDE + "/Sede/Ayuda/guia-practica-declaracion-censal.html",
        "prefijos": ("/Sede/ayuda/manuales-videos-folletos/manuales-practicos/"
                     "guia-practica-cumplimentacion-modelo-censal-036/",
                     "/Sede/Ayuda/guia-practica-declaracion-censal/"),
    },
    "actividades": {
        "titulo": "Manual de actividades económicas (obligaciones de empresarios)",
        "indice": SEDE + "/Sede/ayuda/manuales-videos-folletos/manuales-practicos/"
                         "folleto-actividades-economicas.html",
        "prefijos": ("/Sede/ayuda/manuales-videos-folletos/manuales-practicos/"
                     "folleto-actividades-economicas/",),
    },
}


def _get(url: str, intentos: int = 3) -> tuple[bytes, dict]:
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read(), dict(r.headers)
        except Exception:
            if i == intentos - 1:
                raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("inalcanzable")


def _texto_html(crudo: bytes) -> str:
    s = crudo.decode("utf-8", "ignore")
    m = re.search(r"<main\b.*?</main>", s, re.S | re.I)
    s = m.group(0) if m else s
    s = re.sub(r"<(script|style|nav|header|footer)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</tr>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def _meta(clave: str, cache: Path = CACHE) -> dict:
    f = cache / f"{clave}.meta.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _guardar(clave: str, paginas: list[dict], meta: dict, cache: Path = CACHE) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    with open(cache / f"{clave}.jsonl", "w", encoding="utf-8") as f:
        for p in paginas:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    ahora = datetime.now().isoformat(timespec="seconds")
    meta.update(paginas=len(paginas), descargado=ahora, comprobado=ahora)
    (cache / f"{clave}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))


def descargar(clave: str) -> int:
    m = MANUALES[clave]
    if "pdf" in m:
        from pypdf import PdfReader  # extra opcional: pip install 'gestoria[manuales]'

        crudo, cab = _get(m["pdf"])
        lector = PdfReader(io.BytesIO(crudo))
        paginas = [{"pag": i + 1, "url": m["pdf"], "texto": p.extract_text() or ""}
                   for i, p in enumerate(lector.pages)]
        _guardar(clave, paginas, {"titulo": m["titulo"], "url": m["pdf"],
                                  "last_modified": cab.get("Last-Modified")})
        return len(paginas)
    crudo, cab = _get(m["indice"])
    enlaces = list(dict.fromkeys(SEDE + h for h in re.findall(r'href="(/Sede/[^"#?]+\.html)"',
                                                             crudo.decode("utf-8", "ignore"))
                                 if h.startswith(m["prefijos"])))
    paginas = [{"pag": 0, "url": m["indice"], "texto": _texto_html(crudo)}]
    for n, u in enumerate(enlaces, 1):
        try:
            paginas.append({"pag": n, "url": u, "texto": _texto_html(_get(u)[0])})
        except Exception as e:  # una subpágina caída no tumba la guía entera
            print(f"  ✗ {u}: {e}", file=sys.stderr)
        time.sleep(0.2)
    _guardar(clave, paginas, {"titulo": m["titulo"], "url": m["indice"],
                              "last_modified": cab.get("Last-Modified")})
    return len(paginas)


def al_dia(clave: str) -> str:
    """Como mucho una vez al día: ¿la copia local es la que sirve la AEAT? Si no, se re-baja."""
    m, meta, ahora = MANUALES[clave], _meta(clave), datetime.now()
    if not meta:
        descargar(clave)
        return "descargado (no estaba)"
    if (ahora - datetime.fromisoformat(meta["comprobado"])).total_seconds() < 86400:
        return "al día (comprobado hace <24 h)"
    req = urllib.request.Request(m.get("pdf") or m["indice"], headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        lm = r.headers.get("Last-Modified")
    edad = (ahora - datetime.fromisoformat(meta["descargado"])).days
    if meta.get("last_modified") not in (None, lm) or ("indice" in m and edad > 7):
        descargar(clave)
        return f"RE-DESCARGADO (servidor: {lm})"
    meta.update(last_modified=lm, comprobado=ahora.isoformat(timespec="seconds"))
    (CACHE / f"{clave}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return f"al día (servidor: {lm})"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def buscar(consulta: str, claves: list[str], maximo: int = 8, contexto: int = 350,
           cache: Path = CACHE) -> list[dict]:
    """Páginas que contienen todos los términos (>2 letras), la frase exacta puntúa más."""
    frase = _norm(consulta).strip()
    terminos = [t for t in frase.split() if len(t) > 2] or [frase]
    res = []
    for clave in claves:
        f = cache / f"{clave}.jsonl"
        if not f.exists():
            continue
        for p in (json.loads(l) for l in f.open(encoding="utf-8")):
            t = _norm(p["texto"])
            if not all(term in t for term in terminos):
                continue
            i = t.find(frase)
            i = i if i >= 0 else t.find(terminos[0])
            trozo = re.sub(r"\s+", " ", p["texto"][max(0, i - contexto): i + len(frase) + contexto]).strip()
            res.append({"manual": clave, "pagina": p["pag"], "url": p["url"], "extracto": trozo,
                        "puntos": 100 * t.count(frase) + sum(t.count(x) for x in terminos)})
    return sorted(res, key=lambda r: -r["puntos"])[:maximo]
