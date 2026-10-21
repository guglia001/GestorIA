"""El texto VIGENTE de un artículo, leído del BOE consolidado en el momento (nunca de memoria).

Se usa la versión «texto completo» (`&tn=0`) de la página de la norma y se corta desde
«Artículo N.» hasta el artículo siguiente. Normas que más se usan, con su identificador, en
`skills/normativa-fiscal/SKILL.md`. Fuente: https://www.boe.es/buscar/legislacion.php
"""
from __future__ import annotations

import html
import re
import urllib.request
from datetime import date


def url(id_boe: str) -> str:
    return f"https://www.boe.es/buscar/act.php?id={id_boe}&tn=0"


def _plano(h: str) -> str:
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"</(p|h\d|div|li|tr)>|<br\s*/?>", "\n", h, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h))
    # algunas normas (Ley 39/2015) traen «Artículo\xa043.»: el espacio duro también es blanco
    t = re.sub(r"[ \t\r\f\v\xa0]+", " ", t)
    return "\n".join(l.strip() for l in t.split("\n") if l.strip())


def extraer(pagina_html: str, numero: str) -> str | None:
    """«Artículo <numero>.» … hasta el siguiente «Artículo …» (o el final)."""
    t = _plano(pagina_html)
    m = re.search(rf"^Artículo {re.escape(numero)}\.", t, re.M)
    if not m:
        return None
    sig = re.search(r"^Artículo \d+[\w ]*\.", t[m.end():], re.M)
    return t[m.start(): m.end() + sig.start() if sig else None].strip()


def articulo(id_boe: str, numero: str) -> dict:
    req = urllib.request.Request(url(id_boe), headers={"User-Agent": "Mozilla/5.0 gestoria"})
    with urllib.request.urlopen(req, timeout=60) as r:
        h = r.read().decode("utf-8", "ignore")
    return {"texto": extraer(h, numero), "url": url(id_boe), "consultado": date.today().isoformat()}
