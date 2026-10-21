"""Diseños de registro de la AEAT (xlsx oficiales) → ficheros para «Importar» en la sede.

La AEAT publica para cada modelo y ejercicio un Excel con una hoja por página del fichero: nº de
campo, posición, longitud, tipo y descripción; la casilla del formulario va entre corchetes al
final de la descripción («… Base imponible [01]»). Se lee tal cual: si cambia una posición, se
cambia el Excel, no el código. Tipos (nota de cada hoja): An alfanumérico (izquierda, blancos),
A alfabético, Num numérico sin signo (derecha, ceros), N numérico con signo («N» delante).
Fuente: https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro.html
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

DISENOS = Path(__file__).parent / "disenos"
_CASILLA = re.compile(r"\[(\d{1,3})\]")
_CONST = re.compile(r'Constante\s*"([^"]*)"')
# Constante sin la palabra: la celda es solo el valor entre comillas («"00050". Nota 7.»). No
# confundir con opciones («"1" SI, "2" NO»): esas llevan más texto detrás.
_CONST_SOLA = re.compile(r'^"([^"]*)"\.?\s*(Nota\s*\d+\.?\s*)?$')
_DEC = re.compile(r"(\d+)\s+enteros?\s+y?\s*(\d+)\s+decimal", re.I)


@dataclass
class Campo:
    n: int
    pos: int
    lon: int
    tipo: str
    desc: str
    casilla: str | None
    constante: str | None
    decimales: int | None


@dataclass
class Pagina:
    codigo: str
    campos: list[Campo] = field(default_factory=list)
    longitud: int = 0

    def campo(self, casilla: str) -> Campo:
        for c in self.campos:
            if c.casilla == casilla:
                return c
        raise KeyError(f"la página {self.codigo} no tiene la casilla [{casilla}]")

    def buscar(self, texto: str) -> Campo:
        hay = [c for c in self.campos if texto.lower() in c.desc.lower()]
        if len(hay) != 1:
            raise KeyError(f"«{texto}» aparece {len(hay)} veces en la página {self.codigo}")
        return hay[0]


def _txt(x) -> str:
    return re.sub(r"\s+", " ", str(x if x is not None else "")).strip()


def cargar(xlsx: Path) -> dict[str, Pagina]:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    paginas: dict[str, Pagina] = {}
    for ws in wb.worksheets:
        filas = [tuple(r) for r in ws.iter_rows(values_only=True)]
        cab_i = next((i for i, f in enumerate(filas) if f and _txt(f[0]) == "Nº"), None)
        if cab_i is None:
            continue
        cab = [_txt(c) for c in filas[cab_i]]
        col = {k: cab.index(k) for k in ("Nº", "Posic.", "Lon", "Tipo", "Descripción")}
        extra = [cab.index(k) for k in ("Validación", "Contenido") if k in cab]
        campos: list[Campo] = []
        pos, total = 1, None
        for f in filas[cab_i + 1:]:
            if not f or f[col["Nº"]] is None:
                continue
            if _txt(f[col["Nº"]]).upper().startswith("TOTAL"):
                total = f[col["Posic."]]
                break
            lon = f[col["Lon"]]
            if not isinstance(lon, int):  # «Variable»: la cabecera DP30300, se monta en fichero()
                campos = []
                break
            desc = _txt(f[col["Descripción"]])
            resto = " ".join(_txt(f[i]) for i in extra)
            cas = _CASILLA.findall(desc)
            const = _CONST.search(resto)
            constante = const.group(1) if const else None
            if constante is None:
                sola = [m.group(1) for i in extra if (m := _CONST_SOLA.match(_txt(f[i])))]
                constante = sola[0] if sola and len(sola[0]) == lon else None
            dec = _DEC.search(desc + " " + resto)
            campos.append(Campo(n=len(campos) + 1, pos=pos, lon=lon, tipo=_txt(f[col["Tipo"]]),
                                desc=desc, casilla=cas[-1] if cas else None, constante=constante,
                                decimales=int(dec.group(2)) if dec else None))
            pos += lon
        if not campos:
            continue
        if isinstance(total, int) and total != pos - 1:
            raise ValueError(f"{xlsx.name}/{ws.title}: suma de longitudes {pos - 1} ≠ TOTAL {total}")
        codigo = campos[2].constante  # campo 3: «Página.» Constante "01000"
        paginas[codigo] = Pagina(codigo=codigo, campos=campos, longitud=pos - 1)
    return paginas


def _alfa(s) -> str:
    """Solo letras, números y blancos (nota 2 del diseño); mayúsculas; Ñ y Ç se conservan."""
    s = str(s).upper().replace("Ñ", "\0").replace("Ç", "\1")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.replace("\0", "Ñ").replace("\1", "Ç")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9ÑÇ ]", " ", s)).strip()


def formatear(c: Campo, valor) -> str:
    if valor is None:
        if c.constante is not None and len(c.constante) == c.lon:
            return c.constante
        return " " * c.lon if c.tipo in ("An", "A") else "0" * c.lon
    if c.tipo in ("An", "A"):
        s = _alfa(valor)
        if len(s) > c.lon:
            raise ValueError(f"campo {c.n} ({c.desc[:40]}): «{s}» pasa de {c.lon} caracteres")
        return s.ljust(c.lon)
    if c.decimales is not None:
        n = int((Decimal(str(valor)) * 10 ** c.decimales).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    else:
        n = int(valor)
    if n < 0:
        if c.tipo != "N":
            raise ValueError(f"campo {c.n} ({c.desc[:40]}) no admite negativos: {valor}")
        s = "N" + str(-n).zfill(c.lon - 1)
    else:
        s = str(n).zfill(c.lon)
    if len(s) > c.lon:
        raise ValueError(f"campo {c.n} ({c.desc[:40]}): {valor} no cabe en {c.lon}")
    return s


def pagina_texto(p: Pagina, valores: dict[int, object]) -> str:
    t = "".join(formatear(c, valores.get(c.n)) for c in p.campos)
    if len(t) != p.longitud:
        raise AssertionError(f"página {p.codigo}: {len(t)} ≠ {p.longitud}")
    return t


_PAGINA = re.compile(r"<T(\d{3})(\w{5})>(.*?)</T\1\2>", re.S)


def leer_fichero(texto: str, paginas: dict[str, Pagina]) -> dict[str, Decimal]:
    """Las casillas con importe de un fichero ya escrito: la inversa de pagina_texto()."""
    out: dict[str, Decimal] = {}
    for m in _PAGINA.finditer(texto):
        p = paginas.get(m.group(2))
        if p is None:
            continue
        t = m.group(0)
        for c in p.campos:
            if not c.casilla or c.decimales is None or c.constante is not None:
                continue
            s = t[c.pos - 1:c.pos - 1 + c.lon]
            n = -int(s[1:]) if s.startswith("N") else int(s)
            out[c.casilla] = Decimal(n).scaleb(-c.decimales).quantize(Decimal(10) ** -c.decimales)
    return out


def fichero(modelo: str, ejercicio: int, periodo: str, paginas: list[str],
            version: str = "", nif_desarrollo: str = "") -> str:
    """Hoja DP<modelo>00: «<T» modelo «0» EEEE PP «0000>» «<AUX>» … «</AUX>» páginas «</T…>»."""
    ident = f"{modelo}0{ejercicio:04d}{periodo}0000"
    aux = ("<AUX>" + " " * 70 + version.ljust(4)[:4] + " " * 4
           + nif_desarrollo.ljust(9)[:9] + " " * 213 + "</AUX>")
    return f"<T{ident}>" + aux + "".join(paginas) + f"</T{ident}>"
