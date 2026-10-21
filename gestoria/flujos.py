"""Flujos de trabajo del gestor: varias órdenes encadenadas, pensadas para programarlas.

- `semana` (lunes): el panel de `hoy` más la lista de lo que toca hacer esta semana, en Markdown.
- `trimestre` (día 2 de enero, abril, julio y octubre): el cierre del IVA del último trimestre
  cerrado → borrador del 303, fichero para «Importar», validación en el simulador de la AEAT,
  plazo oficial y resumen.
- `anual` (enero): el año entero por trimestres, el IS o el IRPF estimado, el radar del 347 y
  el calendario de enero a julio (fiscal y, para una SL, mercantil).
Ninguno presenta nada: el último paso lo hace la persona en la sede.
Programarlos: `workflows/crontab.ejemplo`.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


def ultimo_trimestre_cerrado(hoy: date) -> tuple[int, str]:
    n = (hoy.month - 1) // 3  # trimestres enteros ya cerrados este año
    return (hoy.year - 1, "4T") if n == 0 else (hoy.year, f"{n}T")


def trimestre(carpeta: Path, ejercicio: int, periodo: str, validar: bool = True,
              salida: Path | None = None, calendario_ics: dict | None = None) -> dict:
    from gestoria import calendario, libros, perfil, sede
    from gestoria.modelos import m303

    carpeta = Path(carpeta)
    salida = Path(salida) if salida else carpeta / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    pf = perfil.cargar(carpeta)
    ventas, compras = libros.cargar(carpeta)
    aj = libros.ajustes(carpeta)
    desde, hasta = m303.periodo_fechas(ejercicio, periodo)
    cas, avisos = m303.casillas(ventas, compras, desde, hasta,
                                Decimal(str(aj.get("compensar_pendiente", "0"))))
    fichero = salida / f"303_{ejercicio}_{periodo}.txt"
    fichero.write_text(m303.generar_fichero(pf, ejercicio, periodo, cas), encoding="latin-1")

    val = None
    if validar:
        try:
            val = sede.validar("303", ejercicio, fichero, salida / "capturas")
        except Exception as e:  # sin Playwright o sin red: el resumen lo dice
            val = {"fallo": f"{type(e).__name__}: {e}"}

    plazo = None
    try:
        filas, _ = calendario.plazos(pf, hasta, hasta + timedelta(days=45), calendario_ics)
        plazo = next((p for p in filas if p.modelo == "303"), None)
    except Exception:  # sin red: el resumen lo dice
        pass

    md = _resumen(pf, ejercicio, periodo, cas, avisos, fichero, val, plazo, aj)
    resumen = salida / f"trimestre_{ejercicio}_{periodo}.md"
    resumen.write_text(md, encoding="utf-8")
    return {"casillas": cas, "avisos": avisos, "fichero": str(fichero), "validacion": val,
            "plazo": plazo, "resumen": str(resumen)}


def _resumen(pf, ejercicio, periodo, cas, avisos, fichero, val, plazo, aj) -> str:
    from gestoria import calendario

    l = [f"# 303 · {periodo} {ejercicio} · {pf.nombre} ({pf.nif})", "",
         "**Borrador. GestorIA no presenta nada:** importa el fichero en el formulario del 303 "
         "de la sede, revísalo y preséntalo tú.", ""]
    if plazo:
        l += [f"**Plazo:** {calendario.fecha_txt(plazo.fecha)} ({plazo.texto}; calendario oficial de la AEAT).", ""]
    else:
        l += ["**Plazo:** no he podido leer el calendario de la AEAT; compruébalo con `gestoria calendario`.", ""]
    l += ["| casilla | importe |", "|---|---|"]
    l += [f"| [{k}] | {cas[k]} |" for k in sorted(cas, key=int) if cas[k] and k != "65"]
    l += ["", f"Saldo a compensar de periodos anteriores [110]: {aj.get('compensar_pendiente', '0')}"
          f" — fuente: {aj.get('fuente', 'sin indicar en ajustes.toml')}", ""]
    if avisos:
        l += ["## Avisos", ""] + [f"- ⚠️ {a}" for a in avisos] + [""]
    l += ["## Validación en el simulador de la AEAT", ""]
    if val is None:
        l.append("No validado (se pidió sin validar).")
    elif "fallo" in val:
        l.append(f"No validado: {val['fallo']}. Ejecuta `gestoria validar 303 {fichero} --ejercicio {ejercicio}`.")
    else:
        l.append("✅ «No existen errores»." if val.get("sin_errores") else "❌ Con errores:")
        l += [f"- ❌ {e}" for e in val["errores"]] + [f"- ⚠️ {w}" for w in val["avisos"]]
        if val.get("casillas_aeat"):
            l.append(f"- El formulario de la AEAT da [71] = {val['casillas_aeat'].get('71')}.")
    l += ["", f"Fichero para «Importar»: `{fichero}`", ""]
    return "\n".join(l)


def semana(carpeta: Path, hoy: date | None = None, salida: Path | None = None,
           calendario_ics: dict | None = None, sede: dict | None = None) -> dict:
    """El panel más la lista de tareas de la semana. Devuelve el nivel del semáforo y la ruta."""
    from gestoria import calendario, panel
    from gestoria.numeros import eur

    hoy = hoy or date.today()
    carpeta = Path(carpeta)
    salida = Path(salida) if salida else carpeta / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    d = panel.construir(carpeta, hoy, calendario_ics, sede)
    tareas = []
    for p in d["plazos"]:
        if p["obligatorio"] and not p["presentado"] and p["dias"] <= 15:
            tareas.append(f"{p['nivel']} Presentar el {p['modelo']} antes del {calendario.fecha_txt(p['fecha'])}"
                          f" ({p['texto'][:50]}): `gestoria trimestre` si es el 303")
    for h in d["hallazgos"]:
        if h.nivel == "error":
            tareas.append(f"❌ Corregir en los libros: {h.donde}: {h.texto}")
    if (d["sede"] or {}).get("no_leidas"):
        tareas.append("🔴 Hay notificaciones de Hacienda sin leer: decide si abrirla (arranca los plazos)")
    if d["sede"] is None:
        tareas.append("· Hacer una foto de la sede: `gestoria sede`")
    faltan = d["total_hucha"]
    tareas.append(f"💰 Tener apartados {eur(faltan)} para lo que vence (detalle arriba)")
    for t in d["terceros_347"][:3]:
        tareas.append(f"📡 {t.nombre} ya supera 3.005,06 €: irá en el 347 de febrero; guarda sus facturas")
    md = panel.markdown(d) + "\n## Esta semana\n\n" + "\n".join(f"- {t}" for t in tareas) + "\n"
    f = salida / f"semana_{hoy.isocalendar()[0]}-W{hoy.isocalendar()[1]:02d}.md"
    f.write_text(md, encoding="utf-8")
    return {"nivel": d["nivel"], "resumen": str(f), "tareas": tareas, "panel": d}


def anual(carpeta: Path, ejercicio: int, salida: Path | None = None) -> dict:
    """El año en una hoja: IVA por trimestres, resultado, IS o IRPF estimado, 347 y el calendario del cierre."""
    from gestoria import calendario, hucha, libros, perfil, plazos, umbrales
    from gestoria.modelos import m303
    from gestoria.numeros import eur

    carpeta = Path(carpeta)
    salida = Path(salida) if salida else carpeta / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    pf = perfil.cargar(carpeta)
    ventas, compras = libros.cargar(carpeta)
    aj = libros.ajustes(carpeta)
    l = [f"# Cierre {ejercicio} · {pf.nombre} ({pf.nif}) · {'SL' if pf.tipo == 'sl' else 'autónomo'}", "",
         "Estimaciones hechas con los libros; **nada de esto está presentado**.", "",
         "## IVA por trimestres", "", "| trimestre | devengado [27] | deducible [45] | resultado [71] |", "|---|---|---|---|"]
    compensar = Decimal(str(aj.get("compensar_pendiente", "0")))
    iva_total = Decimal(0)
    for n in range(1, 5):
        per = f"{n}T"
        desde, hasta = m303.periodo_fechas(ejercicio, per)
        try:
            cas, _ = m303.casillas(ventas, compras, desde, hasta, compensar)
            l.append(f"| {per} | {eur(cas.get('27', 0))} | {eur(cas.get('45', 0))} | {eur(cas.get('71', 0))} |")
            iva_total += cas.get("71", Decimal(0))
            compensar = cas.get("87", Decimal(0)) + (-cas["71"] if cas.get("71", 0) < 0 else 0)
        except ValueError as e:
            l.append(f"| {per} | — | — | no calculable: {e} |")
    l += ["", f"IVA del año (suma de resultados): {eur(iva_total)}", ""]
    ingresos, gastos, avisos = hucha.ingresos_gastos(ventas, compras, date(ejercicio, 1, 1), date(ejercicio + 1, 1, 1))
    base = ingresos - gastos
    l += ["## Resultado", "", f"- Ingresos sin IVA: {eur(ingresos)}", f"- Gastos (sin inversiones): {eur(gastos)}",
          f"- Resultado: {eur(base)}"]
    if pf.tipo == "sl":
        cuota, tipo, fuente = hucha.tipo_is(pf, ejercicio, base)
        l += [f"- **Impuesto sobre Sociedades estimado: {eur(cuota)}** ({tipo}; {fuente}), a presentar hasta el "
              f"{calendario.fecha_txt(plazos.vence('200', ejercicio))}"]
    else:
        l += [f"- Rendimiento neto estimado: {eur(base)}; los 130 del año adelantan el 20 % ({eur(max(base, 0) * Decimal('0.2'))});"
              f" la renta (abril-junio de {ejercicio + 1}) ajusta según tu situación personal"]
    l += [f"- ⚠️ {a}" for a in avisos[:5]] + [""]
    terceros = umbrales.radar_347(ventas, compras, ejercicio)
    l += ["## Modelo 347 (febrero)", ""]
    l += [f"- {t.nombre}{(' (' + t.nif + ')') if t.nif else ''}: entregas {eur(t.entregas)}, adquisiciones {eur(t.adquisiciones)}"
          for t in terceros] or ["- Ningún tercero supera 3.005,06 €: no hay que presentarlo (art. 33.1 RGAT)"]
    l += ["", "## Umbrales", ""]
    l += [f"- {umbrales.barra(u.pct)} {u.pct} % · {u.nombre}: {eur(u.medido)} de {eur(u.limite)} ({u.fuente})"
          for u in umbrales.umbrales(pf, ventas, ejercicio)]
    l += ["", f"## Calendario del cierre de {ejercicio}", "",
          f"- {calendario.fecha_txt(plazos.vence('303', ejercicio, '4T'))}: 303 del 4T y 390 (resumen anual del IVA)"]
    if pf.tipo == "autonomo":
        l += [f"- {calendario.fecha_txt(plazos.vence('130', ejercicio, '4T'))}: 130 del 4T",
              f"- {calendario.fecha_txt(plazos.vence('347', ejercicio))}: 347, si hay terceros que lo pidan",
              f"- abril a junio de {ejercicio + 1}: renta (modelo 100), hasta el {calendario.fecha_txt(plazos.vence('100', ejercicio))}"]
    else:
        l += [f"- {calendario.fecha_txt(plazos.vence('347', ejercicio))}: 347, si hay terceros que lo pidan",
              f"- 31-mar-{ejercicio + 1}: formular las cuentas anuales (art. 253.1 LSC)",
              f"- 30-abr-{ejercicio + 1}: legalizar los libros en el Registro Mercantil (art. 18 Ley 14/2013)",
              f"- 30-jun-{ejercicio + 1}: aprobar las cuentas (art. 164.1 LSC)",
              f"- un mes después de aprobarlas: depositarlas en el Registro (art. 279.1 LSC)",
              f"- {calendario.fecha_txt(plazos.vence('200', ejercicio))}: Impuesto sobre Sociedades (art. 124.1 LIS)"]
    l.append("")
    f = salida / f"anual_{ejercicio}.md"
    f.write_text("\n".join(l), encoding="utf-8")
    return {"resumen": str(f), "ingresos": ingresos, "gastos": gastos, "iva": iva_total, "terceros": terceros}


def vigia(carpeta: Path, hoy: date | None = None, dehu: bool = True) -> dict:
    """El vigía de cada día: notificaciones de la AEAT y de la DEHú, deudas, alertas de la sede y
    la caducidad del certificado, con los dos certificados si los hay. Solo lectura. Compara con
    la pasada anterior (`salida/vigia.json`) y marca lo NUEVO, para que el cron avise una vez.
    Código de salida en la orden: 2 si hay algo rojo nuevo, 1 si sigue habiendo algo rojo, 0 si no."""
    import json
    from dataclasses import asdict
    from datetime import datetime

    from gestoria import aeat, chequeo, perfil
    from gestoria.navegador import Navegador

    hoy = hoy or date.today()
    carpeta = Path(carpeta)
    salida = carpeta / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    pf = perfil.cargar(carpeta)
    if not pf.tiene_certificado("principal"):
        raise ValueError("perfil.toml no tiene [sede] certificado: el vigía necesita tu certificado")
    anterior_chequeo = {}
    if (salida / "chequeo.json").is_file():
        anterior_chequeo = json.loads((salida / "chequeo.json").read_text(encoding="utf-8"))
    datos: dict = {"fecha": hoy.isoformat(), "certificados": {"principal": chequeo._cert_info(pf, "principal"),
                                                              "personal": chequeo._cert_info(pf, "personal")}}
    que = ("notificaciones", "alertas", "deudas")
    pfx, clave = pf.ruta_certificado("principal"), pf.clave_certificado("principal")
    with Navegador(pfx, clave, sitios=("aeat",)) as nav:
        datos["aeat"] = aeat.consultar(nav, que)
    if dehu:
        datos["dehu"] = chequeo.dehu_aparte(pfx, clave)
    if pf.tiene_certificado("personal"):
        ppfx, pclave = pf.ruta_certificado("personal"), pf.clave_certificado("personal")
        datos["personal"] = {}
        with Navegador(ppfx, pclave, sitios=("aeat",)) as nav:
            datos["personal"]["aeat"] = aeat.consultar(nav, que)
        if dehu:
            datos["personal"]["dehu"] = chequeo.dehu_aparte(ppfx, pclave)
    # el censo del último chequeo dice si las notificaciones electrónicas son obligatorias
    if anterior_chequeo.get("aeat", {}).get("censo"):
        datos["aeat"]["censo"] = anterior_chequeo["aeat"]["censo"]
    if datos.get("personal") and (anterior_chequeo.get("personal") or {}).get("aeat", {}).get("censo"):
        datos["personal"]["aeat"]["censo"] = anterior_chequeo["personal"]["aeat"]["censo"]
    hallazgos = chequeo.evaluar_vigia(datos, pf, hoy)
    previo = salida / "vigia.json"
    ya = set(json.loads(previo.read_text(encoding="utf-8")).get("rojos", [])) if previo.is_file() else set()
    rojos = [str(h) for h in hallazgos if h.nivel == "🔴"]
    nuevos = [r for r in rojos if r not in ya]
    previo.write_text(json.dumps({"fecha": datetime.now().isoformat(timespec="seconds"), "rojos": rojos,
                                  "hallazgos": [asdict(h) for h in hallazgos]}, ensure_ascii=False, indent=1), encoding="utf-8")
    sede = salida / "sede.json"
    foto = json.loads(sede.read_text(encoding="utf-8")) if sede.is_file() else {}
    foto.update({"no_leidas": datos["aeat"].get("no_leidas"), "notificaciones": datos["aeat"].get("notificaciones") or [],
                 "actualizado": datetime.now().isoformat(timespec="seconds"),
                 "dehu_pendientes": len((datos.get("dehu") or {}).get("pendientes") or []),
                 "deudas": (datos["aeat"].get("deudas") or {}).get("estado")})
    if datos.get("personal"):
        foto.update({"personal_no_leidas": (datos["personal"].get("aeat") or {}).get("no_leidas"),
                     "personal_dehu_pendientes": len((datos["personal"].get("dehu") or {}).get("pendientes") or [])})
    foto.setdefault("presentados", {})
    sede.write_text(json.dumps(foto, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    with open(salida / "vigia.log", "a", encoding="utf-8") as log:
        log.write(f"{datetime.now().isoformat(timespec='seconds')} {chequeo.nivel_general(hallazgos)} "
                  f"{len(rojos)} rojo(s), {len(nuevos)} nuevo(s)\n")
    return {"hallazgos": hallazgos, "nuevos": nuevos, "rojos": rojos, "nivel": chequeo.nivel_general(hallazgos), "datos": datos}
