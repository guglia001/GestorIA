"""Órdenes con certificado: todo lo que se puede mirar en las sedes, en SOLO LECTURA.

Cada una abre la sede con el certificado de perfil.toml ([sede]) o, con `--personal`, con el de
persona física ([sede.personal]), lee la pantalla y la explica. Ninguna abre notificaciones,
presenta, firma, paga ni cambia nada.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path


def registrar(sub) -> None:
    def con_cert(nombre: str, ayuda: str, func, personal: bool = True):
        p = sub.add_parser(nombre, help=ayuda)
        if personal:
            p.add_argument("--personal", action="store_true", help="con el certificado de persona física ([sede.personal])")
        p.set_defaults(func=func)
        return p

    sub.add_parser("certificado", help="tus certificados en local: de quién son, de qué tipo y cuándo caducan").set_defaults(func=orden_certificado)
    con_cert("notificaciones", "notificaciones y comunicaciones de la AEAT sin abrir, y qué pasa si nadie las abre", orden_notificaciones)
    d = con_cert("dehu", "DEHú: notificaciones pendientes de TODAS las administraciones (sin comparecer)", orden_dehu)
    d.add_argument("--realizadas", action="store_true", help="también las ya comparecidas")
    con_cert("censo", "lo que el censo dice de ti: identificación, domicilio, obligaciones, regímenes de IVA, IAE, socios, avisos", orden_censo)
    con_cert("poderes", "quién puede actuar por ti en la AEAT (apoderamientos otorgados y recibidos)", orden_poderes)
    con_cert("deudas", "deudas pendientes con la AEAT", orden_deudas)
    con_cert("expedientes", "«Mis expedientes»: procedimientos abiertos con la AEAT", orden_expedientes)
    con_cert("accesos", "«Mis últimos accesos» a la sede y «Mis alertas»", orden_accesos)
    p = con_cert("presentados", "lo presentado de cada modelo, quién lo presentó, y copia del justificante y del fichero", orden_presentados)
    p.add_argument("--modelo", action="append", help="303, 390, 200, 130, 036… (por defecto, los de tu perfil)")
    p.add_argument("--descargar", action="store_true", help="baja el justificante (PDF) y el fichero presentado a salida/presentado/")
    c = con_cert("cotejar", "cotejar el 303 PRESENTADO con tus libros, casilla a casilla", orden_cotejar, personal=False)
    c.add_argument("modelo", nargs="?", default="303", choices=["303"])
    c.add_argument("--ejercicio", type=int)
    c.add_argument("--periodo", help="1T…4T; por defecto el último trimestre cerrado")
    c.add_argument("--fichero", help="un fichero presentado ya bajado (no sale a la sede)")
    r = con_cert("roi", "¿consta un NIF en el registro de operadores intracomunitarios? (certificado de la AEAT con CSV)", orden_roi, personal=False)
    r.add_argument("nif", nargs="?", help="por defecto, el tuyo")
    n = sub.add_parser("nif", help="dígito de control de un NIF y, con --censo, si existe con ese nombre en la AEAT")
    n.add_argument("nif")
    n.add_argument("nombre", nargs="?", default="")
    n.add_argument("--censo", action="store_true", help="comprobarlo en el censo de la AEAT con tu certificado")
    n.set_defaults(func=orden_nif)
    con_cert("terceros", "tus clientes y proveedores contra el censo de la AEAT (NIF y nombre)", orden_terceros, personal=False)
    df = con_cert("datos-fiscales", "lo que pagadores, bancos y clientes han declarado de ti a Hacienda", orden_datos_fiscales)
    df.add_argument("--ejercicio", type=int, help="por defecto, el año pasado")
    con_cert("domiciliaciones", "cargos domiciliados de tus declaraciones", orden_domiciliaciones)
    ss = sub.add_parser("seguridad-social", help="Import@ss: tus altas, la cuota de autónomo, el próximo cargo y la regularización")
    ss.add_argument("--principal", action="store_true", help="con el certificado de [sede] en vez del personal")
    ss.set_defaults(func=orden_seguridad_social)
    m = con_cert("mirar", "leer cualquier página de una sede con tu certificado (solo lectura)", orden_mirar)
    m.add_argument("url")
    m.add_argument("--pulsar", action="append", default=[], help="botón de consulta que pulsar (Buscar, Consultar…)")
    m.add_argument("--clave", action="store_true", help="si pide Cl@ve, entrar con «DNIe / Certificado electrónico»")
    ch = sub.add_parser("chequeo", help="la revisión completa con certificado: todo lo de arriba, con hallazgos 🔴 🟡 🟢 y su fuente")
    ch.add_argument("--sin-personal", action="store_true")
    ch.add_argument("--sin-dehu", action="store_true")
    ch.add_argument("--sin-terceros", action="store_true")
    ch.add_argument("--sin-cotejo", action="store_true")
    ch.set_defaults(func=orden_chequeo)
    v = sub.add_parser("vigia", help="flujo diario: notificaciones (AEAT y DEHú), deudas, alertas y certificado; avisa de lo nuevo")
    v.add_argument("--sin-dehu", action="store_true")
    v.set_defaults(func=orden_vigia)
    pr = sub.add_parser("presentar", help="presenta una declaración en la sede después de revisarlo todo (sin --conforme, solo revisa)")
    pr.add_argument("modelo", choices=["303"])
    pr.add_argument("--ejercicio", type=int, help="por defecto, el del último trimestre cerrado")
    pr.add_argument("--periodo", help="1T…4T; por defecto, el último trimestre cerrado")
    pr.add_argument("--conforme", help="tu conformidad: la frase exacta que da la revisión («PRESENTAR 303 …»)")
    pr.add_argument("--pruebas", action="store_true", help="el ensayo, en el entorno de pruebas de la AEAT (sin efectos)")
    pr.add_argument("--nrc", help="el NRC del pago, si sale a ingresar y no está domiciliado")
    pr.add_argument("--sin-sede", action="store_true", help="revisar sin entrar en la sede (no sirve para presentar)")
    pr.add_argument("--sin-simulador", action="store_true")
    pr.add_argument("--sin-investigar", action="store_true", help="sin leer los manuales de la AEAT ni el BOE")
    pr.set_defaults(func=orden_presentar)
    fi = con_cert("firmar", "firma un documento con tu certificado y AutoFirma (PAdES, XAdES, Facturae o CAdES)", orden_firmar)
    fi.add_argument("fichero")
    fi.add_argument("--formato", choices=["pades", "xades", "facturae", "cades", "auto"], help="por defecto, según el fichero")
    fi.add_argument("--salida", help="por defecto, <nombre>_firmado al lado")


# ─── piezas comunes ─────────────────────────────────────────────────────────────────────────

def _ctx(a):
    from gestoria import perfil
    from gestoria.__main__ import carpeta_de

    c = carpeta_de(a)
    return c, perfil.cargar(c)


def _cual(a) -> str:
    return "personal" if getattr(a, "personal", False) else "principal"


def _nav(c, pf, cual: str):
    from gestoria.navegador import Navegador

    return Navegador(pf.ruta_certificado(cual), pf.clave_certificado(cual), capturas=c / "salida" / "capturas")


def _consultar(a, que: tuple[str, ...], **kw) -> tuple:
    from gestoria import aeat

    c, pf = _ctx(a)
    cual = _cual(a)
    sociedad = pf.tipo == "sl" and cual == "principal"
    with _nav(c, pf, cual) as nav:
        d = aeat.consultar(nav, que, nif=pf.nif, es_sociedad=sociedad, **kw)
    return c, pf, cual, d


def _cabecera(pf, cual: str, que: str) -> None:
    quien = pf.nombre if cual == "principal" else "certificado personal"
    print(f"{que} · {quien} · solo lectura: no se ha abierto, presentado ni cambiado nada\n")


def _errores(d: dict) -> None:
    for k, e in (d.get("errores") or {}).items():
        print(f"⚠️ no he podido leer «{k}»: {e}")


def _imprimir(hallazgos) -> None:
    for h in hallazgos:
        print(f"  {h}")


# ─── órdenes ────────────────────────────────────────────────────────────────────────────────

def orden_certificado(a) -> int:
    from gestoria import certificado, nif as nifmod

    c, pf = _ctx(a)
    peor = 0
    for cual, titulo in (("principal", "[sede]"), ("personal", "[sede.personal]")):
        if not pf.tiene_certificado(cual):
            print(f"{titulo}: sin certificado" + (" (añádelo en perfil.toml para usar las órdenes con certificado)" if cual == "principal" else ""))
            continue
        try:
            x = certificado.leer(pf.ruta_certificado(cual), pf.clave_certificado(cual))
        except Exception as e:
            print(f"{titulo}: ❌ no se puede leer ({type(e).__name__}: {e})")
            peor = max(peor, 2)
            continue
        print(f"{titulo} {x.describir()}")
        if cual == "principal" and nifmod.normalizar(x.nif) != nifmod.normalizar(pf.nif):
            print(f"   ❌ el certificado es del NIF {x.nif} y perfil.toml dice {pf.nif}: la sede enseña los datos del certificado")
            peor = 2
        peor = max(peor, {"🔴": 2, "🟡": 1}.get(x.nivel(), 0))
    return peor


def orden_notificaciones(a) -> int:
    from gestoria import chequeo

    c, pf, cual, d = _consultar(a, ("notificaciones", "censo"))
    _cabecera(pf, cual, "Notificaciones de la AEAT")
    h = []
    chequeo._notificaciones(d, "", date.today(), h)
    _imprimir(h)
    censo = d.get("censo") or {}
    if censo:
        print(f"\nNotificaciones electrónicas obligatorias: {'sí, desde el ' + str(censo.get('neo_desde')) if censo.get('neo_obligado') else 'no'}"
              f" · suscrito voluntariamente: {'sí' if censo.get('neo_voluntario') else 'no'}")
    _errores(d)
    return 2 if any(x.nivel == "🔴" for x in h) else 1 if h and h[0].nivel == "🟡" else 0


def orden_dehu(a) -> int:
    from gestoria import dehu

    c, pf = _ctx(a)
    cual = _cual(a)
    with _nav(c, pf, cual) as nav:
        d = dehu.consultar(nav)
    _cabecera(pf, cual, f"DEHú de {d.get('titular') or '—'}")
    print(dehu.resumen(d))
    for n in d["pendientes"]:
        print(f"  🔴 {n['organismo']} · nº {n['identificador']} · «{n['concepto']}» · puesta a disposición {n['puesta'][:10]}"
              + (f" · caduca {n['caduca'][:10]}" if n["caduca"] else "") + (" · llega también en papel" if n["en_papel"] else ""))
    if d["pendientes"]:
        print("  → no la abro: comparecer la da por notificada y arranca los plazos (art. 43.2 Ley 39/2015). Lo decides tú.")
    for n in d["comunicaciones"]:
        print(f"  ✉️ comunicación de {n['organismo']}: «{n['concepto']}» ({n['puesta'][:10]})")
    if a.realizadas:
        for n in d["realizadas"]:
            print(f"  ✔ {n['organismo']} · nº {n['identificador']} · {n['estado'].lower()} el {(n['realizada'] or '')[:10]}")
    (c / "salida").mkdir(parents=True, exist_ok=True)
    (c / "salida" / f"dehu{'_personal' if cual == 'personal' else ''}.json").write_text(dehu.a_json(d), encoding="utf-8")
    return 2 if d["pendientes"] else 0


def orden_censo(a) -> int:
    from gestoria import chequeo, libros

    c, pf, cual, d = _consultar(a, ("censo", "obligaciones"))
    _cabecera(pf, cual, "Censo de la AEAT")
    x = d.get("censo") or {}
    print(f"{x.get('nombre')} · NIF {x.get('nif')} · {x.get('forma_juridica') or 'persona física'}"
          + (f" · constituida el {x['constitucion']}" if x.get("constitucion") else ""))
    print(f"Domicilio fiscal: {x.get('domicilio_fiscal')}\n   referencia catastral: {x.get('referencia_catastral') or '—'}")
    print(f"Administración: {x.get('administracion')} · situación censal: {d.get('estado_censal') or '—'}")
    print(f"Notificaciones electrónicas: {'OBLIGADO desde el ' + str(x.get('neo_desde')) if x.get('neo_obligado') else 'no obligado'}"
          f"{' · suscrito voluntariamente' if x.get('neo_voluntario') else ''}")
    av = d.get("avisos") or {}
    if av:
        print(f"Avisos de Hacienda: correo {av.get('correo') or '—'} · móvil {av.get('movil') or '—'} · app {'sí' if av.get('app') else 'no'}")
    print("\nObligaciones:")
    for o in d.get("obligaciones") or []:
        print(f"  {o['estado']:<5} {o['obligacion']} · {o['periodicidad'].lower()} · alta {o['alta']}" + (f" · baja {o['baja']}" if o["baja"] else ""))
    s = d.get("situacion") or {}
    if s:
        print(f"Regímenes de IVA: {', '.join(s.get('regimenes_iva') or ['—'])}")
        for o in s.get("otras") or []:
            print(f"  · {o}")
    for t, k, f in (("Actividades (IAE)", "actividades", lambda y: f"{y['epigrafe']} {y['denominacion']} · {y['estado'].lower()} desde {y['inicio']}"),
                    ("Representantes", "representantes", lambda y: f"{y['nombre']} ({y['nif']}) · {y['tipo'].lower()} · {y['situacion'].lower()}"),
                    ("Socios", "socios", lambda y: f"{y['nombre']} ({y['nif']}) · {y['participacion']} % · {y['estado'].lower()}")):
        if d.get(k):
            print(f"\n{t}:")
            for y in d[k]:
                print(f"  {f(y)}")
    v, co = libros.cargar(c)
    h = []
    chequeo._censo(d, pf, v, co, "", cual == "principal", h)
    if h:
        print("\nLo que significa:")
        _imprimir(h)
    _errores(d)
    return 1 if any(y.nivel in ("🔴", "🟡") for y in h) else 0


def orden_poderes(a) -> int:
    from gestoria import chequeo

    c, pf, cual, d = _consultar(a, ("poderes",))
    _cabecera(pf, cual, "Apoderamientos en la AEAT")
    for titulo, k in (("Otorgados (pueden actuar por ti)", "poderes_otorgados"), ("Recibidos (puedes actuar por otros)", "poderes_recibidos")):
        print(titulo + ":")
        for p in d.get(k) or []:
            print(f"  {'✔' if p['vigente'] else '·'} {p['nombre']} ({p['nif']}) · {p['tramite']}: {p['descripcion'].lower()} · "
                  f"{p['estado'].lower()} · hasta {p['baja'] or '—'}")
        if not d.get(k):
            print("  ninguno")
    h = []
    chequeo._poderes(d, "", date.today(), h)
    print()
    _imprimir([x for x in h if x.nivel != "🟢"])
    _errores(d)
    return 1 if any(x.nivel == "🟡" for x in h) else 0


def orden_deudas(a) -> int:
    c, pf, cual, d = _consultar(a, ("deudas",))
    _cabecera(pf, cual, "Deudas con la AEAT")
    x = d.get("deudas") or {}
    print({"sin_deudas": "✅ ", "con_deudas": "🔴 ", "bloqueado": "🟡 "}.get(x.get("estado"), "⚠️ ") + (x.get("texto") or "sin respuesta"))
    for f in x.get("deudas") or []:
        print("  " + " · ".join(f"{k}: {v}" for k, v in f.items() if v))
    _errores(d)
    return 2 if x.get("estado") == "con_deudas" else 1 if x.get("estado") != "sin_deudas" else 0


def orden_expedientes(a) -> int:
    c, pf, cual, d = _consultar(a, ("expedientes",))
    _cabecera(pf, cual, "Mis expedientes (AEAT)")
    for e in d.get("expedientes") or []:
        print(f"  {e['nombre']} ({e['n']})")
    if not d.get("expedientes"):
        print("  ninguno")
    _errores(d)
    return 0


def orden_accesos(a) -> int:
    c, pf, cual, d = _consultar(a, ("accesos", "alertas"))
    _cabecera(pf, cual, "Últimos accesos a la sede y alertas")
    for x in d.get("accesos") or []:
        print(f"  {x['fecha']} · {x['modo']} · {x['canal']}")
    print("\nMis alertas: " + ("; ".join(d.get("alertas") or []) or "ninguna"))
    _errores(d)
    raros = [x for x in d.get("accesos") or [] if "certificado" not in x["modo"].lower()]
    if raros:
        print(f"\n🟡 {len(raros)} acceso(s) sin certificado: ¿eres tú?")
    return 1 if raros or d.get("alertas") else 0


def orden_presentados(a) -> int:
    from gestoria import aeat

    c, pf = _ctx(a)
    cual = _cual(a)
    modelos = tuple(a.modelo or [m for m in pf.modelos if m in aeat.MODELOS_PRESENTADOS] + ["036"])
    with _nav(c, pf, cual) as nav:
        d = aeat.consultar(nav, ("presentados",), modelos=modelos)
        _cabecera(pf, cual, "Declaraciones presentadas")
        for m in modelos:
            filas = (d.get("presentados") or {}).get(m) or []
            print(f"{m}: " + ("nada" if not filas else ""))
            for f in filas:
                linea = f"  {f['ejercicio']} {f['periodo']:<3} {f['estado'].lower():<9} {f['presentada']} · expediente {f['expediente']}"
                if a.descargar and f["estado"] != "BAJA":
                    try:
                        b = aeat.descargar_presentado(nav, m, int(f["ejercicio"]), f["periodo"], c / "salida" / "presentado")
                        j = aeat.leer_justificante(b["justificante"]) if b.get("justificante") else {}
                        linea += (f"\n      presentado por {j.get('presentador') or '—'} ({j.get('presentador_nif') or '—'}) en calidad de "
                                  f"{(j.get('en_calidad_de') or '—').lower()} · {j.get('resultado') or ''} · CSV {j.get('csv') or '—'}"
                                  f"\n      → {b.get('justificante')}\n      → {b.get('fichero')}")
                    except Exception as e:
                        linea += f"\n      ⚠️ no he podido bajarlo: {type(e).__name__}: {str(e)[:120]}"
                print(linea)
    _errores(d)
    return 0


def orden_cotejar(a) -> int:
    from decimal import Decimal

    from gestoria import aeat, cotejo, flujos, libros
    from gestoria.modelos import m303
    from gestoria.numeros import eur

    c, pf = _ctx(a)
    ej0, per0 = flujos.ultimo_trimestre_cerrado(date.today())
    ej, per = a.ejercicio or ej0, a.periodo or per0
    info = {}
    if a.fichero:
        fichero = Path(a.fichero)
    else:
        with _nav(c, pf, "principal") as nav:
            info = aeat.descargar_presentado(nav, "303", ej, per, c / "salida" / "presentado")
        if not info.get("encontrado"):
            print(f"No consta presentado el 303 del {per} {ej} en la sede.")
            return 1
        fichero = Path(info["fichero"])
        if info.get("justificante"):
            info.update(aeat.leer_justificante(info["justificante"]))
    ventas, compras = libros.cargar(c)
    aj = libros.ajustes(c)
    desde, hasta = m303.periodo_fechas(ej, per)
    borrador, avisos = m303.casillas(ventas, compras, desde, hasta, Decimal(str(aj.get("compensar_pendiente", "0"))))
    presentado = cotejo.leer_presentado(fichero)
    print(f"Cotejo del 303 {per} {ej} · {pf.nombre} · presentado vs tus libros")
    if info.get("presentador"):
        print(f"Presentado el {info.get('presentada')} por {info['presentador']} ({info.get('presentador_nif')}) en calidad de "
              f"{(info.get('en_calidad_de') or '').lower()} · {info.get('resultado') or ''} · CSV {info.get('csv')}")
    print(f"Fichero presentado: {fichero}\n")
    difs = cotejo.cotejar_303(presentado, borrador)
    for linea in cotejo.explicar(difs):
        print(("❌ " if linea.startswith("[") else "   ") + linea)
    if not difs:
        print(f"✅ coinciden todas las casillas (resultado [71] = {eur(presentado.get('71', 0))})")
    for x in avisos:
        print(f"⚠️ tus libros: {x}")
    if per != "4T":
        siguiente = cotejo.compensar_siguiente(presentado, per)
        print(f"\nPara el 303 siguiente, en ajustes.toml (casilla [110]: lo pendiente [87] más lo que este salió a compensar):\n"
              f"  compensar_pendiente = \"{siguiente}\"\n"
              f"  fuente = \"303 {per} {ej} presentado: [87] {presentado.get('87', 0)} + a compensar "
              f"{max(-presentado.get('71', 0), 0)} (expediente {info.get('expediente') or fichero.stem})\"")
    return 1 if difs else 0


def orden_roi(a) -> int:
    from gestoria import aeat

    c, pf = _ctx(a)
    objetivo = (a.nif or pf.nif).upper().removeprefix("ES")
    with _nav(c, pf, "principal") as nav:
        d = aeat.consultar(nav, ("roi",), nif=objetivo)
    r = d.get("roi") or {}
    if r.get("en_roi") is None:
        _errores(d)
        print("⚠️ no he entendido la respuesta de la sede")
        return 2
    print(f"ES{objetivo} {'✅ CONSTA' if r['en_roi'] else '❌ NO consta'} en el registro de operadores intracomunitarios "
          f"(certificado de la AEAT a {r['fecha']}, CSV {r['csv']}: compruébalo en la sede con «Cotejo de documentos»)")
    return 0 if r["en_roi"] else 1


def orden_nif(a) -> int:
    from gestoria import nif as nifmod

    n = nifmod.normalizar(a.nif)
    if not nifmod.es_espanol(n):
        print(f"{n}: no es un NIF español; si es de otro país de la UE, compruébalo con `gestoria vies {n}`")
        return 1
    ok = nifmod.valido(n)
    tipo = {"A": "sociedad anónima", "B": "sociedad limitada", "E": "comunidad de bienes", "F": "cooperativa",
            "G": "asociación o fundación", "J": "sociedad civil", "N": "entidad extranjera", "P": "corporación local",
            "Q": "organismo público", "S": "órgano de la Administración", "W": "establecimiento permanente de no residente"
            }.get(n[0], "persona física (NIE)" if n[0] in "XYZ" else "persona física (DNI)" if n[0].isdigit() else "entidad")
    print(f"{n}: {'✅ dígito de control correcto' if ok else '❌ dígito de control MAL'} · {tipo}")
    if not (ok and a.censo):
        return 0 if ok else 1
    from gestoria import certificado, terceros

    c, pf = _ctx(a)
    filas = terceros.comprobar([(n, a.nombre)], certificado.contexto_tls(pf.ruta_certificado(), pf.clave_certificado()))
    f = filas[0] if filas else {"resultado": "sin respuesta", "nombre_censo": ""}
    print(f"censo de la AEAT: {f['resultado']}" + (f" · {f['nombre_censo']}" if f["nombre_censo"] else ""))
    return 0 if f["resultado"] == "IDENTIFICADO" else 1


def orden_terceros(a) -> int:
    from gestoria import certificado, libros, terceros

    c, pf = _ctx(a)
    ventas, compras = libros.cargar(c)
    pares = terceros.de_los_libros(ventas, compras)
    if not pares:
        print("No hay clientes ni proveedores con NIF español en los libros.")
        return 0
    filas = terceros.comprobar([(n, m) for n, m, _ in pares], certificado.contexto_tls(pf.ruta_certificado(), pf.clave_certificado()))
    papel = {n: p for n, _, p in pares}
    print(f"{len(filas)} NIF de tus libros contra el censo de la AEAT (servicio de comprobación de NIF):\n")
    for f in filas:
        marca = "✅" if f["resultado"] == "IDENTIFICADO" else "❌"
        print(f"  {marca} {papel[f['nif']]:<9} {f['nif']}  {f['nombre'][:40]:<40} → {f['resultado']}"
              + (f" · {f['nombre_censo']}" if f["nombre_censo"] and f["nombre_censo"].upper() != f["nombre"].upper() else ""))
    h = terceros.hallazgos(filas, papel)
    if h:
        print()
        for x in h:
            print(f"  {x['nivel']} {x['texto']}")
    return 1 if any(x["nivel"] == "🔴" for x in h) else 0


def orden_datos_fiscales(a) -> int:
    c, pf = _ctx(a)
    ej = a.ejercicio or date.today().year - 1
    c, pf, cual, d = _consultar(a, ("datos_fiscales",), ejercicio_datos_fiscales=ej)
    _cabecera(pf, cual, f"Datos fiscales {ej} (lo que terceros han declarado de ti)")
    for b in d.get("datos_fiscales") or []:
        print(f"■ {b['seccion']}")
        for f in b["filas"]:
            print("   " + " · ".join(f"{k}: {v}" for k, v in f.items() if v and k != "Código"))
    if not d.get("datos_fiscales"):
        print("Sin datos (o la pantalla no se ha podido leer).")
    _errores(d)
    return 0


def orden_domiciliaciones(a) -> int:
    c, pf, cual, d = _consultar(a, ("domiciliaciones",))
    _cabecera(pf, cual, "Domiciliaciones de este año")
    for f in d.get("domiciliaciones") or []:
        print("  " + " · ".join(f"{k}: {v}" for k, v in f.items() if v))
    if not d.get("domiciliaciones"):
        print("  ninguna")
    _errores(d)
    return 0


def orden_seguridad_social(a) -> int:
    from gestoria import chequeo, seguridad_social

    c, pf = _ctx(a)
    cual = "principal" if a.principal or not pf.tiene_certificado("personal") else "personal"
    with _nav(c, pf, cual) as nav:
        d = seguridad_social.consultar(nav)
    print("Seguridad Social (Import@ss) · solo lectura\n")
    for x in d["altas"]:
        print(f"  de alta en {x['regimen']}{' · ' + x['empresa'] if x['empresa'] else ''} desde {x['desde']}")
    if not d["altas"]:
        print("  sin altas que mostrar" if not d["de_alta"] else "  de alta (sin detalle)")
    for k, t in (("nuss", "número de la Seguridad Social"), ("dias_cotizados", "días cotizados"), ("tiempo_cotizado", "tiempo cotizado"),
                 ("base_cotizacion", "última base de cotización"), ("cuota_autonomo", "cuota de autónomo"),
                 ("regularizacion", "regularización de años anteriores"), ("cargo", "próximo cargo a partir del")):
        if d.get(k):
            print(f"  {t}: {d[k]}")
    for x in d["documentos"]:
        print(f"  📄 {x['documento']} ({x['fecha']})")
    h = []
    chequeo._seguridad_social(d, pf, date.today(), h)
    print()
    _imprimir([x for x in h if x.nivel in ("🔴", "🟡")])
    (c / "salida").mkdir(parents=True, exist_ok=True)
    (c / "salida" / "seguridad_social.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def orden_mirar(a) -> int:
    import re

    from gestoria.navegador import comprobar

    c, pf = _ctx(a)
    cual = _cual(a)
    with _nav(c, pf, cual) as nav:
        pg = nav.abrir(a.url, espera=3000)
        if a.clave:
            acceso = pg.locator("button:visible, a:visible").filter(has_text=re.compile("Acceso DNIe", re.I))
            if acceso.count():
                comprobar("Acceso DNIe / Certificado electrónico")
                acceso.first.click()
                pg.wait_for_timeout(12000)
        for b in a.pulsar:
            pg = nav.pulsar(pg, b)
        nav.captura(pg, "mirar")
        texto = pg.inner_text("body")
        url = pg.url
    print(f"# {url}  (solo lectura; captura en {c / 'salida' / 'capturas'})\n")
    print(re.sub(r"\n\s*\n+", "\n", texto).strip()[:12000])
    return 0


def orden_chequeo(a) -> int:
    from gestoria import chequeo
    from gestoria.__main__ import carpeta_de

    r = chequeo.ejecutar(carpeta_de(a), personal=not a.sin_personal, dehu=not a.sin_dehu,
                         terceros=not a.sin_terceros, cotejar=not a.sin_cotejo)
    print(open(r["informe"], encoding="utf-8").read())
    print(f"(informe en {r['informe']})")
    return {"🔴": 2, "🟡": 1}.get(r["nivel"], 0)


def orden_vigia(a) -> int:
    from gestoria import flujos
    from gestoria.__main__ import carpeta_de

    r = flujos.vigia(carpeta_de(a), dehu=not a.sin_dehu)
    print(f"{r['nivel']} Vigía de la sede · {date.today().isoformat()} · {len(r['rojos'])} en rojo, {len(r['nuevos'])} nuevo(s)")
    for h in r["hallazgos"]:
        print(f"  {'🆕 ' if str(h) in r['nuevos'] else ''}{h}")
    if not r["hallazgos"]:
        print("  ✅ nada pendiente en la AEAT ni en la DEHú")
    sys.stdout.flush()
    return 2 if r["nuevos"] else 1 if r["rojos"] else 0


def orden_presentar(a) -> int:
    from gestoria import flujos, presentar

    c, pf = _ctx(a)
    ej0, per0 = flujos.ultimo_trimestre_cerrado(date.today())
    ej, per = a.ejercicio or ej0, a.periodo or per0
    kw = {"nrc": a.nrc, "sede": not a.sin_sede, "simulador": not a.sin_simulador, "investigar": not a.sin_investigar}
    orden = f"gestoria presentar {a.modelo} --ejercicio {ej} --periodo {per}"
    if not a.conforme:
        r = presentar.revisar(c, a.modelo, ej, per, **kw)
        print(presentar.texto(r))
        if not r.bloqueada:
            print(f"\nPrimero, el ensayo en el entorno de pruebas de la AEAT (sin efectos):\n  {orden} --pruebas --conforme \"{r.frase}\"\n"
                  f"Y después, de verdad:\n  {orden} --conforme \"{r.frase}\"")
        return 2 if r.bloqueada else 1 if r.nivel == "⚠️" else 0
    res = presentar.presentar(c, a.modelo, ej, per, a.conforme, pruebas=a.pruebas, **kw)
    r = res["revision"]
    print(presentar.texto(r) + "\n")
    if res["estado"] == "bloqueada":
        print("⛔ No se ha presentado nada.")
        return 2
    if res["estado"] == "sin_conformidad":
        print(f"⛔ No se ha presentado nada: la conformidad no coincide con esta declaración. La suya es:\n  {r.frase}")
        return 2
    if res["estado"] == "parada":
        print(f"⛔ Parado en «{res['paso']}» sin enviar nada: {res['motivo']}\n   Las capturas de cada paso están en salida/capturas/.")
        return 2
    if res["estado"] == "desconocido":
        print(f"❓ Se pulsó «Firmar y Enviar» y algo falló después ({res['motivo']}): NO sé si ha llegado.\n"
              f"   Antes de nada: gestoria presentados --modelo {a.modelo}")
        return 3
    print(("🧪 Ensayo completo en el entorno de pruebas de la AEAT (sin efectos)" if res["pruebas"] else "✅ PRESENTADO")
          + f": CSV {res.get('csv') or '—'} · justificante {res.get('justificante') or '—'}" + (f"\n   {res['pdf']}" if res.get("pdf") else ""))
    if res.get("cotejo"):
        print(f"   Cotejo con tus libros: {res['cotejo']['estado']}")
    if res["pruebas"]:
        print(f"\nPara presentarlo de verdad:\n  {orden} --conforme \"{r.frase}\"")
    return 0


def orden_firmar(a) -> int:
    from gestoria import firma

    c, pf = _ctx(a)
    cual = _cual(a)
    entrada = Path(a.fichero).expanduser()
    out = firma.firmar_fichero(entrada, pf.ruta_certificado(cual), pf.clave_certificado(cual), a.salida, a.formato)
    print(f"✍️ Firmado con AutoFirma ({a.formato or firma.formato_de(entrada)}) y el certificado "
          f"{'personal' if cual == 'personal' else 'de ' + pf.nombre}: {out}")
    return 0
