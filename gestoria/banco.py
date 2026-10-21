"""El banco: los movimientos de tu cuenta, conciliados con tus libros registro.

De dónde salen:
- Los ficheros que dejes en `banco/` de tu carpeta. Puede ser Norma 43 (el formato de la banca
  española, cuaderno 43 de la AEB, que exportan todos los bancos), CSV o Excel.
- O los baja GestorIA (`gestoria banco --descargar`) con las cookies de tu sesión del banco: en
  `[banco]`, `cookies` es el cookies.txt que exporta tu navegador (o el JSON de una extensión) y
  `url_descarga` es la dirección del botón de descargar el extracto. Es una petición de lectura,
  sin navegador ni botones: no puede mover dinero. Las cookies de un banco dan acceso a la cuenta.
  Por eso el fichero tiene que tener permisos 600, GestorIA no las enseña nunca y caducan en
  minutos: se exportan justo antes.

La conciliación casa cada movimiento con una factura: emitida si entra dinero, recibida si sale.
Busca el mismo importe en una ventana de fechas y desempata por el nombre del cliente o proveedor
en el concepto. Después aparta lo que no necesita factura: pagos a Hacienda (y si cuadran con el 303
de tus libros), Seguridad Social, comisiones e intereses, traspasos, nóminas, préstamos y el socio.
Lo que queda suelto es lo que importa:
- un cobro sin factura puede ser una venta sin facturar (art. 2 RD 1619/2012);
- un pago sin factura es IVA que no se deduce (art. 97 LIVA) y un gasto sin justificar
  (art. 106.4 LGT);
- y quedan las facturas que aún no se han cobrado ni pagado.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from gestoria import D2
from gestoria.numeros import eur

# Conceptos comunes del cuaderno 43 (AEB), los que dicen algo para conciliar
CONCEPTO_COMUN = {"01": "talones y reintegros", "02": "ingresos", "03": "recibos domiciliados", "04": "transferencias",
                  "05": "préstamos", "06": "remesas de efectos", "08": "intereses", "11": "cajero automático",
                  "12": "tarjetas", "13": "operaciones con el extranjero", "14": "devoluciones e impagados",
                  "15": "nóminas y seguros sociales", "17": "intereses, comisiones y gastos", "99": "varios"}
# Lo que no necesita factura, por el concepto (en mayúsculas y sin acentos)
CATEGORIAS = (
    ("Hacienda", r"\bAEAT\b|AGENCIA (ESTATAL DE ADMINISTRACION )?TRIBUTARIA|\bHACIENDA\b|\bIMPUESTOS?\b|MODELO ?\d{3}\b"),
    ("Seguridad Social", r"\bTGSS\b|SEGURIDAD SOCIAL|TESORERIA GENERAL|\bRETA\b|CUOTA AUTONOMO"),
    ("comisiones e intereses del banco", r"COMISION|MANTENIMIENTO|\bINTERES|GASTOS? (DE )?(GESTION|BANCARI|CUENTA)|CUOTA TARJETA"),
    ("traspaso entre tus cuentas", r"TRASPASO|ENTRE CUENTAS|CUENTA PROPIA"),
    ("nóminas", r"\bNOMINA"),
    ("préstamo", r"PRESTAMO|AMORTIZACION"),
    ("socio", r"APORTACION|AMPLIACION DE CAPITAL|CAPITAL SOCIAL|\bSOCIO\b"),
)
VENTANA = (timedelta(days=30), timedelta(days=120))   # el cobro o pago, de 30 días antes a 120 después de la factura


@dataclass
class Movimiento:
    fecha: date
    importe: Decimal            # positivo, entra; negativo, sale
    concepto: str
    fecha_valor: date | None = None
    comun: str = ""             # concepto común del cuaderno 43
    referencia: str = ""
    saldo: Decimal | None = None
    origen: str = ""            # el fichero del que sale


@dataclass
class Extracto:
    cuenta: str
    movimientos: list[Movimiento] = field(default_factory=list)
    desde: date | None = None
    hasta: date | None = None
    saldo_inicial: Decimal | None = None
    saldo_final: Decimal | None = None
    origen: str = ""

    @property
    def cuadra(self) -> bool | None:
        """¿Saldo inicial + movimientos = saldo final? (None si el fichero no trae saldos)"""
        if self.saldo_inicial is None or self.saldo_final is None:
            return None
        return D2(self.saldo_inicial + sum((m.importe for m in self.movimientos), Decimal(0))) == D2(self.saldo_final)


# ─── leer extractos ─────────────────────────────────────────────────────────────────────────

def _aammdd(s: str) -> date:
    return date(2000 + int(s[0:2]), int(s[2:4]), int(s[4:6]))


def _imp43(s: str, clave: str) -> Decimal:
    """14 cifras con 2 decimales; clave 1 = debe (cargo, sale), 2 = haber (abono, entra)."""
    x = D2(Decimal(int(s)) / 100)
    return -x if clave == "1" else x


def leer_norma43(texto: str, origen: str = "") -> list[Extracto]:
    """Cuaderno 43 de la AEB: registros 11 (cabecera de cuenta), 22 (movimiento), 23 (más
    concepto), 33 (final de cuenta) y 88 (fin de fichero), de 80 posiciones."""
    extractos, actual = [], None
    for linea in texto.splitlines():
        linea = linea.rstrip("\r\n")
        if len(linea) < 2:
            continue
        tipo = linea[:2]
        if tipo == "11":
            actual = Extracto(cuenta=f"{linea[2:6]} {linea[6:10]} {linea[10:20]}", desde=_aammdd(linea[20:26]),
                              hasta=_aammdd(linea[26:32]), saldo_inicial=-_imp43(linea[33:47], "2") if linea[32] == "1"
                              else _imp43(linea[33:47], "2"), origen=origen)
            extractos.append(actual)
        elif tipo == "22" and actual is not None:
            actual.movimientos.append(Movimiento(
                fecha=_aammdd(linea[10:16]), fecha_valor=_aammdd(linea[16:22]), comun=linea[22:24],
                importe=_imp43(linea[28:42], linea[27]), referencia=(linea[52:64] + " " + linea[64:80]).strip(),
                concepto="", origen=origen))
        elif tipo == "23" and actual is not None and actual.movimientos:
            m = actual.movimientos[-1]
            m.concepto = re.sub(r"\s+", " ", f"{m.concepto} {linea[4:42]} {linea[42:80]}").strip()
        elif tipo == "33" and actual is not None:
            saldo = _imp43(linea[59:73], "2")
            actual.saldo_final = -saldo if linea[58] == "1" else saldo
    for e in extractos:
        for m in e.movimientos:
            m.concepto = m.concepto or CONCEPTO_COMUN.get(m.comun, "")
    return extractos


def _numero(s) -> Decimal | None:
    """«1.234,56», «-1234.56», «1,234.56» o un número de Excel → Decimal."""
    if s is None or s == "":
        return None
    if isinstance(s, (int, float, Decimal)):
        return D2(Decimal(str(s)))
    t = str(s).replace("€", "").replace("EUR", "").replace(" ", "").replace(" ", "").strip()
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return D2(Decimal(t))
    except InvalidOperation:
        return None


def _fecha(s) -> date | None:
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    t = str(s or "").strip()
    for patron, orden in ((r"(\d{4})-(\d{1,2})-(\d{1,2})", "amd"), (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", "dma"),
                          (r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})\b", "dma")):
        m = re.match(patron, t)
        if m:
            g = dict(zip(orden, m.groups()))
            a = int(g["a"]) + (2000 if len(g["a"]) == 2 else 0)
            try:
                return date(a, int(g["m"]), int(g["d"]))
            except ValueError:
                return None
    return None


def _sin_acentos(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").upper())
    return "".join(c for c in s if not unicodedata.combining(c))


def leer_tabla(filas: list[list], origen: str = "") -> Extracto:
    """Un CSV o un Excel de movimientos: busca la fila de títulos (fecha, concepto, importe o
    cargo/abono, saldo) en las 25 primeras y lee lo que hay debajo."""
    col = {}
    for i, fila in enumerate(filas[:25]):
        titulos = [_sin_acentos(x).strip() for x in fila]
        f = next((j for j, t in enumerate(titulos) if t.startswith("FECHA") and "VALOR" not in t), None)
        if f is None:
            continue
        busca = lambda *ps: next((j for j, t in enumerate(titulos) if any(t.startswith(p) or p in t for p in ps)), None)
        col = {"fecha": f, "concepto": busca("CONCEPTO", "DESCRIPCION", "DETALLE", "MOVIMIENTO"),
               "importe": busca("IMPORTE", "CANTIDAD"), "cargo": busca("CARGO", "DEBE"), "abono": busca("ABONO", "HABER"),
               "saldo": busca("SALDO"), "valor": busca("FECHA VALOR", "F. VALOR")}
        inicio = i + 1
        break
    if not col or (col["importe"] is None and col["cargo"] is None):
        raise ValueError(f"{origen}: no encuentro las columnas de fecha e importe (o cargo y abono)")
    e = Extracto(cuenta=Path(origen).stem, origen=origen)
    for fila in filas[inicio:]:
        celda = lambda k: fila[col[k]] if col.get(k) is not None and col[k] < len(fila) else None
        fecha = _fecha(celda("fecha"))
        if not fecha:
            continue
        if col["importe"] is not None:
            imp = _numero(celda("importe"))
        else:
            imp = (_numero(celda("abono")) or D2(0)) - abs(_numero(celda("cargo")) or D2(0))
        if imp is None:
            continue
        e.movimientos.append(Movimiento(fecha=fecha, importe=imp, concepto=str(celda("concepto") or "").strip(),
                                        fecha_valor=_fecha(celda("valor")), saldo=_numero(celda("saldo")), origen=origen))
    e.movimientos.sort(key=lambda m: m.fecha)
    if e.movimientos:
        e.desde, e.hasta = e.movimientos[0].fecha, e.movimientos[-1].fecha
        con_saldo = [m for m in e.movimientos if m.saldo is not None]
        if con_saldo:
            e.saldo_final = con_saldo[-1].saldo
    return e


def leer_fichero(f: Path) -> list[Extracto]:
    f = Path(f)
    crudo = f.read_bytes()
    if crudo[:2] == b"PK":                                    # Excel (xlsx)
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(crudo), read_only=True, data_only=True)
        return [leer_tabla([list(r) for r in wb.worksheets[0].iter_rows(values_only=True)], f.name)]
    texto = next((crudo.decode(c) for c in ("utf-8-sig", "latin-1") if _decodifica(crudo, c)), "")
    if re.match(r"11\d{4}", texto) and re.search(r"^88", texto, re.M):
        return leer_norma43(texto, f.name)
    return [leer_tabla(list(csv.reader(io.StringIO(texto), delimiter=_separador(texto))), f.name)]


def _separador(texto: str) -> str:
    """El que más líneas tienen (los bancos ponen títulos sueltos encima de la tabla)."""
    lineas = texto.splitlines()[:60]
    return max((";", "\t", ","), key=lambda c: sum(c in l for l in lineas))


def _decodifica(crudo: bytes, codificacion: str) -> bool:
    try:
        crudo.decode(codificacion)
        return True
    except UnicodeDecodeError:
        return False


def cargar(carpeta: Path) -> list[Extracto]:
    """Todos los extractos de `banco/`, sin repetir el mismo movimiento de dos ficheros."""
    d = Path(carpeta) / "banco"
    if not d.is_dir():
        return []
    extractos, vistos = [], set()
    for f in sorted(x for x in d.iterdir() if x.is_file() and not x.name.startswith(".")):
        for e in leer_fichero(f):
            unicos = []
            for m in e.movimientos:
                clave = (e.cuenta, m.fecha, m.importe, m.concepto[:40])
                if clave not in vistos:
                    vistos.add(clave)
                    unicos.append(m)
            e.movimientos = unicos
            extractos.append(e)
    return extractos


# ─── bajarlos con las cookies de tu sesión ──────────────────────────────────────────────────

def cargar_cookies(fichero: Path) -> list[dict]:
    """El cookies.txt de un navegador (formato Netscape) o el JSON de una extensión."""
    f = Path(fichero).expanduser()
    if f.stat().st_mode & 0o077:
        raise PermissionError(f"{f} lo pueden leer otros usuarios: `chmod 600 {f}` (son las llaves de tu banco)")
    t = f.read_text(encoding="utf-8", errors="ignore").strip()
    if t.startswith("["):
        return [{"name": c["name"], "value": c["value"], "domain": c.get("domain", ""), "path": c.get("path", "/")}
                for c in json.loads(t)]
    out = []
    for linea in t.splitlines():
        if linea.startswith("#HttpOnly_"):
            linea = linea[len("#HttpOnly_"):]
        elif not linea.strip() or linea.startswith("#"):
            continue
        p = linea.split("\t")
        if len(p) >= 7:
            out.append({"domain": p[0], "path": p[2], "name": p[5], "value": p[6]})
    return out


def cabecera_cookies(cookies: list[dict], url: str) -> str:
    host = urlparse(url).hostname or ""
    vale = lambda d: host == d.lstrip(".") or host.endswith("." + d.lstrip("."))
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies if vale(c["domain"]))


def _tipo(datos: bytes) -> str:
    if datos[:2] == b"PK":
        return "xlsx"
    t = datos[:3000].decode("latin-1", "ignore")
    if re.match(r"11\d{4}", t):
        return "n43"
    if re.search(r"<html|<!doctype", t, re.I):
        return "html"
    return "csv"


def descargar(pf, carpeta: Path, desde: date | None = None, hasta: date | None = None) -> Path:
    """Baja el extracto de `[banco] url_descarga` con las cookies de tu sesión y lo deja en
    `banco/`. En la dirección se pueden poner {desde} y {hasta} (AAAA-MM-DD) o {desde_es} y
    {hasta_es} (DD/MM/AAAA). Es un GET: lee, no puede ordenar nada."""
    b = pf.banco
    if not (b.get("url_descarga") and b.get("cookies")):
        raise ValueError("pon en perfil.toml [banco] cookies = \"~/.config/gestoria/banco_cookies.txt\" (exportadas de tu "
                         "sesión, permisos 600) y url_descarga = \"la dirección del botón de descargar el extracto\"")
    hasta = hasta or date.today()
    desde = desde or hasta - timedelta(days=90)
    url = b["url_descarga"].format(desde=desde.isoformat(), hasta=hasta.isoformat(),
                                   desde_es=desde.strftime("%d/%m/%Y"), hasta_es=hasta.strftime("%d/%m/%Y"))
    from gestoria.navegador import AGENTE

    req = urllib.request.Request(url, headers={"Cookie": cabecera_cookies(cargar_cookies(b["cookies"]), url),
                                               "User-Agent": AGENTE, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        datos = r.read()
    tipo = _tipo(datos)
    if tipo == "html":
        raise ValueError("el banco ha devuelto una página web y no un extracto: la sesión ha caducado (exporta otra vez "
                         "las cookies) o url_descarga no es la del botón de descargar")
    destino = Path(carpeta) / "banco" / f"extracto_{desde:%Y%m%d}_{hasta:%Y%m%d}.{tipo}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(datos)
    return destino


# ─── conciliar ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Conciliacion:
    casados: list[tuple] = field(default_factory=list)            # (movimiento, factura)
    explicados: list[tuple] = field(default_factory=list)         # (movimiento, categoría, nota)
    cobros_sin_factura: list[Movimiento] = field(default_factory=list)
    pagos_sin_factura: list[Movimiento] = field(default_factory=list)
    sin_cobrar: list = field(default_factory=list)                # ventas
    sin_pagar: list = field(default_factory=list)                 # compras
    saldo: Decimal | None = None
    fecha_saldo: date | None = None
    descuadres: list[str] = field(default_factory=list)


def _cobro(v) -> Decimal:
    total = v.total if v.total is not None else (v.base or 0) + (v.cuota or 0)
    return D2(total - (v.retencion or 0))


def _pago(c) -> Decimal:
    return D2(c.base + (c.cuota or 0))


def _norm(s: str) -> str:
    from gestoria.terceros import _norm as norm
    return norm(s)


def _parecido(nombre: str, concepto: str) -> bool:
    c = _norm(concepto)
    return any(len(p) >= 4 and p in c for p in _norm(nombre).split())


def _mejor(m: Movimiento, candidatas: list, importe_de, nombre_de):
    """La factura del mismo importe, dentro de la ventana, más cercana en fecha (mejor si el nombre
    sale en el concepto)."""
    hay = [x for x in candidatas if abs(importe_de(x) - abs(m.importe)) <= Decimal("0.01")
           and x.fecha - VENTANA[0] <= m.fecha <= x.fecha + VENTANA[1]]
    if not hay:
        return None
    return min(hay, key=lambda x: (not _parecido(nombre_de(x), m.concepto), abs((m.fecha - x.fecha).days)))


def _categoria(m: Movimiento) -> str | None:
    c = _sin_acentos(m.concepto)
    for nombre, patron in CATEGORIAS:
        if re.search(patron, c):
            return nombre
    return {"17": "comisiones e intereses del banco", "15": "nóminas", "05": "préstamo"}.get(m.comun)


def conciliar(extractos: list[Extracto], ventas, compras, hoy: date | None = None) -> Conciliacion:
    from gestoria.libros import Venta
    from gestoria.modelos import m303

    hoy = hoy or date.today()
    r = Conciliacion()
    movs = sorted((m for e in extractos for m in e.movimientos), key=lambda m: m.fecha)
    if not movs:
        return r
    desde = min(m.fecha for m in movs)
    for e in extractos:
        if e.cuadra is False:
            r.descuadres.append(f"{e.origen}: el saldo inicial más los movimientos no da el saldo final")
    finales = [(e.hasta, e.saldo_final) for e in extractos if e.saldo_final is not None and e.hasta]
    if finales:
        r.fecha_saldo, r.saldo = max(finales, key=lambda x: x[0])
    libres_v = [v for v in ventas if v.fecha >= desde - VENTANA[1]]
    libres_c = [c for c in compras if c.fecha >= desde - VENTANA[1]]
    resultados_303 = {}
    for m in movs:
        # entra dinero: una factura emitida o el abono de un proveedor; sale: una recibida o una rectificativa tuya
        entra = m.importe > 0
        candidatas = [x for x in libres_v if _cobro(x) and (_cobro(x) > 0) == entra] + \
                     [x for x in libres_c if _pago(x) and (_pago(x) > 0) != entra]
        f = _mejor(m, candidatas, lambda x: abs(_cobro(x) if isinstance(x, Venta) else _pago(x)),
                   lambda x: x.cliente if isinstance(x, Venta) else x.proveedor)
        if f is not None:
            r.casados.append((m, f))
            (libres_v if isinstance(f, Venta) else libres_c).remove(f)
            continue
        cat = _categoria(m)
        if cat is None:
            (r.cobros_sin_factura if m.importe > 0 else r.pagos_sin_factura).append(m)
            continue
        nota = ""
        if cat == "Hacienda" and m.importe < 0:
            ej, per = m.fecha.year, f"{(m.fecha.month - 1) // 3}T"
            if per == "0T":
                ej, per = ej - 1, "4T"
            if (ej, per) not in resultados_303:
                d, h = m303.periodo_fechas(ej, per)
                resultados_303[(ej, per)] = m303.casillas(ventas, compras, d, h, D2(0))[0].get("71", D2(0))
            r303 = resultados_303[(ej, per)]
            nota = (f"cuadra con el 303 del {per} {ej} de tus libros" if r303 == -m.importe else
                    f"el 303 del {per} {ej} de tus libros sale {eur(r303)}: ¿qué se presentó? (`gestoria cotejar 303`)")
        r.explicados.append((m, cat, nota))
    hasta = max(m.fecha for m in movs)
    r.sin_cobrar = [v for v in libres_v if desde <= v.fecha <= hasta and _cobro(v) > 0]
    r.sin_pagar = [c for c in libres_c if desde <= c.fecha <= hasta]
    return r


def hallazgos(r: Conciliacion, hoy: date) -> list[str]:
    out = [f"🟡 {d}" for d in r.descuadres]
    for m in r.cobros_sin_factura:
        out.append(f"🟡 entra {eur(m.importe)} el {m.fecha:%d-%m-%Y} «{m.concepto[:50]}» y no hay factura emitida por ese "
                   "importe: si es una venta, hay que facturarla (art. 2 RD 1619/2012); si es un préstamo o una "
                   "aportación del socio, que quede documentado")
    for m in r.pagos_sin_factura:
        out.append(f"🟡 sale {eur(-m.importe)} el {m.fecha:%d-%m-%Y} «{m.concepto[:50]}» y no hay factura recibida por ese "
                   "importe: pídela, sin ella no deduces su IVA (art. 97 LIVA) y el gasto queda sin justificar (art. 106.4 LGT)")
    for v in r.sin_cobrar:
        dias = (hoy - v.fecha).days
        out.append(f"{'🟡' if dias > 60 else 'ℹ️'} la factura {v.factura} a {v.cliente} ({eur(_cobro(v))}, {v.fecha:%d-%m-%Y}) "
                   f"no aparece cobrada ({dias} días)")
    for c in r.sin_pagar:
        out.append(f"ℹ️ la factura {c.factura} de {c.proveedor} ({eur(_pago(c))}, {c.fecha:%d-%m-%Y}) no aparece pagada")
    return out


def texto(r: Conciliacion, hoy: date, hucha: Decimal | None = None) -> str:
    n = len(r.casados) + len(r.explicados) + len(r.cobros_sin_factura) + len(r.pagos_sin_factura)
    l = [f"🏦 Banco: {n} movimientos · {len(r.casados)} casados con una factura · {len(r.explicados)} sin factura que no la "
         f"necesitan · {len(r.cobros_sin_factura) + len(r.pagos_sin_factura)} por explicar"]
    if r.saldo is not None:
        l.append(f"   saldo {eur(r.saldo)} el {r.fecha_saldo:%d-%m-%Y}" + (
            "" if hucha is None else f" · la hucha pide {eur(hucha)} → " +
            (f"te sobran {eur(r.saldo - hucha)}" if r.saldo >= hucha else f"TE FALTAN {eur(hucha - r.saldo)}")))
    l.append("")
    for m, f in r.casados:
        quien = f.cliente if hasattr(f, "cliente") else f.proveedor
        l.append(f"   ✅ {m.fecha:%d-%m} {eur(m.importe):>12}  {f.factura} · {quien}")
    for m, cat, nota in r.explicados:
        l.append(f"   ·  {m.fecha:%d-%m} {eur(m.importe):>12}  {cat}" + (f": {nota}" if nota else ""))
    h = hallazgos(r, hoy)
    if h:
        l.append("")
        l += [f"   {x}" for x in h]
    return "\n".join(l)


def resumen(carpeta: Path, ventas, compras, hoy: date) -> dict | None:
    """Para el panel: saldo del último extracto y cuántos movimientos quedan por explicar."""
    try:
        extractos = cargar(carpeta)
    except Exception as e:  # un fichero ilegible no tumba el panel
        return {"error": f"{type(e).__name__}: {e}"}
    if not extractos:
        return None
    r = conciliar(extractos, ventas, compras, hoy)
    return {"saldo": r.saldo, "fecha": r.fecha_saldo, "por_explicar": len(r.cobros_sin_factura) + len(r.pagos_sin_factura),
            "casados": len(r.casados)}
