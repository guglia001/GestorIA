"""Presentar declaraciones en la sede de la AEAT, después de revisarlo todo.

GestorIA presenta siempre así, y en este orden:

1. **La revisión** (`revisar`). Comprueba que el período ha terminado y que los libros no tienen
   errores, y revisa el borrador con cada uno de sus avisos. Lee en el momento los manuales
   prácticos de la AEAT y los artículos del BOE de lo que aplica ese trimestre (REBU,
   adquisiciones intracomunitarias, rectificativas, bienes de inversión). Cuadra el saldo a
   compensar con el 303 anterior PRESENTADO. En la sede mira que estás de alta en el modelo, que el
   período no está ya presentado y si tienes notificaciones sin abrir. Calcula el plazo y, si llega
   tarde, el recargo. Pasa el fichero por el simulador de la AEAT, que no debe dar errores y debe
   salir con las mismas casillas. Y comprueba cómo se paga o se devuelve. Un solo ⛔ lo para todo.
2. **El ensayo** (`--pruebas`). Es la presentación entera en el entorno de pruebas de la AEAT
   (prewww1/prewww2.aeat.es), hasta el justificante. Lo que se presenta ahí «no tiene en ningún
   caso trascendencia tributaria» (https://preportal.aeat.es). Si ESE fichero no ha tenido un
   ensayo bueno, no se presenta de verdad.
3. **Tu conformidad**. Es la frase exacta, con el modelo, el período, el NIF y el resultado
   («PRESENTAR 303 3T 2026 B00000000 67,60»), y vale como tu orden para esa declaración y para
   ninguna otra. Si cambia una casilla, cambia la frase.
4. **La presentación**: ventana censal → «Importar» → «Errores y avisos» limpio → «Firmar y Enviar»
   → «Conforme» → «Firmar y Enviar» → «Su presentación ha sido realizada con éxito». Es el diálogo
   de firma de la AEAT, con el certificado con el que entras (no hace falta AutoFirma). El
   justificante, con su CSV, queda en salida/presentado/.
5. **El cotejo**: lo presentado se baja de la sede y se compara con los libros, casilla a casilla.

Si algo no sale como se espera a mitad, GestorIA se para, deja la captura y no reintenta. Antes de
volver a probar hay que mirar `gestoria presentados`, porque dos presentaciones del mismo período
no se arreglan presentando una tercera.

Las pantallas de la ventana censal y del diálogo de firma están tomadas de la ayuda de la AEAT y
de una presentación real del 036 con el mismo diálogo («Firmar y Enviar» → «Conforme» → «Firmar y
Enviar», 16-oct-2026). Lo que no coincida lo enseña el ensayo, que para eso existe.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

from gestoria import D2, plazos
from gestoria.numeros import eur

MODELOS = ("303",)    # los que GestorIA genera, revisa y presenta; los demás, cuando genere su fichero
VENTANA = {"303": "/wlpl/TOAE-JDIT/VentanaCensalIva?fOrigen=pre303"}   # ficha G414 de la sede (21-oct-2026)
SERVIDOR = {False: "https://www1.agenciatributaria.gob.es", True: "https://prewww1.aeat.es"}
HOSTS = {False: ("www1.agenciatributaria.gob.es", "www2.agenciatributaria.gob.es", "www12.agenciatributaria.gob.es",
                 "sede.agenciatributaria.gob.es"),
         True: ("prewww1.aeat.es", "prewww2.aeat.es")}
EXITO = "realizada con éxito"
LIVA = "BOE-A-1992-28740"
DIAS_ENSAYO = 7       # un ensayo vale para presentar ese mismo fichero durante una semana
TIPOS = {"I": "a ingresar, con NRC", "U": "a ingresar, domiciliado", "G": "a ingresar en la cuenta corriente tributaria",
         "C": "a compensar", "D": "a devolver", "N": "sin actividad o resultado cero"}
# lo que se investiga en el Manual práctico de IVA y en la Ley del IVA según lo que lleve el período
INVESTIGAR = {
    "rebu": ("régimen especial de los bienes usados", ("135", "136", "137")),
    "margen_negativo": ("margen de beneficio negativo", ("137",)),
    "intracomunitaria": ("adquisiciones intracomunitarias", ("13", "84")),
    "rectificativa": ("modificación de la base imponible", ("80",)),
    "inversion": ("bienes de inversión", ("108",)),
}


@dataclass
class Paso:
    nivel: str        # ✅ bien · ⚠️ míralo · ⛔ no se presenta
    que: str
    detalle: str
    fuente: str = ""

    def __str__(self) -> str:
        return f"{self.nivel} {self.que}: {self.detalle}" + (f" ({self.fuente})" if self.fuente else "")


@dataclass
class Revision:
    modelo: str
    ejercicio: int
    periodo: str
    nif: str
    pasos: list[Paso] = field(default_factory=list)
    casillas: dict = field(default_factory=dict)
    fichero: str = ""
    huella: str = ""          # sha256 del fichero: el ensayo y la presentación son del MISMO fichero
    tipo: str = ""            # tipo de declaración del fichero (nota 1 del diseño de registro)
    resultado: Decimal = field(default_factory=lambda: D2(0))

    @property
    def bloqueada(self) -> bool:
        return any(p.nivel == "⛔" for p in self.pasos)

    @property
    def nivel(self) -> str:
        return "⛔" if self.bloqueada else "⚠️" if any(p.nivel == "⚠️" for p in self.pasos) else "✅"

    @property
    def frase(self) -> str:
        return frase(self.modelo, self.periodo, self.ejercicio, self.nif, self.resultado)


class Parada(RuntimeError):
    """La presentación se ha parado en un paso (antes de enviar nada)."""

    def __init__(self, paso: str, motivo: str):
        super().__init__(motivo)
        self.paso = paso


def frase(modelo: str, periodo: str, ejercicio: int, nif: str, resultado: Decimal) -> str:
    return f"PRESENTAR {modelo} {periodo} {ejercicio} {nif} {eur(resultado).replace(' €', '')}"


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("latin-1")).hexdigest()


# ─── la revisión ────────────────────────────────────────────────────────────────────────────

def revisar(carpeta: Path, modelo: str, ejercicio: int, periodo: str, hoy: date | None = None,
            nrc: str | None = None, sede: bool = True, simulador: bool = True, investigar: bool = True,
            para: str = "revisar") -> Revision:
    """Todo lo que se mira antes de presentar. `para`: «revisar», «ensayo» o «presentar» (solo
    la presentación de verdad exige el ensayo)."""
    from gestoria import libros, perfil as perfilmod, revisar as libros_revisar
    from gestoria.modelos import m303

    hoy = hoy or date.today()
    carpeta = Path(carpeta)
    pf = perfilmod.cargar(carpeta)
    r = Revision(modelo, ejercicio, periodo, pf.nif)
    paso = r.pasos.append
    if modelo not in MODELOS:
        paso(Paso("⛔", "modelo", f"GestorIA todavía no genera el {modelo}: hoy presenta el {', '.join(MODELOS)}"))
        return r
    desde, hasta = m303.periodo_fechas(ejercicio, periodo)
    if hoy < hasta:
        paso(Paso("⛔", "período", f"el {periodo} {ejercicio} no ha terminado: se presenta desde el {hasta.strftime('%d-%m-%Y')}"))
    else:
        paso(Paso("✅", "período", f"el {periodo} {ejercicio} está cerrado"))
    if modelo not in pf.modelos:
        paso(Paso("⚠️", "perfil", f"perfil.toml no lista el {modelo} en [obligaciones] modelos (lo confirma el censo)"))

    ventas, compras = libros.cargar(carpeta)
    aj = libros.ajustes(carpeta)
    hallazgos = libros_revisar.revisar(ventas, compras, hoy)
    errores = [h for h in hallazgos if h.nivel == "error"]
    avisos_libros = [h for h in hallazgos if h.nivel == "aviso"]
    for h in errores:
        paso(Paso("⛔", "libros", str(h)))
    if not errores:
        paso(Paso("✅", "libros", f"{len(ventas)} facturas emitidas y {len(compras)} recibidas, sin errores"
                  + (f" ({len(avisos_libros)} aviso(s), abajo)" if avisos_libros else "")))

    compensar = D2(aj.get("compensar_pendiente", "0"))
    cas, avisos = m303.casillas(ventas, compras, desde, hasta, compensar)
    r.casillas = {k: str(v) for k, v in cas.items()}
    r.resultado = cas.get("71", D2(0))
    hay = any(v for k, v in cas.items() if k != "65")
    r.tipo = m303.tipo_declaracion(r.resultado, periodo, pf.forma_pago, hay)
    salida = carpeta / "salida" / "presentado"
    salida.mkdir(parents=True, exist_ok=True)
    texto = m303.generar_fichero(pf, ejercicio, periodo, cas)
    f = salida / f"{modelo}_{ejercicio}_{periodo}_a_presentar.txt"
    f.write_text(texto, encoding="latin-1")
    r.fichero, r.huella = str(f), _huella(texto)
    paso(Paso("✅", "borrador", f"[71] = {eur(r.resultado)}, {TIPOS.get(r.tipo, r.tipo)}; fichero para «Importar»: {f.name}"))
    for a in avisos:
        paso(Paso("⚠️", "borrador", a))

    if investigar:
        _investigar(r, ventas, compras, desde, hasta, avisos)
    if sede:
        _sede(r, pf, carpeta, compensar)
    else:
        paso(Paso("⚠️", "sede", "sin mirar la sede: ni si ya está presentado ni si cuadra el saldo a compensar"))
    _plazo(r, hoy)
    _pago(r, pf, hoy, nrc)
    if simulador:
        _simulador(r, carpeta)
    if para == "presentar" and not (sede and simulador):
        paso(Paso("⛔", "revisión", "para presentar de verdad hay que mirar la sede y pasar el simulador (sin --sin-sede ni --sin-simulador)"))
    if para == "presentar":
        e = ensayo(carpeta, r, hoy)
        paso(Paso("✅", "ensayo", f"ensayado en el entorno de pruebas de la AEAT el {e['fecha'][:10]} (CSV de pruebas {e.get('csv') or '—'})")
             if e else
             Paso("⛔", "ensayo", "falta el ensayo de este fichero en el entorno de pruebas de la AEAT: "
                  f"`gestoria presentar {modelo} --ejercicio {ejercicio} --periodo {periodo} --pruebas --conforme \"{r.frase}\"`"))
    return r


def _investigar(r: Revision, ventas, compras, desde: date, hasta: date, avisos: list[str]) -> None:
    """El Manual práctico de IVA de la AEAT y la Ley del IVA (BOE consolidado), leídos ahora, para
    cada cosa especial que lleve el período."""
    from gestoria import boe, manuales

    v = [x for x in ventas if desde <= x.fecha < hasta]
    c = [x for x in compras if desde <= x.fecha < hasta]
    temas = [t for t, si in (("rebu", any(x.regimen == "rebu" for x in v)),
                             ("margen_negativo", any("margen REBU" in a for a in avisos)),
                             ("intracomunitaria", any(x.origen == "intracomunitaria" for x in c)),
                             ("rectificativa", any(x.rectifica for x in v)),
                             ("inversion", any(x.gasto == "inversion" for x in c))) if si]
    if not temas:
        r.pasos.append(Paso("✅", "investigación", "solo régimen general: nada especial que leer"))
        return
    try:
        manuales.al_dia("iva")
    except Exception as e:
        r.pasos.append(Paso("⚠️", "investigación", f"no he podido leer el Manual práctico de IVA: {type(e).__name__}"))
    ley = None
    try:
        import urllib.request
        req = urllib.request.Request(boe.url(LIVA), headers={"User-Agent": "Mozilla/5.0 gestoria"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            ley = resp.read().decode("utf-8", "ignore")
    except Exception as e:
        r.pasos.append(Paso("⚠️", "investigación", f"no he podido leer la Ley del IVA en el BOE: {type(e).__name__}"))
    titulo = manuales.MANUALES["iva"]["titulo"]
    for t in temas:
        consulta, articulos = INVESTIGAR[t]
        hits = manuales.buscar(consulta, ["iva"], maximo=1)
        leidos = [a for a in articulos if ley and boe.extraer(ley, a)]
        donde = f"{titulo}, pág. {hits[0]['pagina']}" if hits else f"nada en el {titulo}"
        arts = (f"art{'s' if len(leidos) > 1 else ''}. {_lista(leidos)} LIVA, vigente{'s' if len(leidos) > 1 else ''} en el BOE"
                if leidos else "sin leer la ley")
        r.pasos.append(Paso("✅" if hits and len(leidos) == len(articulos) else "⚠️", "investigación",
                            f"{consulta}: {donde} · {arts}"))


def _lista(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def _sede(r: Revision, pf, carpeta: Path, compensar: Decimal) -> None:
    """Censo, si ya está presentado, notificaciones y el 303 anterior presentado (para la [110])."""
    from gestoria import aeat, cotejo
    from gestoria.chequeo import error_corto
    from gestoria.navegador import Navegador

    paso = r.pasos.append
    if not pf.tiene_certificado():
        paso(Paso("⛔", "sede", "sin certificado ([sede] en perfil.toml) no se puede presentar"))
        return
    ej_prev, per_prev = plazos.trimestre_anterior(r.ejercicio, r.periodo)
    try:
        with Navegador(pf.ruta_certificado(), pf.clave_certificado(), capturas=carpeta / "salida" / "capturas",
                       sitios=("aeat",)) as nav:
            d = aeat.consultar(nav, ("notificaciones", "obligaciones", "presentados"), modelos=(r.modelo,))
            previo = aeat.descargar_presentado(nav, r.modelo, ej_prev, per_prev, carpeta / "salida" / "presentado")
    except Exception as e:
        paso(Paso("⛔", "sede", f"no he podido leer la sede: {error_corto(e)}"))
        return
    for parte, err in (d.get("errores") or {}).items():
        paso(Paso("⚠️", "sede", f"no he podido leer «{parte}»: {err}"))
    if d.get("obligaciones") is not None:
        de_alta = r.modelo in aeat.modelos_de_obligaciones(d["obligaciones"])
        paso(Paso("✅" if de_alta else "⛔", "censo", f"{'de alta' if de_alta else 'NO consta de alta'} en el {r.modelo}",
                  "Mis obligaciones, sede de la AEAT"))
    ya = [x for x in (d.get("presentados") or {}).get(r.modelo, [])
          if x["ejercicio"] == str(r.ejercicio) and x["periodo"] == r.periodo and x["estado"] != "BAJA"]
    if ya:
        paso(Paso("⛔", "sede", f"el {r.modelo} del {r.periodo} {r.ejercicio} YA está presentado (expediente "
                  f"{ya[-1]['expediente']}, {ya[-1]['presentada']}): cambiarlo es una autoliquidación rectificativa, "
                  "que GestorIA no hace; compáralo con `gestoria cotejar`"))
    elif "presentados" in d:
        paso(Paso("✅", "sede", f"el {r.periodo} {r.ejercicio} no está presentado todavía"))
    if d.get("no_leidas"):
        paso(Paso("⚠️", "notificaciones", "hay notificaciones de la AEAT sin abrir: mira de qué son antes de presentar "
                  "(`gestoria notificaciones`; abrirlas arranca los plazos)"))
    if previo.get("encontrado"):
        pres = cotejo.leer_presentado(Path(previo["fichero"]))
        deberia = cotejo.compensar_siguiente(pres, per_prev)
        paso(Paso("✅" if deberia == compensar else "⛔", "compensación",
                  f"[110] = {eur(compensar)}; el 303 del {per_prev} {ej_prev} presentado deja {eur(deberia)} "
                  "por compensar ([87] más lo que salió a compensar)" + ("" if deberia == compensar else
                                                                          ": corrige compensar_pendiente en ajustes.toml"),
                  "art. 99.Cinco LIVA"))
    else:
        paso(Paso("✅" if compensar == 0 else "⚠️", "compensación",
                  f"no consta 303 del {per_prev} {ej_prev} presentado; [110] = {eur(compensar)}"))


def _plazo(r: Revision, hoy: date) -> None:
    from gestoria import recargos

    vence = plazos.vence(r.modelo, r.ejercicio, r.periodo)
    if hoy <= vence:
        r.pasos.append(Paso("✅", "plazo", f"vence el {vence.strftime('%d-%m-%Y')}: quedan {(vence - hoy).days} días"))
        return
    rc = recargos.calcular(max(r.resultado, D2(0)), vence, hoy)
    r.pasos.append(Paso("⚠️", "plazo", f"FUERA DE PLAZO desde el {vence.strftime('%d-%m-%Y')}: recargo {eur(rc.recargo)} "
                        f"({rc.porcentaje} %), {eur(rc.recargo_reducido)} si se paga todo a la vez; sin requerimiento previo "
                        "no hay sanción", "art. 27 LGT"))


def _pago(r: Revision, pf, hoy: date, nrc: str | None) -> None:
    paso = r.pasos.append
    cuenta = f"…{pf.iban[-4:]}" if pf.iban else ""
    if r.tipo == "U":
        fin = plazos.vence(r.modelo, r.ejercicio, r.periodo) - timedelta(days=5)
        if not pf.iban:
            paso(Paso("⛔", "pago", "domiciliación sin cuenta: pon [pago] iban en perfil.toml"))
        elif hoy > fin:
            paso(Paso("⛔", "pago", f"ya no se puede domiciliar (hasta el {fin.strftime('%d-%m-%Y')}): paga en tu banco y "
                      "presenta con el NRC (`--nrc`, y [iva] forma_pago = \"I\")",
                      "calendario del contribuyente de la AEAT; Orden EHA/1658/2009"))
        else:
            paso(Paso("✅", "pago", f"domiciliado en la cuenta {cuenta}: la AEAT carga {eur(r.resultado)} el último día del plazo "
                      f"(se puede domiciliar hasta el {fin.strftime('%d-%m-%Y')})",
                      "calendario del contribuyente de la AEAT; Orden EHA/1658/2009"))
    elif r.tipo == "I":
        if not nrc:
            paso(Paso("⛔", "pago", f"sale a ingresar {eur(r.resultado)} sin domiciliar: paga antes en tu banco (o con cargo en "
                      "cuenta en la sede) y dame el NRC con `--nrc`, o domicilia ([iva] forma_pago = \"U\" y [pago] iban)"))
        elif not re.fullmatch(r"[0-9A-Z]{22}", nrc.strip().upper()):
            paso(Paso("⛔", "pago", "el NRC son 22 letras y números: revísalo en el justificante del banco"))
        else:
            paso(Paso("✅", "pago", f"ingreso con el NRC …{nrc.strip()[-4:]}"))
    elif r.tipo == "D":
        paso(Paso("✅", "pago", f"a devolver {eur(-r.resultado)} en la cuenta {cuenta}") if pf.iban else
             Paso("⛔", "pago", "a devolver sin cuenta: pon [pago] iban en perfil.toml"))
    elif r.tipo == "G":
        paso(Paso("⚠️", "pago", "cuenta corriente tributaria: compruébala en la sede antes de presentar"))
    else:
        paso(Paso("✅", "pago", TIPOS.get(r.tipo, r.tipo) + ("" if r.tipo == "N" else f": {eur(-r.resultado)} para el trimestre siguiente")))


def _simulador(r: Revision, carpeta: Path) -> None:
    from gestoria import sede

    try:
        v = sede.validar(r.modelo, r.ejercicio, Path(r.fichero), carpeta / "salida" / "capturas")
    except Exception as e:
        r.pasos.append(Paso("⛔", "simulador", f"no he podido pasarlo por el simulador de la AEAT: {type(e).__name__}: "
                            f"{(str(e).splitlines() or [''])[0][:120]}"))
        return
    for e in v["errores"]:
        r.pasos.append(Paso("⛔", "simulador", e, "simulador del 303 de la AEAT"))
    for w in v["avisos"]:
        r.pasos.append(Paso("⚠️", "simulador", w, "simulador del 303 de la AEAT"))
    if v["errores"]:
        return
    cas = v.get("casillas_aeat") or {}
    distintas = [k for k, x in cas.items() if k in r.casillas and D2(r.casillas[k]) != x]
    if distintas:
        r.pasos.append(Paso("⛔", "simulador", "el formulario de la AEAT recalcula distinto: " + ", ".join(
            f"[{k}] {eur(cas[k])} frente a {eur(D2(r.casillas[k]))}" for k in distintas)))
    else:
        r.pasos.append(Paso("✅", "simulador", "«No existen errores»" + (f"; el formulario de la AEAT recalcula [71] = {eur(cas['71'])}"
                                                                        if "71" in cas else ""), "simulador del 303 de la AEAT"))


# ─── el ensayo y la presentación ────────────────────────────────────────────────────────────

def _registro(carpeta: Path) -> Path:
    return Path(carpeta) / "salida" / "presentado" / "presentaciones.json"


def _historial(carpeta: Path) -> list[dict]:
    f = _registro(carpeta)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []


def ensayo(carpeta: Path, r: Revision, hoy: date | None = None) -> dict | None:
    """El último ensayo bueno de ESTE fichero (misma huella) en los últimos DIAS_ENSAYO días."""
    hoy = hoy or date.today()
    for e in reversed(_historial(carpeta)):
        if (e.get("pruebas") and e.get("estado") == "ensayada" and e.get("huella") == r.huella
                and (hoy - date.fromisoformat(e["fecha"][:10])).days <= DIAS_ENSAYO):
            return e
    return None


def presentar(carpeta: Path, modelo: str, ejercicio: int, periodo: str, conforme: str, pruebas: bool = False,
              nrc: str | None = None, hoy: date | None = None, sede: bool = True, simulador: bool = True,
              investigar: bool = True) -> dict:
    """Revisa y, si todo está en orden y `conforme` es la frase exacta, presenta (o ensaya, con
    `pruebas`). Devuelve {"estado": "bloqueada" | "sin_conformidad" | "parada" | "desconocido" |
    "ensayada" | "presentada", "revision": Revision, …}."""
    from gestoria import perfil as perfilmod
    from gestoria.navegador import Navegador

    carpeta = Path(carpeta)
    r = revisar(carpeta, modelo, ejercicio, periodo, hoy, nrc, sede, simulador, investigar,
                para="ensayo" if pruebas else "presentar")
    if r.bloqueada:
        return {"estado": "bloqueada", "revision": r}
    if (conforme or "").strip() != r.frase:
        return {"estado": "sin_conformidad", "revision": r}
    pf = perfilmod.cargar(carpeta)
    capturas = carpeta / "salida" / "capturas"
    out: dict = {"modelo": modelo, "ejercicio": ejercicio, "periodo": periodo, "nif": r.nif, "resultado": str(r.resultado),
                 "tipo": r.tipo, "huella": r.huella, "pruebas": pruebas, "fecha": datetime.now().isoformat(timespec="seconds")}
    with Navegador(pf.ruta_certificado(), pf.clave_certificado(), capturas=capturas,
                   sitios=("aeat_pruebas",) if pruebas else ("aeat",), presentar=True) as nav:
        estado = {"enviado": False}
        try:
            out.update(_enviar(nav, r, pruebas, nrc, carpeta, estado))
            out["estado"] = "ensayada" if pruebas else "presentada"
            if not pruebas:
                out["cotejo"] = _cotejar(nav, r, carpeta)
        except Parada as e:
            out.update(estado="parada", paso=e.paso, motivo=str(e))
        except Exception as e:
            out.update(estado="desconocido" if estado["enviado"] else "parada", paso=estado.get("paso", ""),
                       motivo=f"{type(e).__name__}: {(str(e).splitlines() or [''])[0][:200]}")
    historial = _historial(carpeta) + [out]
    _registro(carpeta).write_text(json.dumps(historial, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    out["revision"] = r
    return out


def _en_su_sitio(pg, pruebas: bool) -> None:
    host = re.match(r"https?://([^/]+)", pg.url or "")
    if not host or host.group(1) not in HOSTS[pruebas]:
        raise Parada("servidor", f"la página ha salido de {'las pruebas' if pruebas else 'la sede'}: {pg.url[:80]}")


def _visible(pg, nombre: str, rol: str = "button"):
    loc = pg.get_by_role(rol, name=nombre)
    if not loc.count():
        loc = pg.get_by_text(nombre, exact=True)
    return [x for x in loc.all() if x.is_visible()]


def _rellenar_ventana(pg, r: Revision) -> None:
    """Datos identificativos de la ventana censal: NIF, ejercicio y período (21-oct-2026, pruebas)."""
    selects = [s for s in pg.locator("select").all() if s.is_visible()]
    ejercicio = next((s for s in selects if str(r.ejercicio) in s.inner_text()), None)
    if ejercicio is None:
        raise Parada("ventana censal", "no encuentro dónde elegir el ejercicio")
    ejercicio.select_option(str(r.ejercicio))
    pg.wait_for_timeout(1500)
    selects = [s for s in pg.locator("select").all() if s.is_visible()]
    periodo = next((s for s in selects if re.search(rf"\b{r.periodo}\b", s.inner_text())), None)
    if periodo is None:
        raise Parada("ventana censal", "no encuentro dónde elegir el período")
    periodo.select_option(r.periodo)
    nif = pg.get_by_label(re.compile(r"N\.?\s?I\.?\s?F", re.I))
    nif = nif.first if nif.count() else next((i for i in pg.locator("form input[type=text], form input:not([type])").all()
                                              if i.is_visible()), None)
    if nif is None:
        raise Parada("ventana censal", "no encuentro el campo del NIF")
    if (nif.input_value() or "").strip().upper() != r.nif:
        nif.fill(r.nif)


def _hasta_el_formulario(nav, pg, pruebas: bool):
    from gestoria.navegador import PRESENTAR_NAVEGAR

    for _ in range(4):
        _en_su_sitio(pg, pruebas)
        if _visible(pg, "Importar"):
            return pg
        candidatos = [x for x in pg.locator("button, a, input[type=button], input[type=submit]").all()
                      if x.is_visible() and PRESENTAR_NAVEGAR.fullmatch(((x.inner_text() or x.get_attribute("value") or "").strip()))]
        if not candidatos:
            raise Parada("ventana censal", "no reconozco esta pantalla y no sigo: " +
                         re.sub(r"\s+", " ", pg.inner_text("body"))[:300])
        nombre = (candidatos[0].inner_text() or candidatos[0].get_attribute("value") or "").strip()
        pg = nav.pulsar_para_presentar(pg, nombre, rol="link" if candidatos[0].evaluate("e => e.tagName") == "A" else "button")
    raise Parada("ventana censal", "no llego al formulario del modelo")


def _enviar(nav, r: Revision, pruebas: bool, nrc: str | None, carpeta: Path, estado: dict) -> dict:
    from gestoria import sede

    def foto(etiqueta: str) -> None:
        nav.captura(pg, f"presentar_{'pruebas_' if pruebas else ''}{r.modelo}_{r.periodo}_{etiqueta}")

    estado["paso"] = "ventana censal"
    pg = nav.abrir(SERVIDOR[pruebas] + VENTANA[r.modelo], espera=3000)
    _en_su_sitio(pg, pruebas)
    _rellenar_ventana(pg, r)
    foto("1_ventana")
    pg = nav.pulsar_para_presentar(pg, "Confirmar")
    pg = _hasta_el_formulario(nav, pg, pruebas)
    foto("2_formulario")

    estado["paso"] = "importar"
    with pg.expect_file_chooser(timeout=30000) as fc:
        _visible(pg, "Importar")[0].click()
    fc.value.set_files(r.fichero)
    pg.wait_for_timeout(8000)
    foto("3_importado")
    filas = sede.tabla_errores(pg.inner_text("body"))
    errores, _ = sede._clasificar(filas)
    if errores:
        raise Parada("importar", "el formulario de la AEAT da errores: " + "; ".join(errores))
    cas = sede._casillas_del_formulario(pg)
    distintas = [k for k, x in cas.items() if k in r.casillas and D2(r.casillas[k]) != x]
    if distintas:
        raise Parada("importar", "el formulario recalcula distinto: " + ", ".join(f"[{k}]" for k in distintas))

    if r.tipo == "I":
        estado["paso"] = "NRC"
        campo = pg.get_by_label(re.compile("NRC", re.I))
        campo = campo if campo.count() else pg.locator("input[id*='nrc' i], input[name*='nrc' i]")
        if not campo.count():
            raise Parada("NRC", "no encuentro dónde poner el NRC")
        campo.first.fill(nrc.strip().upper())

    estado["paso"] = "firmar"
    boton = "Firmar y Enviar" if _visible(pg, "Firmar y Enviar") else "Presentar declaración"
    if not _visible(pg, boton):
        raise Parada("firmar", "no encuentro «Firmar y Enviar» ni «Presentar declaración»")
    pg = nav.pulsar_para_presentar(pg, boton)
    foto("4_dialogo")
    conforme = pg.get_by_label("Conforme")
    conforme = conforme if conforme.count() else pg.get_by_role("checkbox", name=re.compile("Conforme", re.I))
    if not conforme.count():
        raise Parada("firmar", "no encuentro la casilla «Conforme» del diálogo de firma")
    conforme.first.check()
    finales = _visible(pg, "Firmar y Enviar")
    if not finales:
        raise Parada("firmar", "no encuentro el «Firmar y Enviar» del diálogo")
    estado["enviado"] = True            # desde aquí, si algo falla, no se sabe si ha llegado
    finales[-1].click()
    pg.wait_for_function(f"document.body.innerText.includes('{EXITO}')", timeout=180000)
    pg.wait_for_timeout(3000)
    foto("5_justificante")
    return _justificante(nav, pg, r, carpeta, pruebas)


def _justificante(nav, pg, r: Revision, carpeta: Path, pruebas: bool) -> dict:
    texto = pg.inner_text("body")

    def g(patron):
        m = re.search(patron, texto, re.I)
        return m.group(1).strip() if m else ""

    out = {"csv": g(r"(?:C[óo]digo Seguro de Verificaci[óo]n|CSV)\W+([A-Z0-9]{16})"),
           "justificante": g(r"justificante\W+(\d{13})"), "expediente": g(r"(?:Expediente|Referencia)\W+([0-9A-Z]{12,})"),
           "presentada": g(r"(\d{2}[-/]\d{2}[-/]\d{4}(?: a las)? \d{2}:\d{2}:\d{2})")}
    src = next((x.get_attribute("src") or x.get_attribute("data") for x in pg.locator("iframe, embed, object").all()
                if re.search(r"Cotejo|\.pdf|Justificante", x.get_attribute("src") or x.get_attribute("data") or "", re.I)), None)
    if src:
        datos = _bajar_pdf(nav, pg, urljoin(pg.url, src))
        if datos:
            pdf = carpeta / "salida" / "presentado" / f"{'ensayo' if pruebas else 'justificante'}_{r.modelo}_{r.ejercicio}_{r.periodo}_{out['csv'] or 'sincsv'}.pdf"
            pdf.write_bytes(datos)
            out["pdf"] = str(pdf)
        else:
            out["pdf_error"] = "el justificante no ha llegado como PDF: bájalo con `gestoria presentados --descargar`"
    return out


def _bajar_pdf(nav, pg, url: str) -> bytes | None:
    """Desde la propia página (su sesión y sus cookies) y, si no, con la petición del contexto."""
    try:
        b64 = pg.evaluate("""async u => { const r = await fetch(u, {credentials: 'include'});
            const b = new Uint8Array(await r.arrayBuffer()); let s = '';
            for (let i = 0; i < b.length; i++) s += String.fromCharCode(b[i]); return btoa(s); }""", url)
        datos = base64.b64decode(b64)
        if datos.startswith(b"%PDF"):
            return datos
    except Exception:
        pass
    try:
        datos = nav.ctx.request.get(url).body()
        return datos if datos.startswith(b"%PDF") else None
    except Exception:
        return None


def _cotejar(nav, r: Revision, carpeta: Path) -> dict:
    """Lo que de verdad ha quedado presentado, contra los libros."""
    from gestoria import aeat, cotejo

    try:
        b = aeat.descargar_presentado(nav, r.modelo, r.ejercicio, r.periodo, carpeta / "salida" / "presentado")
        if not b.get("encontrado"):
            return {"estado": "todavía no aparece en «presentados»: míralo en un rato con `gestoria cotejar 303`"}
        difs = cotejo.cotejar_303(cotejo.leer_presentado(Path(b["fichero"])), {k: D2(v) for k, v in r.casillas.items()})
        return {"estado": "coincide al céntimo" if not difs else f"{len(difs)} casilla(s) distintas",
                "difs": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in x.items()} for x in difs]}
    except Exception as e:
        return {"estado": f"no he podido cotejarlo: {type(e).__name__}"}


def texto(r: Revision) -> str:
    """La revisión para la terminal: cada paso y, al final, qué se puede hacer."""
    l = [f"{r.nivel} Antes de presentar el {r.modelo} del {r.periodo} {r.ejercicio} · {r.nif}", ""]
    l += [f"  {p}" for p in r.pasos]
    l.append("")
    if r.bloqueada:
        n = sum(p.nivel == "⛔" for p in r.pasos)
        l.append(f"⛔ No se presenta: {n} cosa(s) que arreglar antes (arriba, con ⛔).")
    else:
        l.append(f"Todo lo que se puede comprobar está comprobado. Tu conformidad, si quieres presentarlo, es:\n"
                 f"  {r.frase}")
    return "\n".join(l)
