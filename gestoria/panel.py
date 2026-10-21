"""El panel de cada mañana (`gestoria hoy`): en una pantalla, lo que un gestor miraría por ti.

Semáforo general: 🔴 si vence algo obligatorio en 3 días o menos, hay una notificación sin abrir
(AEAT o DEHú), una deuda, un error en los libros registro o el certificado caduca en 15 días;
🟡 si algo vence en 15 días, hay avisos, el certificado caduca en 60 días o el último chequeo
dejó cosas por revisar; 🟢 si no. Cada bloque sale de un módulo con su fuente (calendario
oficial, hucha, revisar, umbrales, sede, certificado).
No sale a la red salvo para el calendario de la AEAT (una vez al día); la sede se lee de la
última foto guardada por `gestoria vigia`, `gestoria chequeo` o `gestoria sede`.
"""
from __future__ import annotations

import json
import re
import textwrap
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from gestoria import banco, calendario, hucha, libros, perfil, revisar, umbrales
from gestoria.numeros import eur

ROJO, AMARILLO, VERDE = "🔴", "🟡", "🟢"
_TRIM = {"primer": "1T", "segundo": "2T", "tercer": "3T", "cuarto": "4T"}


def foto_sede(carpeta: Path) -> dict | None:
    f = Path(carpeta) / "salida" / "sede.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def foto_chequeo(carpeta: Path) -> dict | None:
    f = Path(carpeta) / "salida" / "chequeo.json"
    if not f.is_file():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    hs = d.get("hallazgos") or []
    return {"fecha": d.get("fecha"), "nivel": d.get("nivel"), "rojos": sum(1 for h in hs if h.get("nivel") == "🔴"),
            "amarillos": sum(1 for h in hs if h.get("nivel") == "🟡")}


def certificados_de(pf) -> list[dict]:
    """Caducidad de los certificados del perfil, leída en local (sin red)."""
    from gestoria import chequeo

    out = []
    for cual in ("principal", "personal"):
        info = chequeo._cert_info(pf, cual) if pf.tiene_certificado(cual) else None
        if info:
            out.append({"cual": cual, **info})
    return out


def presentados_de(sede: dict | None) -> set[tuple[int, str]]:
    """(ejercicio, periodo) de los 303 y 130 que la sede da por presentados."""
    out = set()
    for modelo in ("303", "130"):
        for fila in (sede or {}).get("presentados", {}).get(modelo, []):
            try:
                out.add((int(fila["ejercicio"]), fila["periodo"]))
            except (KeyError, ValueError):
                pass
    return out


def _periodo_del_plazo(texto: str) -> tuple[int, str] | None:
    m = re.search(r"(primer|segundo|tercer|cuarto) trimestre (\d{4})", texto, re.I)
    return (int(m.group(2)), _TRIM[m.group(1).lower()]) if m else None


def construir(carpeta: Path, hoy: date | None = None, calendario_ics: dict | None = None,
              sede: dict | None = None, saldo: Decimal | None = None, certificados: list[dict] | None = None,
              chequeo: dict | None = None) -> dict:
    hoy = hoy or date.today()
    carpeta = Path(carpeta)
    pf = perfil.cargar(carpeta)
    ventas, compras = libros.cargar(carpeta)
    aj = libros.ajustes(carpeta)
    sede = sede if sede is not None else foto_sede(carpeta)
    presentados = presentados_de(sede)
    d: dict = {"hoy": hoy, "perfil": pf, "nivel": VERDE, "plazos": [], "plazos_error": None,
               "hucha": [], "hallazgos": [], "terceros_347": [], "umbrales": [], "sede": sede,
               "n_ventas": len(ventas), "n_compras": len(compras), "saldo": saldo,
               "certificados": certificados if certificados is not None else certificados_de(pf),
               "chequeo": chequeo if chequeo is not None else foto_chequeo(carpeta)}

    # Plazos del calendario oficial; sin red, los de la hucha (por norma)
    try:
        filas, _ = calendario.plazos(pf, hoy, hoy + timedelta(days=120), calendario_ics)
        for p in filas:
            dias = (p.fecha - hoy).days
            per = _periodo_del_plazo(p.texto)
            hecho = p.modelo in ("303", "130") and per is not None and per in presentados
            nivel = "✅" if hecho else (ROJO if dias <= 3 else AMARILLO if dias <= 15 else VERDE) if p.obligatorio else "· "
            d["plazos"].append({"fecha": p.fecha, "dias": dias, "modelo": p.modelo, "texto": p.texto,
                                "obligatorio": p.obligatorio, "condicion": p.condicion, "nivel": nivel, "presentado": hecho})
    except Exception as e:  # sin red
        d["plazos_error"] = f"{type(e).__name__}: {e}"

    d["banco"] = banco.resumen(carpeta, ventas, compras, hoy)
    if saldo is None and d["banco"] and d["banco"].get("saldo") is not None:
        d["saldo"], d["saldo_de_banco"] = d["banco"]["saldo"], True
    d["hucha"] = hucha.calcular(pf, ventas, compras, aj, hoy, presentados)
    d["total_hucha"] = hucha.total(d["hucha"])
    d["hallazgos"] = revisar.revisar(ventas, compras, hoy)
    d["terceros_347"] = umbrales.radar_347(ventas, compras, hoy.year)
    d["umbrales"] = umbrales.umbrales(pf, ventas, hoy.year)

    for c in d["certificados"]:
        c["dias"] = (date.fromisoformat(c["hasta"]) - hoy).days if c.get("hasta") else None
    s_ = sede or {}
    rojo = any(p["nivel"] == ROJO for p in d["plazos"]) or any(h.nivel == "error" for h in d["hallazgos"]) \
        or bool(s_.get("no_leidas")) or bool(s_.get("dehu_pendientes")) or bool(s_.get("personal_no_leidas")) \
        or bool(s_.get("personal_dehu_pendientes")) or s_.get("deudas") == "con_deudas" \
        or any(c["dias"] is not None and c["dias"] <= 15 for c in d["certificados"])
    amarillo = any(p["nivel"] == AMARILLO for p in d["plazos"]) or bool(d["hallazgos"]) or d["plazos_error"] is not None \
        or any(c["dias"] is not None and c["dias"] <= 60 for c in d["certificados"]) \
        or bool((d["chequeo"] or {}).get("rojos") or (d["chequeo"] or {}).get("amarillos")) \
        or bool((d["banco"] or {}).get("por_explicar"))
    d["nivel"] = ROJO if rojo else AMARILLO if amarillo else VERDE
    return d


def _edad(iso: str | None, hoy: date) -> str:
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    horas = (datetime.combine(hoy, datetime.max.time()) - t).total_seconds() / 3600
    return f"hace {int(horas)} h" if horas < 48 else f"hace {int(horas // 24)} días"


def render(d: dict) -> str:
    pf, hoy = d["perfil"], d["hoy"]
    L = [f"{d['nivel']} GestorIA · {calendario.fecha_txt(hoy)} · {pf.nombre} ({pf.nif}) · "
         f"{'SL' if pf.tipo == 'sl' else 'autónomo'} · IVA {pf.iva_regimen.upper()}", "━" * 78]

    L.append("📅 Plazos")
    if d["plazos_error"]:
        L.append(f"   ⚠️ sin calendario de la AEAT ({d['plazos_error'][:60]}); las fechas de abajo son por norma")
    oblig = [p for p in d["plazos"] if p["obligatorio"]]
    for p in oblig[:6]:
        L.append(f"   {p['nivel']} {calendario.fecha_txt(p['fecha'])} (en {p['dias']:>3} d)  {p['modelo']}  "
                 f"{p['texto'][:60]}{'  — presentado según la sede' if p['presentado'] else ''}")
    cond = sorted({p["modelo"] for p in d["plazos"] if not p["obligatorio"]})
    if cond:
        L.append(f"   ·  condicionales en 120 días: {', '.join(cond)} (`gestoria calendario` los explica)")
    if not d["plazos"] and not d["plazos_error"]:
        L.append("   nada obligatorio en 120 días")

    tienes = "en el banco" if d.get("saldo_de_banco") else "tienes"
    L.append(f"\n💰 Hucha: aparta {eur(d['total_hucha'])}"
             + (f" · {tienes} {eur(d['saldo'])} → {'te sobran ' + eur(d['saldo'] - d['total_hucha']) if d['saldo'] >= d['total_hucha'] else 'TE FALTAN ' + eur(d['total_hucha'] - d['saldo'])}" if d["saldo"] is not None else ""))
    for p in d["hucha"]:
        L.append(f"   {eur(p.importe):>14}  {p.modelo:<4} {p.concepto[:48]:<48} → {calendario.fecha_txt(p.vence)}")
        for i, linea in enumerate(textwrap.wrap(p.nota, 88)[:3]):
            L.append(f"   {'':14}  {'↳' if i == 0 else ' '} {linea}")

    errores = [h for h in d["hallazgos"] if h.nivel == "error"]
    avisos = [h for h in d["hallazgos"] if h.nivel == "aviso"]
    L.append(f"\n🧾 Libros registro: {d['n_ventas']} facturas emitidas, {d['n_compras']} recibidas · "
             + (f"❌ {len(errores)} error(es), ⚠️ {len(avisos)} aviso(s)" if d["hallazgos"] else "✅ sin hallazgos"))
    for h in d["hallazgos"][:4]:
        L.append(f"   {str(h)[:100]}")
    if len(d["hallazgos"]) > 4:
        L.append(f"   … y {len(d['hallazgos']) - 4} más (`gestoria revisar`)")

    L.append("\n📡 Radares")
    if d["terceros_347"]:
        for t in d["terceros_347"][:4]:
            L.append(f"   347 → {t.nombre} {('(' + t.nif + ') ') if t.nif else ''}entregas {eur(t.entregas)}, "
                     f"adquisiciones {eur(t.adquisiciones)}: va en el 347 de febrero")
    else:
        L.append("   347: ningún tercero pasa de 3.005,06 € este año")
    for u in d["umbrales"]:
        L.append(f"   {umbrales.barra(u.pct)} {u.pct:>3} %  {u.nombre}: {eur(u.medido)} de {eur(u.limite)}")

    b = d.get("banco")
    if b and b.get("error"):
        L.append(f"\n🏦 Banco: ⚠️ no puedo leer un extracto de banco/ ({b['error'][:70]})")
    elif b:
        L.append(f"\n🏦 Banco: saldo {eur(b['saldo'])} el {calendario.fecha_txt(b['fecha'])} · {b['casados']} movimientos casados con su factura"
                 + (f" · 🟡 {b['por_explicar']} por explicar (`gestoria banco`)" if b["por_explicar"] else " · ✅ nada por explicar")
                 if b.get("saldo") is not None else f"\n🏦 Banco: {b['casados']} movimientos casados"
                 + (f" · 🟡 {b['por_explicar']} por explicar (`gestoria banco`)" if b["por_explicar"] else ""))

    s = d["sede"]
    if s is None:
        L.append("\n🏛️ Sede: sin foto reciente (`gestoria vigia` o `gestoria chequeo` con tu certificado)")
    else:
        nl = s.get("no_leidas")
        estado = "✅ sin notificaciones pendientes" if nl == 0 else f"🔴 {nl} sección(es) con notificaciones SIN LEER" if nl else "⚠️ resumen ilegible"
        L.append(f"\n🏛️ Sede: {estado} ({_edad(s.get('actualizado'), hoy)})")
        for n in s.get("notificaciones") or []:
            if not n.get("leida"):
                L.append(f"   🔴 {n.get('concepto')} · emitida {n.get('emitida')} — no la abras sin decidirlo: arranca los plazos")
        if s.get("dehu_pendientes"):
            L.append(f"   🔴 DEHú: {s['dehu_pendientes']} notificación(es) pendiente(s) de otras administraciones (`gestoria dehu`)")
        if s.get("deudas") == "con_deudas":
            L.append("   🔴 deudas pendientes con la AEAT (`gestoria deudas`)")
        if s.get("personal_no_leidas") or s.get("personal_dehu_pendientes"):
            L.append(f"   🔴 con tu certificado personal: {s.get('personal_no_leidas') or 0} sin leer en la AEAT, "
                     f"{s.get('personal_dehu_pendientes') or 0} en la DEHú (`gestoria notificaciones --personal`)")
    for c in d["certificados"]:
        if c.get("error"):
            L.append(f"🔐 Certificado {'personal' if c['cual'] == 'personal' else ''}: ⚠️ no se puede leer ({c['error'][:60]})")
            continue
        dias = c["dias"]
        marca = ROJO if dias is not None and dias <= 15 else AMARILLO if dias is not None and dias <= 60 else "✅"
        L.append(f"🔐 Certificado {'personal' if c['cual'] == 'personal' else 'de ' + (c.get('entidad') or c.get('titular') or '')}: "
                 f"{marca} caduca el {calendario.fecha_txt(date.fromisoformat(c['hasta']))} (en {dias} días)")
    ch = d["chequeo"]
    if ch:
        L.append(f"🩺 Último chequeo ({ch['fecha']}): {ch['nivel']} {ch['rojos']} urgente(s), {ch['amarillos']} por revisar (`gestoria chequeo`)")
    return "\n".join(L)


def markdown(d: dict) -> str:
    """El mismo panel, en Markdown, para los informes y el correo."""
    t = render(d)
    cuerpo = t.split("\n", 2)[2] if t.count("\n") >= 2 else t
    return f"# {t.splitlines()[0]}\n\n```\n{cuerpo}\n```\n"
