"""El chequeo con certificado: lo que un gestor revisa el primer día que le das tu certificado,
y luego cada mes. Todo en SOLO LECTURA.

Con el certificado principal (el de la empresa, o el tuyo si eres autónomo):
  AEAT: notificaciones sin abrir, censo (identificación, notificaciones electrónicas obligatorias,
  domicilio), obligaciones de alta, regímenes de IVA, IAE, representantes, socios, canales de aviso,
  poderes otorgados y recibidos, deudas, expedientes, alertas, últimos accesos, lo presentado de
  cada modelo (con quién lo presentó) y el cotejo del 303 presentado con tus libros, el ROI, los
  datos fiscales y las domiciliaciones · DEHú · tus clientes y proveedores contra el censo.
Con el certificado personal, si lo hay ([sede.personal]):
  AEAT de la persona (notificaciones, censo, obligaciones, poderes, deudas, alertas, datos
  fiscales de la renta) · DEHú de la persona · Seguridad Social (Import@ss).

`evaluar()` convierte todo eso en hallazgos 🔴 🟡 🟢 ℹ️, cada uno con su fuente y qué hacer. Es una
función pura: los tests le pasan datos inventados.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from gestoria import aeat, plazos

ORDEN = {"🔴": 0, "🟡": 1, "🟢": 2, "ℹ️": 3}
NUCLEO = {"303", "130", "131", "111", "115", "200", "349"}   # los modelos que el censo dice con certeza


@dataclass
class Hallazgo:
    nivel: str
    area: str
    texto: str
    fuente: str = ""
    que_hacer: str = ""

    def __str__(self) -> str:
        extra = (f" — {self.que_hacer}" if self.que_hacer else "") + (f" ({self.fuente})" if self.fuente else "")
        return f"{self.nivel} {self.area}: {self.texto}{extra}"


def _f(s) -> date | None:
    return aeat._fecha(str(s)) if s else None


def nivel_general(h: list[Hallazgo]) -> str:
    return "🔴" if any(x.nivel == "🔴" for x in h) else "🟡" if any(x.nivel == "🟡" for x in h) else "🟢"


# ─── evaluar ────────────────────────────────────────────────────────────────────────────────

def _certificados(datos, perfil, hoy, H):
    from gestoria import nif as nifmod

    for cual, c in (datos.get("certificados") or {}).items():
        nombre = "certificado" if cual == "principal" else "certificado personal"
        if not c:
            continue
        if c.get("error"):
            H.append(Hallazgo("🟡", nombre, f"no lo he podido leer: {c['error']}", que_hacer="revisa la ruta y la clave en perfil.toml"))
            continue
        dias = (_f(c["hasta"]) - hoy).days
        quien = c.get("entidad") or c.get("titular")
        if dias < 0:
            H.append(Hallazgo("🔴", nombre, f"de {quien}: CADUCADO desde el {c['hasta']}", que_hacer="pide uno nuevo: sin él no entras en ninguna sede"))
        elif dias <= 60:
            H.append(Hallazgo("🔴" if dias <= 15 else "🟡", nombre, f"de {quien}: caduca el {c['hasta']} (en {dias} días)",
                              que_hacer="renuévalo ya: con el certificado caducado no entras en la sede"))
        else:
            H.append(Hallazgo("🟢", nombre, f"de {quien} ({c['tipo']}): válido hasta el {c['hasta']}"))
        if cual == "principal" and c.get("nif") and nifmod.normalizar(c["nif"]) != nifmod.normalizar(perfil.nif):
            H.append(Hallazgo("🔴", nombre, f"es del NIF {c['nif']} y perfil.toml dice {perfil.nif}",
                              que_hacer="la sede enseña los datos del NIF del certificado, no los de tu perfil"))


def _notificaciones(a: dict, quien: str, hoy, H):
    censo = a.get("censo") or {}
    obligado = True if censo.get("neo_obligado") or censo.get("neo_voluntario") else (False if censo else None)
    vistas = set()
    for n in a.get("resumen") or []:
        vistas.add(n["numero"])
        if n["seccion"] == "comunicacion":
            H.append(Hallazgo("🟡", f"AEAT{quien}", f"comunicación sin leer nº {n['numero']} «{n['concepto']}» del {n['emitida']}",
                              que_hacer="una comunicación no arranca plazos; léela cuando puedas"))
            continue
        p = aeat.plazo_notificacion(n["emitida"], obligado, hoy)
        H.append(Hallazgo("🔴", f"AEAT{quien}", f"NOTIFICACIÓN SIN ABRIR nº {n['numero']}{' «' + n['concepto'] + '»' if n['concepto'] else ''}, "
                          f"emitida el {n['emitida']}: {p['texto']}",
                          que_hacer="GestorIA no la abre: decide tú cuándo (abrirla arranca los plazos)"))
    for n in a.get("notificaciones") or []:
        if not n.get("leida") and n["numero"] not in vistas:
            p = aeat.plazo_notificacion(n["emitida"], obligado, hoy)
            H.append(Hallazgo("🔴", f"AEAT{quien}", f"NOTIFICACIÓN SIN ABRIR nº {n['numero']} «{n['concepto']}», emitida el {n['emitida']}: {p['texto']}",
                              que_hacer="GestorIA no la abre: decide tú cuándo (abrirla arranca los plazos)"))
    if a.get("no_leidas") == 0:
        H.append(Hallazgo("🟢", f"AEAT{quien}", "sin notificaciones ni comunicaciones sin leer"))


def _dehu(d: dict | None, quien: str, H):
    if not d:
        return
    if d.get("error"):
        H.append(Hallazgo("🟡", f"DEHú{quien}", f"no he podido entrar: {d['error']}", que_hacer="mírala tú en dehu.redsara.es"))
        return
    for n in d.get("pendientes") or []:
        extra = []
        if n.get("caduca"):
            extra.append(f"si no la abres antes del {n['caduca'][:10]} se entiende rechazada")
        if n.get("en_papel"):
            extra.append("llega también en papel")
        H.append(Hallazgo("🔴", f"DEHú{quien}", f"notificación PENDIENTE de {n['organismo']} ({n['identificador']}, «{n['concepto']}»), "
                          f"puesta a disposición el {n['puesta'][:10]}" + (f": {'; '.join(extra)}" if extra else ""),
                          fuente="art. 43 Ley 39/2015", que_hacer="GestorIA no comparece: abrirla arranca los plazos y lo decides tú"))
    if d.get("comunicaciones"):
        H.append(Hallazgo("🟡", f"DEHú{quien}", f"{len(d['comunicaciones'])} comunicación(es) de los últimos 30 días"))
    if not d.get("pendientes") and "pendientes" in (d.get("leidas") or []):
        H.append(Hallazgo("🟢", f"DEHú{quien}", "sin notificaciones pendientes de ninguna administración"))


def _censo(a: dict, perfil, ventas, compras, quien: str, es_principal: bool, H):
    c = a.get("censo") or {}
    if c.get("neo_obligado"):
        H.append(Hallazgo("ℹ️", f"censo{quien}", f"obligado a notificaciones electrónicas desde el {c.get('neo_desde')}: si nadie abre una "
                          "en 10 días naturales, se da por notificada", fuente="art. 43.2 Ley 39/2015",
                          que_hacer="por eso `gestoria vigia` mira la sede cada día"))
    av = a.get("avisos") or {}
    if av:
        canales = ", ".join(x for x in (av.get("correo"), av.get("movil")) if x)
        H.append(Hallazgo("ℹ️" if canales else "🟡", f"avisos{quien}",
                          f"Hacienda avisa de cada notificación en: {canales}" if canales else "no tienes ningún canal de aviso de Hacienda",
                          fuente="art. 41.6 Ley 39/2015",
                          que_hacer="el aviso es voluntario: que no llegue no frena la notificación" if canales
                          else "date de alta en los avisos (procedimiento FZ04 de la sede)"))
    estado = a.get("estado_censal")
    if es_principal and estado and estado != "ACTIVO":
        H.append(Hallazgo("🔴", f"censo{quien}", f"la situación tributaria es «{estado}»", que_hacer="revisa con la sede qué obligaciones tienes de alta"))
    if not es_principal:
        return
    obl = a.get("obligaciones")
    if obl:
        censo_m = aeat.modelos_de_obligaciones(obl) & NUCLEO
        perfil_m = set(perfil.modelos) & NUCLEO
        for m in sorted(censo_m - perfil_m):
            H.append(Hallazgo("🟡", "censo", f"la sede te tiene de alta en el {m} y perfil.toml no lo lista",
                              que_hacer=f"añade «{m}» a [obligaciones] modelos: si no, GestorIA no te avisa de sus plazos"))
        for m in sorted(perfil_m - censo_m):
            H.append(Hallazgo("🟡", "censo", f"perfil.toml lista el {m} y en la sede no consta esa obligación de alta",
                              que_hacer="o sobra en el perfil o falta el alta en el censo (036): compruébalo"))
        if censo_m and not (censo_m - perfil_m) and not (perfil_m - censo_m):
            H.append(Hallazgo("🟢", "censo", "las obligaciones de alta en la sede coinciden con perfil.toml: "
                              + ", ".join(sorted(censo_m))))
    reg = (a.get("situacion") or {}).get("regimenes_iva") or []
    if reg:
        rebu_censo = any("REBU" in r for r in reg)
        if perfil.iva_regimen == "rebu" and not rebu_censo:
            H.append(Hallazgo("🔴", "IVA", "aplicas el REBU y en el censo no consta el alta en él", fuente="arts. 135-139 LIVA; 036 casillas 518 y 522",
                              que_hacer="sin el alta, esas ventas tributan por el régimen general"))
        elif perfil.iva_regimen != "rebu" and rebu_censo:
            H.append(Hallazgo("🟡", "IVA", "el censo dice que estás en el REBU y perfil.toml dice régimen general",
                              que_hacer="si revendes bienes usados comprados a particulares, pon regimen = \"rebu\" en [iva]"))
        for r in reg:
            if r in ("recargo de equivalencia", "criterio de caja", "simplificado", "agricultura, ganadería y pesca", "agencias de viajes"):
                H.append(Hallazgo("🟡", "IVA", f"estás de alta en el régimen de {r}: GestorIA no lo calcula", que_hacer="revisa el 303 a mano"))
        H.append(Hallazgo("ℹ️", "IVA", "regímenes de IVA de alta en la sede: " + ", ".join(reg)))
    socios = a.get("socios") or []
    if perfil.tipo == "sl" and len(socios) == 1 and (socios[0].get("participacion") or "").startswith("100"):
        H.append(Hallazgo("🟡", "sociedad", f"SL unipersonal (socio único: {socios[0]['nombre']})",
                          fuente="arts. 13 y 16 LSC",
                          que_hacer="la unipersonalidad tiene que estar inscrita en el Registro Mercantil, «Sociedad Unipersonal» "
                                    "en facturas y documentos, y los contratos con el socio en el libro-registro legalizado"))
    act = [x for x in a.get("actividades") or [] if (x.get("estado") or "").lower() == "alta"]
    if act:
        H.append(Hallazgo("ℹ️", "IAE", "epígrafes de alta: " + "; ".join(f"{x['epigrafe']} {x['denominacion']}" for x in act),
                          fuente="art. 82.1 TRLRHL", que_hacer="exento de la cuota del IAE el inicio de actividad (dos primeros años) y, "
                          "en una sociedad, con cifra de negocios < 1 M€; la persona física siempre"))
    rep = a.get("representantes") or []
    if rep:
        H.append(Hallazgo("ℹ️", "censo", "representantes: " + "; ".join(f"{r['nombre']} ({r['tipo'].lower()})" for r in rep)))


def _poderes(a: dict, quien: str, hoy, H):
    for p in a.get("poderes_otorgados") or []:
        if not p.get("vigente"):
            continue
        que = {"GENERALNOT": "recibir y ABRIR tus notificaciones (si la abre, quedas notificado ese día)",
               "GENERALLEY58": "presentar declaraciones y hacer trámites en tu nombre"}.get(p["tramite"], p["descripcion"].lower())
        baja = _f(p.get("baja"))
        H.append(Hallazgo("🟡", f"poderes{quien}", f"{p['nombre']} ({p['nif']}) puede {que} hasta el {p.get('baja') or '—'}",
                          fuente=f"apoderamiento {p['tramite']}, registro de apoderamientos de la AEAT",
                          que_hacer="si ya no trabajas con ella, revoca el poder en la sede (lo haces tú; GestorIA no revoca)"))
        if baja and 0 <= (baja - hoy).days <= 60:
            H.append(Hallazgo("🟡", f"poderes{quien}", f"el poder {p['tramite']} a {p['nombre']} vence el {p['baja']}"))
    for p in a.get("poderes_recibidos") or []:
        if p.get("vigente"):
            H.append(Hallazgo("ℹ️", f"poderes{quien}", f"puedes actuar por {p['nombre']} ({p['nif']}): {p['tramite']}"))
    if "poderes_otorgados" in a and not any(p.get("vigente") for p in a.get("poderes_otorgados") or []):
        H.append(Hallazgo("🟢", f"poderes{quien}", "no has dado poder a nadie en la AEAT"))


def _deudas_alertas_expedientes(a: dict, quien: str, H):
    d = a.get("deudas")
    if d:
        if d["estado"] == "con_deudas":
            for x in d["deudas"]:
                H.append(Hallazgo("🔴", f"deudas{quien}", " · ".join(f"{k}: {v}" for k, v in x.items() if v),
                                  que_hacer="mira el periodo (voluntario o ejecutivo): el recargo de apremio sube con el tiempo (art. 28 LGT)"))
        elif d["estado"] == "bloqueado":
            H.append(Hallazgo("🟡", f"deudas{quien}", d["texto"]))
        elif d["estado"] == "sin_deudas":
            H.append(Hallazgo("🟢", f"deudas{quien}", "sin deudas con la AEAT"))
        else:
            H.append(Hallazgo("🟡", f"deudas{quien}", d["texto"]))
    for x in a.get("alertas") or []:
        if "notificaciones" in x.lower():
            continue  # ya sale como notificación
        H.append(Hallazgo("🟡", f"alertas{quien}", f"«{x}» (Mis alertas de la sede)"))
    exp = a.get("expedientes") or []
    if exp:
        hojas = [e for e in exp if e["nombre"] != "Agencia Estatal de Administración Tributaria"]
        H.append(Hallazgo("ℹ️", f"expedientes{quien}", "en «Mis expedientes»: " + "; ".join(f"{e['nombre']} ({e['n']})" for e in hojas[-6:])))
    acc = a.get("accesos") or []
    raros = [x for x in acc if "certificado" not in (x.get("modo") or "").lower()]
    if raros:
        H.append(Hallazgo("🟡", f"accesos{quien}", f"{len(raros)} acceso(s) a la sede sin certificado: "
                          + "; ".join(f"{x['fecha']} {x['modo']}" for x in raros[:3]), que_hacer="¿eres tú? Si no, cambia tus claves de Cl@ve"))
    elif acc:
        H.append(Hallazgo("ℹ️", f"accesos{quien}", f"últimos {len(acc)} accesos a la sede, todos con certificado (el último, {acc[0]['fecha']})"))


def _inicio(a: dict, perfil, modelo: str, ejercicio: int) -> date:
    """Desde cuándo se deben las declaraciones de un modelo: el alta en el censo, o el inicio del ejercicio."""
    altas = [_f(o["alta"]) for o in a.get("obligaciones") or []
             if modelo in aeat.modelos_de_obligaciones([o]) and o.get("estado", "").upper() == "ALTA"]
    candidatas = [x for x in altas if x] + ([perfil.ejercicio_inicio] if perfil.ejercicio_inicio else [])
    return max(candidatas) if candidatas else date(ejercicio, 1, 1)


def _presentado(a: dict, perfil, hoy, H, cotejos):
    pres = a.get("presentados") or {}
    for modelo in ("303", "130"):
        if modelo not in perfil.modelos or modelo not in pres:
            continue
        hechos = {(int(f["ejercicio"]), f["periodo"]) for f in pres[modelo] if f.get("estado") != "BAJA"}
        for ej in (hoy.year - 1, hoy.year):
            inicio = _inicio(a, perfil, modelo, ej)
            for n in range(1, 5):
                per = f"{n}T"
                fin_periodo = date(ej + 1, 1, 1) if n == 4 else date(ej, 3 * n + 1, 1)
                vence = plazos.vence(modelo, ej, per)
                if fin_periodo <= inicio or vence >= hoy:
                    continue
                if (ej, per) not in hechos:
                    H.append(Hallazgo("🔴", "presentado", f"no consta presentado el {modelo} del {per} {ej} (venció el {vence.isoformat()})",
                                      fuente="consulta de declaraciones presentadas de la sede",
                                      que_hacer=f"preséntalo cuanto antes: `gestoria recargo <importe> --vencio {vence.isoformat()}`"))
    for modelo, filas in pres.items():
        if filas:
            ult = filas[-1]
            H.append(Hallazgo("ℹ️", "presentado", f"{modelo}: {len(filas)} presentada(s); la última, {ult['ejercicio']} {ult['periodo']} "
                              f"el {ult['presentada'][:10]} ({ult['estado'].lower()})"))
    for c in cotejos or []:
        if c.get("error"):
            H.append(Hallazgo("🟡", "cotejo", f"303 {c['periodo']} {c['ejercicio']}: no he podido cotejarlo ({c['error']})"))
            continue
        quien = c.get("presentador") or ""
        if quien and c.get("en_calidad_de") and c["en_calidad_de"].lower() != "titular":
            H.append(Hallazgo("ℹ️", "presentado", f"el 303 del {c['periodo']} {c['ejercicio']} lo presentó {quien} "
                              f"en calidad de {c['en_calidad_de'].lower()} el {c.get('presentada', '')[:10]}"))
        if c.get("difs"):
            from gestoria import cotejo as cot
            H.append(Hallazgo("🟡", "cotejo", f"el 303 PRESENTADO del {c['periodo']} {c['ejercicio']} no coincide con tus libros en "
                              f"{len(c['difs'])} casilla(s): " + " | ".join(cot.explicar(c["difs"])[:4]),
                              que_hacer=f"`gestoria cotejar 303 --ejercicio {c['ejercicio']} --periodo {c['periodo']}` lo detalla"))
        elif "difs" in c:
            H.append(Hallazgo("🟢", "cotejo", f"el 303 presentado del {c['periodo']} {c['ejercicio']} coincide al céntimo con tus libros"))


def _roi(a: dict, perfil, ventas, compras, H):
    r = a.get("roi")
    if not r or r.get("en_roi") is None:
        return
    intra = any(v.regimen == "intracomunitaria" for v in ventas) or any(c.origen == "intracomunitaria" for c in compras)
    if r["en_roi"]:
        H.append(Hallazgo("ℹ️", "ROI", f"constas en el registro de operadores intracomunitarios (certificado de la AEAT, CSV {r['csv']})"))
        if "349" not in perfil.modelos and intra:
            H.append(Hallazgo("🟡", "ROI", "tienes operaciones intracomunitarias y perfil.toml no lista el 349",
                              fuente="art. 78 RGAT", que_hacer="añade «349» a [obligaciones] modelos"))
    elif intra or "349" in perfil.modelos:
        H.append(Hallazgo("🟡", "ROI", f"NO constas en el ROI (certificado de la AEAT a {r['fecha']}, CSV {r['csv']}) y tienes "
                          "operaciones intracomunitarias", fuente="arts. 25 y 84.Uno.2.º LIVA; 036 casilla 582",
                          que_hacer="sin ROI tus proveedores de la UE te cobran su IVA y tú no puedes vender sin IVA a empresas de la UE"))


def _terceros(t: dict | None, H):
    if not t:
        return
    if t.get("error"):
        H.append(Hallazgo("🟡", "terceros", f"no he podido comprobar NIF en el censo: {t['error']}"))
        return
    malos = t.get("hallazgos") or []
    for x in malos:
        H.append(Hallazgo(x["nivel"], "terceros", x["texto"], fuente="servicio de comprobación de NIF de la AEAT"))
    n = len(t.get("filas") or [])
    if n and not any(x["nivel"] == "🔴" for x in malos):
        H.append(Hallazgo("🟢", "terceros", f"{n} cliente(s) y proveedor(es) con NIF español comprobados en el censo"))


def _datos_fiscales(a: dict, quien: str, H):
    for b in a.get("datos_fiscales") or []:
        sec, filas = b["seccion"], b["filas"]
        if sec.startswith(("NO EXISTEN", "NO PRESENTACI", "DATOS IDENTIFICATIVOS", "DOMICILIO")) or not filas:
            continue
        if "RENDIMIENTOS DE TRABAJO" in sec:
            from gestoria.numeros import eur, importe
            ret = sum((importe(f.get("Retenciones")) or 0 for f in filas), Decimal(0))
            din = sum((importe(f.get("Retribuciones Dinerarias")) or 0 for f in filas), Decimal(0))
            H.append(Hallazgo("ℹ️", f"datos fiscales{quien}", f"rendimientos del trabajo: {len(filas)} pagador(es), {eur(din)} con "
                              f"{eur(ret)} de retenciones", que_hacer="es lo que tus pagadores declararon (190): cotéjalo con tus nóminas"))
        else:
            H.append(Hallazgo("ℹ️", f"datos fiscales{quien}", f"{sec.capitalize()}: {len(filas)} dato(s) declarado(s) por terceros"))


def _seguridad_social(s: dict | None, perfil, hoy, H):
    if not s:
        return
    if s.get("error"):
        H.append(Hallazgo("🟡", "Seguridad Social", f"no he podido entrar en Import@ss: {s['error']}"))
        return
    altas = s.get("altas") or []
    if altas:
        H.append(Hallazgo("ℹ️", "Seguridad Social", "de alta en: " + "; ".join(
            f"{x['regimen']}{' (' + x['empresa'] + ')' if x['empresa'] else ''} desde {x['desde']}" for x in altas)
            + (f"; {s['dias_cotizados']} días cotizados" if s.get("dias_cotizados") else "")))
    regs = {x["regimen"].lower() for x in altas}
    if any("autónomo" in r for r in regs) and any("general" in r for r in regs):
        H.append(Hallazgo("🟡", "Seguridad Social", "pluriactividad (autónomo y por cuenta ajena a la vez)", fuente="art. 313 LGSS",
                          que_hacer="si lo cotizado entre los dos supera el tope de la Ley de Presupuestos, te devuelven el 50 % del exceso"))
    if s.get("cuota_autonomo"):
        cargo = _f(s.get("cargo"))
        regul = f" + {s['regularizacion']} de regularización de años anteriores" if s.get("regularizacion") else ""
        cerca = cargo is not None and 0 <= (cargo - hoy).days <= 15
        H.append(Hallazgo("🟡" if cerca else "ℹ️", "Seguridad Social", f"cuota de autónomo {s['cuota_autonomo']}{regul}"
                          + (f", cargo a partir del {s['cargo']}" if s.get("cargo") else ""),
                          que_hacer="tenlo en la cuenta ese día" if cerca else ""))
        if perfil.tipo == "autonomo" and perfil.reta_mensual is not None:
            from gestoria.numeros import importe
            real = importe(s["cuota_autonomo"])
            if real is not None and real != perfil.reta_mensual:
                H.append(Hallazgo("🟡", "Seguridad Social", f"perfil.toml dice reta_mensual = {perfil.reta_mensual} y la Seguridad Social te carga {s['cuota_autonomo']}",
                                  que_hacer="corrige reta_mensual: la hucha la usa"))


def evaluar(datos: dict, perfil, ventas, compras, hoy: date | None = None) -> list[Hallazgo]:
    hoy = hoy or date.today()
    H: list[Hallazgo] = []
    _certificados(datos, perfil, hoy, H)
    a = datos.get("aeat") or {}
    if a:
        _notificaciones(a, "", hoy, H)
        _censo(a, perfil, ventas, compras, "", True, H)
        _poderes(a, "", hoy, H)
        _deudas_alertas_expedientes(a, "", H)
        _presentado(a, perfil, hoy, H, datos.get("cotejos"))
        _roi(a, perfil, ventas, compras, H)
        _datos_fiscales(a, "", H)
        for parte, err in (a.get("errores") or {}).items():
            H.append(Hallazgo("🟡", "sede", f"no he podido leer «{parte}»: {err}"))
    _dehu(datos.get("dehu"), "", H)
    _terceros(datos.get("terceros"), H)
    p = datos.get("personal") or {}
    if p:
        pa = p.get("aeat") or {}
        if pa:
            _notificaciones(pa, " (personal)", hoy, H)
            _censo(pa, perfil, ventas, compras, " (personal)", False, H)
            _poderes(pa, " (personal)", hoy, H)
            _deudas_alertas_expedientes(pa, " (personal)", H)
            _datos_fiscales(pa, " (personal)", H)
            for parte, err in (pa.get("errores") or {}).items():
                H.append(Hallazgo("🟡", "sede (personal)", f"no he podido leer «{parte}»: {err}"))
        _dehu(p.get("dehu"), " (personal)", H)
        _seguridad_social(p.get("seguridad_social"), perfil, hoy, H)
    return sorted(H, key=lambda h: ORDEN.get(h.nivel, 9))


def evaluar_vigia(datos: dict, perfil, hoy: date | None = None) -> list[Hallazgo]:
    """Lo del vigía diario: certificados, notificaciones (AEAT y DEHú), deudas y alertas."""
    hoy = hoy or date.today()
    H: list[Hallazgo] = []
    _certificados(datos, perfil, hoy, H)
    for clave, quien in (("aeat", ""), ("personal", " (personal)")):
        a = (datos.get(clave) or {}) if clave == "aeat" else ((datos.get("personal") or {}).get("aeat") or {})
        if a:
            _notificaciones(a, quien, hoy, H)
            _deudas_alertas_expedientes(a, quien, H)
            for parte, err in (a.get("errores") or {}).items():
                H.append(Hallazgo("🟡", f"sede{quien}", f"no he podido leer «{parte}»: {err}"))
    _dehu(datos.get("dehu"), "", H)
    _dehu((datos.get("personal") or {}).get("dehu"), " (personal)", H)
    return sorted([h for h in H if h.nivel != "ℹ️"], key=lambda h: ORDEN.get(h.nivel, 9))


# ─── informe ────────────────────────────────────────────────────────────────────────────────

def markdown(datos: dict, hallazgos: list[Hallazgo], perfil) -> str:
    nivel = nivel_general(hallazgos)
    l = [f"# {nivel} Chequeo con certificado · {perfil.nombre} ({perfil.nif}) · {datos['fecha']}", "",
         "**Solo lectura.** GestorIA no ha abierto ninguna notificación, no ha presentado, firmado, pagado "
         "ni cambiado nada en ninguna sede.", ""]
    for marca, titulo in (("🔴", "Lo urgente"), ("🟡", "Para revisar"), ("🟢", "En orden"), ("ℹ️", "Lo que dice la administración de ti")):
        hs = [h for h in hallazgos if h.nivel == marca]
        if hs:
            l += [f"## {marca} {titulo}", ""] + [f"- **{h.area}**: {h.texto}" + (f" — {h.que_hacer}" if h.que_hacer else "")
                                                + (f" _({h.fuente})_" if h.fuente else "") for h in hs] + [""]
    a = datos.get("aeat") or {}
    c = a.get("censo") or {}
    if c:
        l += ["## Censo (AEAT)", "", f"- {c.get('nombre')} · {c.get('forma_juridica') or 'persona física'} · NIF {c.get('nif')}",
              f"- Domicilio fiscal: {c.get('domicilio_fiscal')}" + (f" · {c['referencia_catastral']}" if c.get("referencia_catastral") else ""),
              f"- Administración: {c.get('administracion')}"]
        l += [f"- Obligación: {o['obligacion']} · {o['periodicidad'].lower()} · alta {o['alta']}" for o in a.get("obligaciones") or []]
        l.append("")
    p = (datos.get("personal") or {}).get("seguridad_social") or {}
    if p and not p.get("error"):
        etiquetas = (("nuss", "número de la Seguridad Social"), ("dias_cotizados", "días cotizados"),
                     ("tiempo_cotizado", "tiempo cotizado"), ("base_cotizacion", "última base de cotización"),
                     ("cuota_autonomo", "cuota de autónomo"), ("regularizacion", "regularización de años anteriores"),
                     ("cargo", "próximo cargo a partir del"))
        l += ["## Seguridad Social", ""] + [f"- {t}: {p[k]}" for k, t in etiquetas if p.get(k)] + [""]
    l += ["---", f"Datos en `salida/chequeo.json`. Repetirlo: `gestoria chequeo` (el workflow mensual lo hace solo).", ""]
    return "\n".join(l)


def error_corto(e: Exception) -> str:
    """El error en una línea: los de Playwright traen el registro entero detrás."""
    return f"{type(e).__name__}: {(str(e).strip().splitlines() or [''])[0][:160]}"


def dehu_aparte(pfx, clave) -> dict:
    """La DEHú en un navegador propio: entra por Cl@ve y no conviene mezclarla con la sesión de la AEAT."""
    from gestoria import dehu
    from gestoria.navegador import Navegador

    error = None
    for _ in range(2):  # la pasarela de Cl@ve a veces tarda: un segundo intento antes de rendirse
        try:
            with Navegador(pfx, clave, sitios=("clave", "dehu")) as nav:
                return dehu.consultar(nav)
        except Exception as e:
            error = error_corto(e)
    return {"error": error}


def _cert_info(perfil, cual: str) -> dict | None:
    from gestoria import certificado

    if not perfil.tiene_certificado(cual):
        return None
    try:
        c = certificado.leer(perfil.ruta_certificado(cual), perfil.clave_certificado(cual))
        return {**asdict(c), "nif": c.nif, "desde": c.desde.isoformat(), "hasta": c.hasta.isoformat()}
    except Exception as e:
        return {"error": error_corto(e)}


def _foto_compat(a: dict) -> dict:
    """Lo que `gestoria hoy` lee de `salida/sede.json` (el formato de `gestoria sede`)."""
    return {"no_leidas": a.get("no_leidas"), "notificaciones": a.get("notificaciones") or [],
            "obligaciones": a.get("obligaciones") or [], "presentados": a.get("presentados") or {},
            "errores": a.get("errores") or {}}


def ejecutar(carpeta: Path, hoy: date | None = None, personal: bool = True, dehu: bool = True,
             terceros: bool = True, cotejar: bool = True) -> dict:
    """El chequeo entero. Devuelve {"datos", "hallazgos", "nivel", "informe"}."""
    from gestoria import certificado, cotejo, libros, perfil as perfilmod, seguridad_social, terceros as ter
    from gestoria.modelos import m303
    from gestoria.navegador import Navegador

    hoy = hoy or date.today()
    carpeta = Path(carpeta)
    pf = perfilmod.cargar(carpeta)
    ventas, compras = libros.cargar(carpeta)
    aj = libros.ajustes(carpeta)
    salida = carpeta / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    datos: dict = {"fecha": hoy.isoformat(), "perfil": {"nif": pf.nif, "nombre": pf.nombre, "tipo": pf.tipo},
                   "certificados": {"principal": _cert_info(pf, "principal"), "personal": _cert_info(pf, "personal")}}
    if not pf.tiene_certificado("principal"):
        raise ValueError("perfil.toml no tiene [sede] certificado: el chequeo necesita tu certificado")
    pfx, clave = pf.ruta_certificado("principal"), pf.clave_certificado("principal")
    with Navegador(pfx, clave, capturas=salida / "capturas") as nav:
        datos["aeat"] = aeat.consultar(nav, ("notificaciones", "censo", "obligaciones", "poderes", "deudas", "expedientes",
                                             "alertas", "accesos", "presentados", "roi", "datos_fiscales", "domiciliaciones"),
                                       nif=pf.nif, es_sociedad=pf.tipo == "sl",
                                       modelos=tuple(dict.fromkeys(m for m in pf.modelos + ["303", "036"] if m in aeat.MODELOS_PRESENTADOS)))
        if cotejar and "303" in pf.modelos:
            datos["cotejos"] = []
            for f in [x for x in (datos["aeat"].get("presentados") or {}).get("303", []) if x["estado"] != "BAJA"][-4:]:
                ej, per = int(f["ejercicio"]), f["periodo"]
                c = {"ejercicio": ej, "periodo": per, "expediente": f["expediente"]}
                try:
                    bajado = aeat.descargar_presentado(nav, "303", ej, per, salida / "presentado")
                    if bajado.get("justificante"):
                        c.update({k: v for k, v in aeat.leer_justificante(bajado["justificante"]).items()
                                  if k in ("presentador", "presentador_nif", "en_calidad_de", "presentada", "csv", "resultado")})
                    desde, hasta = m303.periodo_fechas(ej, per)
                    borrador, _ = m303.casillas(ventas, compras, desde, hasta, Decimal(str(aj.get("compensar_pendiente", "0"))))
                    c["difs"] = cotejo.cotejar_303(cotejo.leer_presentado(Path(bajado["fichero"])), borrador)
                except Exception as e:
                    c["error"] = error_corto(e)
                datos["cotejos"].append(c)
    if dehu:
        datos["dehu"] = dehu_aparte(pfx, clave)
    if terceros:
        pares = ter.de_los_libros(ventas, compras)
        try:
            filas = ter.comprobar([(n, m) for n, m, _ in pares], certificado.contexto_tls(pfx, clave)) if pares else []
            datos["terceros"] = {"filas": filas, "hallazgos": ter.hallazgos(filas, {n: p for n, _, p in pares})}
        except Exception as e:
            datos["terceros"] = {"error": error_corto(e)}
    if personal and pf.tiene_certificado("personal"):
        datos["personal"] = {}
        ppfx, pclave = pf.ruta_certificado("personal"), pf.clave_certificado("personal")
        with Navegador(ppfx, pclave, capturas=salida / "capturas") as nav:
            datos["personal"]["aeat"] = aeat.consultar(nav, ("notificaciones", "censo", "obligaciones", "poderes", "deudas",
                                                             "alertas", "datos_fiscales"), es_sociedad=False)
            try:
                datos["personal"]["seguridad_social"] = seguridad_social.consultar(nav)
            except Exception as e:
                datos["personal"]["seguridad_social"] = {"error": error_corto(e)}
        if dehu:
            datos["personal"]["dehu"] = dehu_aparte(ppfx, pclave)
    hallazgos = evaluar(datos, pf, ventas, compras, hoy)
    informe = salida / f"chequeo_{hoy.isoformat()}.md"
    informe.write_text(markdown(datos, hallazgos, pf), encoding="utf-8")
    datos["hallazgos"] = [asdict(h) for h in hallazgos]
    datos["nivel"] = nivel_general(hallazgos)
    (salida / "chequeo.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    foto = _foto_compat(datos["aeat"])
    foto["actualizado"] = datetime.now().isoformat(timespec="seconds")
    foto["dehu_pendientes"] = len((datos.get("dehu") or {}).get("pendientes") or [])
    foto["deudas"] = ((datos["aeat"].get("deudas") or {}).get("estado"))
    if datos.get("personal"):
        foto["personal_no_leidas"] = (datos["personal"].get("aeat") or {}).get("no_leidas")
        foto["personal_dehu_pendientes"] = len((datos["personal"].get("dehu") or {}).get("pendientes") or [])
    (salida / "sede.json").write_text(json.dumps(foto, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return {"datos": datos, "hallazgos": hallazgos, "nivel": datos["nivel"], "informe": str(informe)}
