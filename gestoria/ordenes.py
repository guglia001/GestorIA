"""Subórdenes del CLI."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path


def registrar(sub) -> None:
    h = sub.add_parser("hoy", help="el panel de cada mañana: plazos, hucha, libros, radares y sede")
    h.add_argument("--saldo", help="lo que tienes en el banco, para compararlo con la hucha")
    h.set_defaults(func=orden_hoy)
    hu = sub.add_parser("hucha", help="cuánto apartar para lo que viene, partida a partida")
    hu.add_argument("--saldo", help="lo que tienes en el banco")
    hu.set_defaults(func=orden_hucha)
    r = sub.add_parser("revisar", help="salud de los libros registro: numeración, NIF, cuotas, REBU, compras")
    r.set_defaults(func=orden_revisar)
    u = sub.add_parser("umbrales", help="radar del 347 y de los umbrales que cambian tus obligaciones")
    u.add_argument("--ejercicio", type=int)
    u.set_defaults(func=orden_umbrales)
    re_ = sub.add_parser("recargo", help="qué cuesta presentar tarde (art. 27 LGT)")
    re_.add_argument("importe", help="lo que salía a ingresar")
    re_.add_argument("--vencio", required=True, help="AAAA-MM-DD, último día del plazo")
    re_.add_argument("--presentas", help="AAAA-MM-DD (por defecto hoy)")
    re_.add_argument("--interes", help="interés de demora anual en %%, si la Ley de Presupuestos lo cambió")
    re_.set_defaults(func=orden_recargo)
    p = sub.add_parser("303", help="borrador del 303 y fichero para «Importar»")
    p.add_argument("--ejercicio", type=int, required=True)
    p.add_argument("--periodo", required=True, help="1T…4T o 01…12")
    p.add_argument("--fichero", help="dónde escribir el fichero (por defecto salida/)")
    p.set_defaults(func=orden_303)
    v = sub.add_parser("validar", help="validar un fichero en el simulador OPEN de la AEAT")
    v.add_argument("modelo", choices=["303"])
    v.add_argument("fichero")
    v.add_argument("--ejercicio", type=int, required=True)
    v.set_defaults(func=orden_validar)
    c = sub.add_parser("calendario", help="próximos plazos, del calendario oficial de la AEAT")
    c.add_argument("--dias", type=int, default=120)
    c.add_argument("--solo-obligatorios", action="store_true")
    c.set_defaults(func=orden_calendario)
    m = sub.add_parser("manuales", help="buscar en los manuales prácticos de la AEAT")
    m.add_argument("consulta")
    m.add_argument("--manual", action="append", help="iva, sociedades, renta, censal, actividades")
    m.add_argument("--max", type=int, default=8)
    m.set_defaults(func=orden_manuales)
    b = sub.add_parser("boe", help="texto vigente de un artículo del BOE consolidado")
    b.add_argument("id_boe", help="p. ej. BOE-A-1992-28740 (Ley del IVA)")
    b.add_argument("articulo", help="p. ej. 137 o «201 bis»")
    b.set_defaults(func=orden_boe)
    s = sub.add_parser("sede", help="foto de tu sede de la AEAT con tu certificado (solo lectura)")
    s.add_argument("--modelos", default="303,390,200,036", help="modelos de los que mirar lo presentado")
    s.set_defaults(func=orden_sede)
    vi = sub.add_parser("vies", help="¿NIF-IVA válido en el VIES?")
    vi.add_argument("nif")
    vi.set_defaults(func=orden_vies)
    t = sub.add_parser("trimestre", help="flujo de cierre del IVA: borrador, fichero, validación, plazo y resumen")
    t.add_argument("--ejercicio", type=int, help="por defecto, el del último trimestre cerrado")
    t.add_argument("--periodo", help="1T…4T; por defecto, el último trimestre cerrado")
    t.add_argument("--sin-validar", action="store_true", help="no abrir el simulador de la AEAT")
    t.set_defaults(func=orden_trimestre)
    se = sub.add_parser("semana", help="flujo semanal: el panel más lo que toca hacer, en Markdown")
    se.set_defaults(func=orden_semana)
    an = sub.add_parser("anual", help="flujo de cierre del año: IVA por trimestres, IS/IRPF, 347 y calendario")
    an.add_argument("--ejercicio", type=int, help="por defecto, el año pasado")
    an.set_defaults(func=orden_anual)
    bn = sub.add_parser("banco", help="concilia los movimientos del banco con tus libros (Norma 43, CSV o Excel en banco/, "
                                      "o --descargar con las cookies de tu sesión)")
    bn.add_argument("--descargar", action="store_true", help="baja antes el extracto con las cookies de tu sesión ([banco] en perfil.toml)")
    bn.add_argument("--desde", help="AAAA-MM-DD, para la descarga (por defecto, hace 90 días)")
    bn.add_argument("--hasta", help="AAAA-MM-DD, para la descarga (por defecto, hoy)")
    bn.set_defaults(func=orden_banco)
    w = sub.add_parser("web", help="el panel de control contable en tu navegador: diario, mayor, sumas y saldos, PyG, balance, "
                                   "IVA, facturación, 303 y banco")
    w.add_argument("--puerto", type=int, default=8640)
    w.add_argument("--fichero", action="store_true", help="solo escribe salida/web/index.html, sin servidor")
    w.add_argument("--sin-abrir", action="store_true", help="no abre el navegador")
    w.set_defaults(func=orden_web)
    co = sub.add_parser("contabilidad", help="los asientos que salen de tus libros y del banco, sumas y saldos, PyG y balance")
    co.add_argument("--ejercicio", type=int, help="por defecto, el de hoy")
    co.set_defaults(func=orden_contabilidad)
    ay = sub.add_parser("ayudas", help="ayudas y subvenciones que puedes pedir: la Base de Datos Nacional de Subvenciones, filtrada por quién "
                                       "eres, dónde estás y a qué te dedicas; y las bonificaciones que no están ahí")
    ay.add_argument("--region", help="tu provincia o comunidad como la llama la BDNS (por defecto, [ayudas] region de perfil.toml)")
    ay.add_argument("--palabras", help="lo que te describe, separado por comas (por defecto, [ayudas] palabras de perfil.toml)")
    ay.add_argument("--dias", type=int, default=120, help="convocatorias publicadas en los últimos N días (120)")
    ay.add_argument("--max", type=int, default=25, help="cuántas se miran con detalle (25)")
    ay.set_defaults(func=orden_ayudas)
    de = sub.add_parser("deducciones", help="qué te puedes deducir y qué no, comprobado contra tus libros y tu banco, cada regla con su artículo")
    de.add_argument("--comprobar", action="store_true", help="lee cada artículo en el BOE ahora mismo y comprueba que la cifra sigue ahí")
    de.set_defaults(func=orden_deducciones)
    ik = sub.add_parser("instalar-skills", help="copia las skills a .claude/skills/ (o a ~/.claude/skills con --global)")
    ik.add_argument("--global", dest="global_", action="store_true")
    ik.set_defaults(func=orden_instalar_skills)
    from gestoria import ordenes_sede

    ordenes_sede.registrar(sub)


def _dec(x) -> Decimal | None:
    from gestoria.numeros import importe

    return importe(x) if x is not None else None


def orden_hoy(a) -> int:
    from gestoria import panel
    from gestoria.__main__ import carpeta_de

    d = panel.construir(carpeta_de(a), saldo=_dec(a.saldo))
    print(panel.render(d))
    return {panel.ROJO: 2, panel.AMARILLO: 1}.get(d["nivel"], 0)


def orden_hucha(a) -> int:
    from gestoria import calendario, hucha, libros, panel, perfil
    from gestoria.__main__ import carpeta_de
    from gestoria.numeros import eur
    from datetime import date

    c = carpeta_de(a)
    pf = perfil.cargar(c)
    ventas, compras = libros.cargar(c)
    partidas = hucha.calcular(pf, ventas, compras, libros.ajustes(c), date.today(), panel.presentados_de(panel.foto_sede(c)))
    print(f"Hucha de {pf.nombre} a {calendario.fecha_txt(date.today())}: aparta {eur(hucha.total(partidas))}\n")
    for p in partidas:
        print(f"{eur(p.importe):>14}  {p.modelo:<4} {p.concepto} → {calendario.fecha_txt(p.vence)}")
        print(f"{'':14}  ↳ {p.nota or '—'}\n{'':14}  fuente: {p.fuente}")
    saldo = _dec(a.saldo)
    if saldo is not None:
        dif = saldo - hucha.total(partidas)
        print(f"\nTienes {eur(saldo)}: {'te sobran ' + eur(dif) if dif >= 0 else 'TE FALTAN ' + eur(-dif)}")
    return 0


def orden_revisar(a) -> int:
    from datetime import date

    from gestoria import libros, revisar
    from gestoria.__main__ import carpeta_de

    ventas, compras = libros.cargar(carpeta_de(a))
    h = revisar.revisar(ventas, compras, date.today())
    for x in h:
        print(x)
    errores = sum(1 for x in h if x.nivel == "error")
    print(f"\n{len(ventas)} facturas emitidas, {len(compras)} recibidas · {errores} error(es), {len(h) - errores} aviso(s)"
          if h else f"✅ {len(ventas)} facturas emitidas y {len(compras)} recibidas sin hallazgos")
    return 1 if errores else 0


def orden_umbrales(a) -> int:
    from datetime import date

    from gestoria import libros, perfil, umbrales
    from gestoria.__main__ import carpeta_de
    from gestoria.numeros import eur

    c = carpeta_de(a)
    ej = a.ejercicio or date.today().year
    ventas, compras = libros.cargar(c)
    print(f"Radar del 347 ({ej}): terceros con más de 3.005,06 € (art. 33.1 RGAT)")
    terceros = umbrales.radar_347(ventas, compras, ej)
    for t in terceros:
        print(f"  {t.nombre}{(' (' + t.nif + ')') if t.nif else ''}: entregas {eur(t.entregas)}, adquisiciones {eur(t.adquisiciones)}")
    if not terceros:
        print("  ninguno")
    print(f"\nUmbrales ({ej}, cifra de negocios {eur(umbrales.cifra_negocios(ventas, ej))}):")
    for u in umbrales.umbrales(perfil.cargar(c), ventas, ej):
        print(f"  {umbrales.barra(u.pct)} {u.pct:>3} %  {u.nombre} ({eur(u.limite)}, {u.fuente}): si lo pasas, {u.consecuencia}")
    return 0


def orden_recargo(a) -> int:
    from datetime import date

    from gestoria import recargos
    from gestoria.numeros import eur, importe

    presentas = date.fromisoformat(a.presentas) if a.presentas else date.today()
    r = recargos.calcular(importe(a.importe), date.fromisoformat(a.vencio), presentas,
                          importe(a.interes) if a.interes else recargos.INTERES_DEMORA)
    print(f"Importe {eur(importe(a.importe))}, vencía el {a.vencio}, se presenta el {presentas}: {r.meses_completos} mes(es) completo(s) de retraso")
    print(f"  recargo {r.porcentaje} % = {eur(r.recargo)} → {eur(r.recargo_reducido)} si pagas todo en plazo (reducción del 25 %, art. 27.5 LGT)")
    if r.intereses:
        print(f"  intereses de demora {r.dias_interes} días al {recargos.INTERES_DEMORA if not a.interes else a.interes} %: {eur(r.intereses)}")
    print(f"  total a ingresar: {eur(r.total)} (sin la reducción)\n  fuente: {r.fuente}")
    print("  ⚠️ si Hacienda te lo hubiera requerido antes, en vez de recargo hay sanción (arts. 191 y ss. LGT)")
    return 0


def orden_303(a) -> int:
    from gestoria import libros, perfil
    from gestoria.__main__ import carpeta_de
    from gestoria.modelos import m303

    c = carpeta_de(a)
    pf = perfil.cargar(c)
    ventas, compras = libros.cargar(c)
    aj = libros.ajustes(c)
    desde, hasta = m303.periodo_fechas(a.ejercicio, a.periodo)
    cas, avisos = m303.casillas(ventas, compras, desde, hasta,
                                Decimal(str(aj.get("compensar_pendiente", "0"))))
    print(f"Modelo 303 · {a.ejercicio} {a.periodo} · {pf.nombre} ({pf.nif}) · BORRADOR, no presentado")
    for k in sorted(cas, key=int):
        if cas[k] and k != "65":
            print(f"  [{k:>3}] {cas[k]:>12}")
    for x in avisos:
        print(f"⚠️ {x}")
    f = Path(a.fichero) if a.fichero else c / "salida" / f"303_{a.ejercicio}_{a.periodo}.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(m303.generar_fichero(pf, a.ejercicio, a.periodo, cas), encoding="latin-1")
    print(f"fichero para «Importar»: {f}")
    print(f"valídalo:  gestoria validar 303 {f} --ejercicio {a.ejercicio}")
    return 0


def orden_calendario(a) -> int:
    from datetime import date, timedelta

    from gestoria import calendario, perfil
    from gestoria.__main__ import carpeta_de

    pf = perfil.cargar(carpeta_de(a))
    hoy = date.today()
    hasta = hoy + timedelta(days=a.dias)
    filas, ultimo = calendario.plazos(pf, hoy, hasta)
    for p in filas:
        if a.solo_obligatorios and not p.obligatorio:
            continue
        marca = "✅" if p.obligatorio else "· "
        print(f"{marca} {calendario.fecha_txt(p.fecha)} (en {(p.fecha - hoy).days:>3} d)  {p.modelo}  {p.texto[:90]}"
              + ("" if p.obligatorio else f"\n{'':36}↳ {p.condicion}"))
    if ultimo and ultimo < hasta:
        print(f"\n⚠️ El calendario publicado por la AEAT llega hasta el {calendario.fecha_txt(ultimo)}.")
    if not filas:
        print("Sin plazos en el intervalo.")
    print("Fuente: calendario del contribuyente de la AEAT (iCalendar oficial).")
    return 0


def orden_manuales(a) -> int:
    import sys

    from gestoria import manuales

    claves = a.manual or list(manuales.MANUALES)
    for k in claves:
        try:
            print(f"[{k}] {manuales.al_dia(k)}", file=sys.stderr)
        except Exception as e:  # sin red: se busca en la copia que haya
            print(f"[{k}] ⚠️ no se pudo comprobar la versión ({e})", file=sys.stderr)
    res = manuales.buscar(a.consulta, claves, a.max)
    for r in res:
        donde = f"pág. PDF {r['pagina']} de {r['url']}" if r["url"].endswith(".pdf") else r["url"]
        print(f"■ [{r['manual']}] {donde}\n  …{r['extracto']}…\n")
    print(f"{len(res)} resultados." if res else "Sin resultados.")
    return 0 if res else 1


def orden_boe(a) -> int:
    from gestoria import boe

    r = boe.articulo(a.id_boe, a.articulo)
    if not r["texto"]:
        print(f"No encuentro el artículo {a.articulo} en {r['url']}")
        return 1
    print(r["texto"])
    print(f"\nFuente: {r['url']} (texto consolidado, consultado el {r['consultado']})")
    return 0


def orden_sede(a) -> int:
    from datetime import datetime

    from gestoria import perfil, sede
    from gestoria.__main__ import carpeta_de

    c = carpeta_de(a)
    pf = perfil.cargar(c)
    if not pf.certificado:
        print("perfil.toml no tiene [sede] certificado = \"ruta al .p12/.pfx\"")
        return 2
    d = sede.foto(Path(pf.certificado).expanduser(), pf.clave_certificado(),
                  tuple(m.strip() for m in a.modelos.split(",")))
    d["actualizado"] = datetime.now().isoformat(timespec="seconds")
    (c / "salida").mkdir(parents=True, exist_ok=True)
    (c / "salida" / "sede.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Sede de la AEAT · {pf.nombre} ({pf.nif}) · solo lectura: no se ha abierto nada")
    nl = d.get("no_leidas")
    print("\n## Notificaciones")
    print("✅ ninguna sin leer" if nl == 0 else f"🚨 hay secciones con notificaciones SIN LEER ({nl})"
          if nl else "⚠️ no he podido leer el resumen")
    for n in d.get("notificaciones") or []:
        if not n["leida"]:
            print(f"  🚨 {n['concepto']} · emitida {n['emitida']} — NO la abro: abrirla arranca "
                  "los plazos; sin abrir, a los 10 días naturales se entiende rechazada y el trámite "
                  "sigue (arts. 43.2 y 41.5 Ley 39/2015)")
    print("\n## Obligaciones de alta")
    for o in d.get("obligaciones") or []:
        print(f"  {o['obligacion']} · {o['periodicidad']} · alta {o['alta']}" + (f" · baja {o['baja']}" if o["baja"] else ""))
    print("\n## Presentado")
    for m, filas in d["presentados"].items():
        print(f"  {m}: " + (", ".join(f"{f['ejercicio']} {f['periodo']} ({f['estado'].lower()}, {f['presentada'][:10]})"
                                       for f in filas) or "nada"))
    for k, e in d["errores"].items():
        print(f"⚠️ {k}: {e}")
    print(f"\n(foto guardada en {c / 'salida' / 'sede.json'}; `gestoria hoy` la usa)")
    return 1 if nl else 0


def orden_vies(a) -> int:
    from gestoria import sede

    r = sede.vies(a.nif)
    print(f"{r['nif']} → {'✅ válido' if r['valido'] else '❌ no válido'} en el VIES · {r['nombre'] or ''} · {r['consulta']}")
    return 0 if r["valido"] else 1


def orden_trimestre(a) -> int:
    from datetime import date

    from gestoria import flujos
    from gestoria.__main__ import carpeta_de

    ej, per = flujos.ultimo_trimestre_cerrado(date.today())
    r = flujos.trimestre(carpeta_de(a), a.ejercicio or ej, a.periodo or per, validar=not a.sin_validar)
    print(open(r["resumen"], encoding="utf-8").read())
    print(f"(resumen guardado en {r['resumen']})")
    v = r["validacion"]
    return 1 if v and ("fallo" in v or v.get("errores")) else 0


def orden_semana(a) -> int:
    from gestoria import flujos, panel
    from gestoria.__main__ import carpeta_de

    r = flujos.semana(carpeta_de(a))
    print(open(r["resumen"], encoding="utf-8").read())
    print(f"(guardado en {r['resumen']})")
    return 2 if r["nivel"] == panel.ROJO else 0


def orden_anual(a) -> int:
    from datetime import date

    from gestoria import flujos
    from gestoria.__main__ import carpeta_de

    r = flujos.anual(carpeta_de(a), a.ejercicio or date.today().year - 1)
    print(open(r["resumen"], encoding="utf-8").read())
    print(f"(guardado en {r['resumen']})")
    return 0


def orden_ayudas(a) -> int:
    from gestoria import ayudas, perfil
    from gestoria.__main__ import carpeta_de

    c = carpeta_de(a)
    pf = perfil.cargar(c)
    region = a.region or pf.ayudas.get("region")
    palabras = [p.strip() for p in a.palabras.split(",") if p.strip()] if a.palabras else [str(p) for p in pf.ayudas.get("palabras") or []]
    hoy = date.today()
    r = ayudas.buscar(region, palabras, hoy, a.dias, a.max)
    t = ayudas.texto(r, pf, hoy)
    print(t)
    print(f"\n(guardado en {ayudas.guardar(c, r, t, pf, hoy)})")
    return 0


def orden_deducciones(a) -> int:
    from gestoria import banco, deducciones, libros, perfil
    from gestoria.__main__ import carpeta_de

    c = carpeta_de(a)
    pf = perfil.cargar(c)
    ventas, compras = libros.cargar(c)
    extractos = banco.cargar(c)
    hoy = date.today()
    hs = deducciones.revisar(pf, ventas, compras, libros.ajustes(c), extractos, hoy)
    comprobado = deducciones.comprobar([h.regla for h in hs]) if a.comprobar else None
    n_banco = sum(len(e.movimientos) for e in extractos)
    t = deducciones.texto(hs, pf, hoy, sum(1 for x in compras if x.fecha.year == hoy.year), n_banco, comprobado)
    print(t)
    print(f"\n(guardado en {deducciones.guardar(c, t, pf, hoy)})")
    return 1 if any(h.estado == "⛔" for h in hs) or (comprobado and not all(x["ok"] for x in comprobado.values())) else 0


def orden_instalar_skills(a) -> int:
    import shutil

    origen = Path(__file__).resolve().parent.parent / "skills"
    if not origen.is_dir():
        print(f"no encuentro las skills en {origen} (instala GestorIA desde el repositorio)")
        return 1
    destino = (Path.home() if a.global_ else Path.cwd()) / ".claude" / "skills"
    destino.mkdir(parents=True, exist_ok=True)
    for skill in sorted(p for p in origen.iterdir() if p.is_dir()):
        shutil.copytree(skill, destino / skill.name, dirs_exist_ok=True)
        print(f"  {skill.name} → {destino / skill.name}")
    print("Listo: abre Claude Code en esta carpeta y pregúntale como a tu gestor.")
    return 0


def orden_validar(a) -> int:
    from gestoria import dr, sede
    from gestoria.__main__ import carpeta_de

    texto = Path(a.fichero).read_text(encoding="latin-1")
    pags = dr.cargar(dr.DISENOS / "DR303e26v101.xlsx")
    r = sede.validar(a.modelo, a.ejercicio, Path(a.fichero), carpeta_de(a) / "salida" / "capturas")
    if not r["importado"]:
        print("❌ el simulador de la AEAT RECHAZÓ el fichero:")
    for e in r["errores"]:
        nota = (" (normal con un NIF inventado: no está en el censo, y sin él el formulario no"
                " deja cotejar las casillas)") if e.startswith(sede.NO_IDENTIFICADO) else ""
        print(f"❌ {e}{nota}")
    for w in r["avisos"]:
        print(f"⚠️ {w}")
    if r["sin_errores"]:
        print("✅ simulador de la AEAT: «No existen errores»")
    difs = []
    if r["casillas_aeat"]:
        constantes = {c.casilla for p in pags.values() for c in p.campos if c.casilla and c.constante}
        difs = sede.diferencias(dr.leer_fichero(texto, pags), r["casillas_aeat"], constantes)
        for k, nuestra, suya in difs:
            print(f"❌ casilla [{k}]: el fichero dice {nuestra} y el formulario de la AEAT {suya}")
        if not difs:
            res = r["casillas_aeat"].get("71")
            print(f"✅ el formulario de la AEAT recalcula las mismas casillas"
                  f"{f' (resultado [71] = {res})' if res is not None else ''}")
    print("capturas:", *r["capturas"], sep="\n  ")
    return 1 if r["errores"] or difs else 0


def orden_banco(a) -> int:
    from gestoria import banco, hucha, libros, panel, perfil
    from gestoria.__main__ import carpeta_de

    c = carpeta_de(a)
    pf = perfil.cargar(c)
    hoy = date.today()
    if a.descargar:
        f = banco.descargar(pf, c, date.fromisoformat(a.desde) if a.desde else None, date.fromisoformat(a.hasta) if a.hasta else None)
        print(f"⬇️ Extracto bajado con las cookies de tu sesión (solo lectura): banco/{f.name}\n")
    extractos = banco.cargar(c)
    if not extractos:
        print("No hay extractos en banco/: deja ahí el Norma 43, CSV o Excel que exporta tu banco, o pon [banco] cookies y "
              "url_descarga en perfil.toml y usa --descargar.")
        return 1
    ventas, compras = libros.cargar(c)
    r = banco.conciliar(extractos, ventas, compras, hoy)
    partidas = hucha.calcular(pf, ventas, compras, libros.ajustes(c), hoy, panel.presentados_de(panel.foto_sede(c)))
    t = banco.texto(r, hoy, hucha.total(partidas))
    print(t)
    salida = c / "salida"
    salida.mkdir(exist_ok=True)
    (salida / f"banco_{hoy.isoformat()}.md").write_text(f"# Banco · {pf.nombre} · {hoy.isoformat()}\n\n```\n{t}\n```\n",
                                                       encoding="utf-8")
    return 1 if r.cobros_sin_factura or r.pagos_sin_factura or r.descuadres else 0


def orden_web(a) -> int:
    from gestoria import web
    from gestoria.__main__ import carpeta_de

    c = carpeta_de(a)
    if a.fichero:
        print(f"🌐 Panel contable: {web.escribir(c)}")
        return 0
    web.servir(c, a.puerto, abrir=not a.sin_abrir)
    return 0


def orden_contabilidad(a) -> int:
    from datetime import date

    from gestoria import banco, contabilidad as ct, libros, perfil
    from gestoria.__main__ import carpeta_de
    from gestoria.numeros import eur

    c = carpeta_de(a)
    hoy = date.today()
    ej = a.ejercicio or hoy.year
    pf = perfil.cargar(c)
    ventas, compras = libros.cargar(c)
    k = ct.generar(pf, ventas, compras, libros.ajustes(c), ej, hoy if ej == hoy.year else date(ej, 12, 31), banco.cargar(c))
    print(f"📒 Contabilidad {ej} · {pf.nombre} ({pf.nif}) · {len(k.asientos)} asientos (el diario entero: `gestoria web`)\n")
    print("Sumas y saldos")
    for x in ct.sumas_y_saldos(k):
        print(f"  {x['cuenta']:<5} {x['nombre'][:44]:<44} {eur(x['deudor']) if x['deudor'] else '':>13} {eur(x['acreedor']) if x['acreedor'] else '':>13}")
    print("\nPérdidas y ganancias")
    for n, v in ct.perdidas_y_ganancias(k):
        print(f"  {n:<44} {eur(v):>13}")
    b = ct.balance(k)
    print(f"\nBalance: activo {eur(b['total_activo'])} · patrimonio neto y pasivo {eur(b['total_pasivo'])} "
          f"{'✅ cuadra' if b['cuadra'] else '❌ NO cuadra'}")
    for x in k.avisos:
        print(f"⚠️ {x}")
    return 0 if b["cuadra"] and not any("no cuadran" in x for x in k.avisos) else 1
