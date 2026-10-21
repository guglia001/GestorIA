"""El panel de control contable en el navegador: `gestoria web`.

Una sola página, sin nada de internet (son tus cuentas): todo va dentro del HTML. Lleva el resumen
del día (semáforo, plazos, hucha y avisos), el libro diario, el extracto de cada cuenta (mayor),
sumas y saldos, pérdidas y ganancias, el balance de situación, el libro de IVA, la facturación con
su estado de cobro y pago, los terceros (cuánto a cada cliente y a cada proveedor, con el radar del
347), el 303 de cada trimestre con el nombre de cada casilla, los radares de los umbrales y el banco
conciliado. Cada tabla se baja en CSV (separado por «;», el que abre Excel en español) para dársela
a una gestoría, y cada vista se imprime o se guarda en PDF.

`gestoria web` la sirve en http://127.0.0.1:8640, solo en tu equipo, y la rehace con cada recarga.
Con `--fichero` solo la escribe en salida/web/index.html. Todo sale de los mismos módulos que las
órdenes: `contabilidad` (asientos y estados), `panel` (el día y los radares), `banco`
(conciliación), `m303` y `cotejo` (los nombres de las casillas).
«Facturación» enseña las facturas de tu programa de facturación: GestorIA no las emite, porque un
programa que emite facturas tiene que cumplir el reglamento de Verifactu (RD 1007/2023).
"""
from __future__ import annotations

import datetime as _dt
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

PUERTO = 8640


def _plano(x):
    """Decimal, date… → lo que entiende JSON."""
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, _dt.date):
        return x.isoformat()
    if isinstance(x, dict):
        return {str(k): _plano(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plano(v) for v in x]
    return x


def datos(carpeta: Path, hoy: date | None = None, calendario_ics: dict | None = None, sede: dict | None = None) -> dict:
    from gestoria import banco, contabilidad as ct, cotejo, hucha, libros, panel, perfil
    from gestoria.modelos import m303

    hoy = hoy or date.today()
    c = Path(carpeta)
    pf = perfil.cargar(c)
    ventas, compras = libros.cargar(c)
    aj = libros.ajustes(c)
    extractos = banco.cargar(c)
    k = ct.generar(pf, ventas, compras, aj, hoy.year, hoy, extractos)
    p = panel.construir(c, hoy, calendario_ics, sede)
    conc = banco.conciliar(extractos, ventas, compras, hoy) if extractos else None
    pyg = ct.perdidas_y_ganancias(k)
    base_is = pyg[-1][1]
    cuota_is, tipo_is, fuente_is = (hucha.tipo_is(pf, hoy.year, base_is) if pf.tipo == "sl" else (None, "", ""))

    meses = {}
    for a in k.asientos:
        m = meses.setdefault(a.fecha.strftime("%Y-%m"), {"ingresos": Decimal(0), "gastos": Decimal(0)})
        for x in a.apuntes:
            if x.cuenta.startswith("7"):
                m["ingresos"] += x.haber - x.debe
            elif x.cuenta.startswith("6"):
                m["gastos"] += x.debe - x.haber

    trimestres = []
    for n in range(1, 5):
        d, h = m303.periodo_fechas(hoy.year, f"{n}T")
        if d > hoy:
            break
        cas, avisos = m303.casillas(ventas, compras, d, h, Decimal(str(aj.get("compensar_pendiente", "0"))) if n == 1 else Decimal(0))
        trimestres.append({"periodo": f"{n}T", "cerrado": h <= hoy, "casillas": {x: cas[x] for x in sorted(cas, key=int) if cas[x]},
                           "resultado": cas.get("71", Decimal(0)), "avisos": avisos})

    cobro = {id(f): m for m, f in (conc.casados if conc else [])}
    estado = lambda f: ({"estado": "cobrada" if hasattr(f, "cliente") else "pagada", "fecha_banco": cobro[id(f)].fecha}
                        if id(f) in cobro else {"estado": "pendiente", "dias": (hoy - f.fecha).days})
    iva = ct.libro_iva(ventas, compras, hoy.year)
    facturas = {"emitidas": [{**x, **estado(v)} for x, v in zip(iva["emitidas"], sorted(
                    (v for v in ventas if v.fecha.year == hoy.year), key=lambda v: (v.fecha, v.factura)))],
                "recibidas": [{**x, **estado(f), "cuenta": ct.cuenta_de_compra(f, {str(a): str(b) for a, b in (aj.get("cuentas") or {}).items()})}
                              for x, f in zip(iva["recibidas"], sorted((f for f in compras if f.fecha.year == hoy.year),
                                                                     key=lambda f: (f.fecha, f.factura)))]}
    movimientos = []
    if conc:
        for m, f in conc.casados:
            movimientos.append({"fecha": m.fecha, "importe": m.importe, "concepto": m.concepto, "estado": "casado",
                                "detalle": f"{f.factura} · {f.cliente if hasattr(f, 'cliente') else f.proveedor}"})
        for m, cat, nota in conc.explicados:
            movimientos.append({"fecha": m.fecha, "importe": m.importe, "concepto": m.concepto, "estado": "explicado",
                                "detalle": cat + (f": {nota}" if nota else "")})
        for m in conc.cobros_sin_factura + conc.pagos_sin_factura:
            movimientos.append({"fecha": m.fecha, "importe": m.importe, "concepto": m.concepto, "estado": "por explicar",
                                "detalle": "sin factura"})
        movimientos.sort(key=lambda x: x["fecha"])

    usadas = sorted({x.cuenta for a in k.asientos for x in a.apuntes})
    s = p["sede"] or {}
    hallazgos = p["hallazgos"]
    return _plano({
        "empresa": {"nombre": pf.nombre, "nif": pf.nif, "tipo": pf.tipo, "iva": pf.iva_regimen},
        "hoy": hoy, "ejercicio": hoy.year, "nivel": p["nivel"],
        "kpis": {"ingresos": pyg[0][1], "gastos": sum((v for n, v in pyg[1:5]), Decimal(0)), "resultado": base_is,
                 "hucha": p["total_hucha"], "saldo": conc.saldo if conc else None, "fecha_saldo": conc.fecha_saldo if conc else None,
                 "iva": trimestres[-1]["resultado"] if trimestres else None, "iva_periodo": trimestres[-1]["periodo"] if trimestres else ""},
        "plazos": [{"fecha": x["fecha"], "dias": x["dias"], "modelo": x["modelo"], "texto": x["texto"], "nivel": x["nivel"],
                    "obligatorio": x["obligatorio"], "presentado": x["presentado"]} for x in p["plazos"]],
        "hucha": [{"importe": x.importe, "modelo": x.modelo, "concepto": x.concepto, "vence": x.vence, "nota": x.nota,
                   "fuente": x.fuente} for x in p["hucha"]],
        "avisos": [str(h) for h in hallazgos] + k.avisos + (banco.hallazgos(conc, hoy) if conc else []),
        "libros": {"ventas": p["n_ventas"], "compras": p["n_compras"],
                   "errores": sum(1 for h in hallazgos if h.nivel == "error"), "avisos": sum(1 for h in hallazgos if h.nivel == "aviso")},
        "sede": {"actualizado": s.get("actualizado"), "no_leidas": s.get("no_leidas"), "dehu": s.get("dehu_pendientes"),
                 "deudas": s.get("deudas")} if p["sede"] else None,
        "chequeo": p["chequeo"],
        "certificados": [{"cual": x["cual"], "quien": x.get("entidad") or x.get("titular"), "hasta": x.get("hasta"),
                          "dias": x.get("dias")} for x in p["certificados"] if not x.get("error")],
        "radares": {"terceros_347": [{"nombre": t.nombre, "nif": t.nif, "entregas": t.entregas, "adquisiciones": t.adquisiciones}
                                     for t in p["terceros_347"]],
                    "umbrales": [{"nombre": u.nombre, "medido": u.medido, "limite": u.limite, "pct": u.pct, "fuente": u.fuente,
                                  "consecuencia": u.consecuencia} for u in p["umbrales"]]},
        "meses": [{"mes": m, **v} for m, v in sorted(meses.items())],
        "cuentas": {x: k.nombres.get(x, "") for x in usadas},
        "diario": [{"n": a.n, "fecha": a.fecha, "concepto": a.concepto, "fuente": a.fuente,
                    "apuntes": [{"cuenta": x.cuenta, "debe": x.debe, "haber": x.haber} for x in a.apuntes]} for a in k.asientos],
        "sumas": ct.sumas_y_saldos(k),
        "pyg": pyg, "impuesto": {"cuota": cuota_is, "tipo": tipo_is, "fuente": fuente_is},
        "balance": ct.balance(k),
        "iva": iva, "trimestres": trimestres, "nombres_303": cotejo.NOMBRES_303, "facturas": facturas,
        "banco": {"movimientos": movimientos, "saldo": conc.saldo if conc else None, "fecha": conc.fecha_saldo if conc else None,
                  "hallazgos": banco.hallazgos(conc, hoy) if conc else []},
    })


def html(d: dict) -> str:
    return PLANTILLA.replace("__TITULO__", f"GestorIA · {d['empresa']['nombre']}").replace(
        "__DATOS__", json.dumps(d, ensure_ascii=False).replace("</", "<\\/"))


def escribir(carpeta: Path, hoy: date | None = None, **kw) -> Path:
    f = Path(carpeta) / "salida" / "web" / "index.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(html(datos(carpeta, hoy, **kw)), encoding="utf-8")
    return f


def servir(carpeta: Path, puerto: int = PUERTO, abrir: bool = True) -> None:
    """En 127.0.0.1 (solo tu equipo): cada recarga vuelve a leer tus libros y tu banco."""
    import http.server
    import webbrowser

    class Pagina(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] not in ("/", "/index.html"):
                self.send_error(404)
                return
            try:
                cuerpo, codigo = html(datos(carpeta)).encode("utf-8"), 200
            except Exception as e:  # el error, en la página: los datos siguen en tu carpeta
                cuerpo, codigo = f"<pre>GestorIA: {type(e).__name__}: {e}</pre>".encode("utf-8"), 500
            self.send_response(codigo)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), Pagina)
    url = f"http://127.0.0.1:{puerto}/"
    print(f"🌐 Panel contable en {url} (solo en tu equipo; Ctrl+C para cerrarlo)")
    if abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


PLANTILLA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__</title>
<style>
:root{--fondo:#f5f6fa;--tarjeta:#fff;--texto:#1d2433;--tenue:#667085;--borde:#e5e7eb;--suave:#f2f4f8;--acento:#4f46e5;
--verde:#079455;--verde-f:#ecfdf3;--amarillo:#b54708;--amarillo-f:#fffaeb;--rojo:#d92d20;--rojo-f:#fef3f2;--ingreso:#12b76a;--gasto:#f97066}
@media (prefers-color-scheme:dark){:root{--fondo:#0b1020;--tarjeta:#121a30;--texto:#e7eaf3;--tenue:#98a2b3;--borde:#24304d;--suave:#172140;
--verde-f:#05391f;--amarillo-f:#3d2405;--rojo-f:#3f1513}}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--fondo);color:var(--texto)}
a{color:var(--acento);text-decoration:none}
.app{display:grid;grid-template-columns:250px 1fr;min-height:100vh}
aside{background:#0f172a;color:#cbd5e1;padding:20px 14px;position:sticky;top:0;height:100vh;overflow:auto}
.marca{display:flex;gap:10px;align-items:center;font-weight:800;font-size:19px;color:#fff;margin:2px 8px 6px;letter-spacing:-.02em}
.logo{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#38bdf8,#8b5cf6);display:grid;place-items:center;color:#fff;font-size:15px}
.ia{background:linear-gradient(95deg,#fbbf24,#fb7185);-webkit-background-clip:text;background-clip:text;color:transparent}
.empresa{margin:0 8px 14px;font-size:12px;color:#94a3b8}
.menu{display:none;font:inherit;font-size:13px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;border-radius:8px;padding:6px 10px;cursor:pointer}
aside h4{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;margin:16px 8px 6px}
aside nav a{display:flex;gap:10px;align-items:center;padding:7px 10px;border-radius:8px;color:#cbd5e1;font-size:13.5px}
aside nav a:hover{background:#1e293b}aside nav a.activo{background:#4f46e5;color:#fff}
main{padding:26px 34px 70px;min-width:0}
.cabecera{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px}
.cabecera h1{margin:0;font-size:24px;letter-spacing:-.02em}.cabecera p{margin:2px 0 0;color:var(--tenue)}
.derecha{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{background:var(--tarjeta);border:1px solid var(--borde);border-radius:14px;padding:14px 16px}
.kpi small{color:var(--tenue);font-size:12px}.kpi b{display:block;font-size:21px;margin-top:2px;font-variant-numeric:tabular-nums}
.kpi span{font-size:12px;color:var(--tenue)}
.rejilla{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.tarjeta{background:var(--tarjeta);border:1px solid var(--borde);border-radius:14px;padding:16px 18px;margin-top:16px;overflow:auto}
.tarjeta h2{font-size:15px;margin:0 0 10px}
.cab2{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:10px}.cab2 h2{margin:0}
.boton{font:inherit;font-size:12px;font-weight:600;padding:5px 10px;border:1px solid var(--borde);border-radius:8px;background:var(--tarjeta);color:var(--texto);cursor:pointer;white-space:nowrap}
.boton:hover{border-color:var(--acento);color:var(--acento)}
.hueco{flex:1}
table{width:100%;border-collapse:collapse;font-size:13px}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--tenue);text-align:left;padding:8px 10px;border-bottom:1px solid var(--borde);position:sticky;top:0;background:var(--tarjeta)}
td{padding:7px 10px;border-bottom:1px solid var(--borde);vertical-align:top}
.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr.asiento td{background:var(--suave);font-weight:600}
tr.destacado td{box-shadow:inset 3px 0 var(--acento)}
tr.total td{font-weight:700;border-top:2px solid var(--texto);border-bottom:none}
tr.titulo td{font-weight:700;padding-top:14px}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.verde{background:var(--verde-f);color:var(--verde)}.amarillo{background:var(--amarillo-f);color:var(--amarillo)}.rojo{background:var(--rojo-f);color:var(--rojo)}
.gris{background:var(--suave);color:var(--tenue)}
.tenue{color:var(--tenue)}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.filtro{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
input,select{font:inherit;padding:7px 10px;border:1px solid var(--borde);border-radius:9px;background:var(--tarjeta);color:var(--texto);max-width:100%}
.pestanas{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.pestanas button{font:inherit;border:1px solid var(--borde);background:var(--tarjeta);color:var(--texto);padding:6px 12px;border-radius:9px;cursor:pointer}
.pestanas button.activo{background:var(--acento);border-color:var(--acento);color:#fff}
ul.avisos{margin:0;padding-left:18px}ul.avisos li{margin:4px 0}
.leyenda{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--tenue)}.leyenda i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}
.nota{font-size:12px;color:var(--tenue);margin-top:8px}
.barra{height:8px;min-width:120px;background:var(--suave);border-radius:999px;overflow:hidden}.barra i{display:block;height:100%;border-radius:999px;background:var(--verde)}
.barra i.alto{background:#f79009}.barra i.tope{background:var(--rojo)}
@media (max-width:980px){.rejilla{grid-template-columns:1fr}}
@media (max-width:760px){.app{grid-template-columns:1fr}aside{position:sticky;height:auto;padding:10px 16px;z-index:5;display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px}
.marca{margin:0}.empresa{margin:0;flex:1;font-size:11px;line-height:1.3}.menu{display:inline-block}aside h4{display:none}
aside nav{display:none;width:100%;flex-wrap:wrap;gap:4px;padding-top:8px}aside.abierto nav{display:flex}aside nav a{padding:6px 10px;font-size:13px;background:#1e293b}
main{padding:18px 16px 60px}.kpis{grid-template-columns:1fr 1fr}}
@media print{aside,.filtro,.pestanas,.no-imprimir{display:none!important}.app{display:block}main{padding:0}.tarjeta{border:none}}
</style></head>
<body><div class="app">
<aside id="aside"><div class="marca"><div class="logo">✓</div><span>Gestor<span class="ia">IA</span></span></div>
<div class="empresa" id="empresa"></div><button class="menu" id="menu" aria-label="Abrir o cerrar el menú">☰ Menú</button>
<nav id="nav"></nav></aside>
<main id="vista"></main></div>
<script>
const D = __DATOS__;
const NAV = [["Hoy", [["resumen", "📊", "Resumen"], ["plazos", "📅", "Plazos y hucha"]]],
  ["Contabilidad", [["diario", "📒", "Libro diario"], ["mayor", "🔎", "Extracto de cuenta"], ["sumas", "⚖️", "Sumas y saldos"],
                    ["pyg", "📈", "Pérdidas y ganancias"], ["balance", "🏛️", "Balance de situación"]]],
  ["IVA y facturas", [["iva", "🧾", "Libro de IVA"], ["facturacion", "🧮", "Facturación"], ["terceros", "🤝", "Terceros"], ["m303", "📄", "Modelo 303"]]],
  ["Tesorería", [["banco", "🏦", "Banco"]]]];
const e = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const eur = (n) => { if (n == null) return "—"; const p = Math.abs(Number(n)).toFixed(2).split(".");
  return (Number(n) < 0 ? "-" : "") + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "," + p[1] + " €"; };
const num = (n) => n ? eur(n) : "";
const dh = (s) => Math.abs(s) < 0.005 ? "0,00 €" : `${eur(Math.abs(s))} <span class="tenue">${s > 0 ? "D" : "H"}</span>`;
const fe = (s) => s ? s.slice(8, 10) + "/" + s.slice(5, 7) + "/" + s.slice(0, 4) : "";
const cuenta = (c) => `<a href="#mayor/${c}" class="mono">${c}</a> ${e(D.cuentas[c] || "")}`;
const chip = (t, color) => `<span class="chip ${color}">${e(t)}</span>`;
const nivel = {"🔴": "rojo", "🟡": "amarillo", "🟢": "verde"};
const cab = (titulo, sub) => `<div class="cabecera"><div><h1>${titulo}</h1><p>${sub || `${e(D.empresa.nombre)} · ${e(D.empresa.nif)} · ejercicio ${D.ejercicio}`}</p></div>
  <div class="derecha">${chip(D.nivel + " " + ({"🔴": "hay algo urgente", "🟡": "cosas por revisar", "🟢": "todo en orden"}[D.nivel] || ""), nivel[D.nivel] || "gris")}
  <span class="tenue">${fe(D.hoy)}</span><button class="boton no-imprimir" onclick="print()" title="Imprimir esta vista o guardarla en PDF">🖨 Imprimir</button></div></div>`;
const tabla = (cols, filas, pie) => `<table><thead><tr>${cols.map(c => `<th class="${c[1] || ""}">${c[0]}</th>`).join("")}</tr></thead>
  <tbody>${filas.join("")}</tbody>${pie ? `<tfoot>${pie}</tfoot>` : ""}</table>`;

// Cada tabla se baja en CSV: separado por «;» y con coma decimal, el que abre Excel en español.
const CSV = {};
const csv = (nombre, cols, filas) => { CSV[nombre] = {cols, filas};
  return `<button class="boton no-imprimir" onclick="descargar('${nombre}')" title="Baja esta tabla en CSV (separado por «;», para Excel o para tu gestoría)">⬇ CSV</button>`; };
const celda = (v) => { if (v == null || v === "") return "";
  if (typeof v === "number") return (Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100)).replace(".", ",");
  const s = String(v); return /[;"\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
function descargar(nombre) {
  const {cols, filas} = CSV[nombre], texto = "﻿" + [cols, ...filas].map(f => f.map(celda).join(";")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([texto], {type: "text/csv;charset=utf-8"}));
  a.download = `${nombre}_${D.empresa.nif}_${D.ejercicio}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

const nice = (x) => { const p = Math.pow(10, Math.floor(Math.log10(x))), r = x / p; return (r <= 1 ? 1 : r <= 2 ? 2 : r <= 2.5 ? 2.5 : r <= 5 ? 5 : 10) * p; };
const corto = (v) => { const f = (x) => x.toFixed(1).replace(/\.0$/, "").replace(".", ",");
  return v >= 1e6 ? f(v / 1e6) + " M€" : v >= 1e3 ? f(v / 1e3) + " k€" : Math.round(v) + " €"; };
function grafico(meses) {
  if (!meses.length) return '<p class="tenue">Sin movimientos todavía.</p>';
  const W = 640, H = 224, izq = 64, pie = 26, arriba = 12, nombres = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const max = Math.max(1, ...meses.map(m => Math.max(m.ingresos, m.gastos))), paso = nice(max / 4), tope = Math.ceil(max / paso - 1e-9) * paso;
  const alto = H - pie - arriba, y = (v) => arriba + alto - alto * Math.max(0, v) / tope;
  const ancho = (W - izq - 10) / meses.length, barra = Math.min(26, ancho / 3);
  let g = "";
  for (let v = 0; v <= tope + paso / 1000; v += paso)
    g += `<line x1="${izq}" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--borde)"/><text x="${izq - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--tenue)">${corto(v)}</text>`;
  meses.forEach((m, i) => {
    const x = izq + i * ancho + ancho / 2, mes = nombres[+m.mes.slice(5, 7) - 1];
    g += `<rect x="${x - barra - 2}" y="${y(m.ingresos)}" width="${barra}" height="${H - pie - y(m.ingresos)}" rx="4" fill="var(--ingreso)"><title>${mes}: ingresos ${eur(m.ingresos)}</title></rect>`;
    g += `<rect x="${x + 2}" y="${y(m.gastos)}" width="${barra}" height="${H - pie - y(m.gastos)}" rx="4" fill="var(--gasto)"><title>${mes}: gastos ${eur(m.gastos)}</title></rect>`;
    g += `<text x="${x}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--tenue)">${mes}</text>`;
  });
  const ti = meses.reduce((a, m) => a + m.ingresos, 0), tg = meses.reduce((a, m) => a + m.gastos, 0);
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Ingresos y gastos por mes">${g}</svg>
    <div class="leyenda"><span><i style="background:var(--ingreso)"></i>Ingresos ${eur(ti)}</span><span><i style="background:var(--gasto)"></i>Gastos ${eur(tg)}</span></div>`;
}
const cuentaPorDefecto = () => { if (D.cuentas["572"]) return "572";
  const n = {}; for (const a of D.diario) for (const x of a.apuntes) n[x.cuenta] = (n[x.cuenta] || 0) + 1;
  return Object.keys(n).sort((a, b) => n[b] - n[a])[0] || Object.keys(D.cuentas)[0]; };

const V = {};
V.resumen = () => {
  const k = D.kpis, imp = D.impuesto && D.impuesto.cuota != null, l = D.libros;
  const proximos = D.plazos.filter(p => p.obligatorio).slice(0, 6).map(p => `<tr><td>${p.nivel === "✅" ? chip("presentado", "verde") : chip(p.dias + " d", nivel[p.nivel] || "gris")}</td>
    <td>${fe(p.fecha)}</td><td class="mono">${e(p.modelo)}</td><td>${e(p.texto)}</td></tr>`);
  const sede = D.sede ? `${D.sede.no_leidas ? chip(D.sede.no_leidas + " sin leer en la AEAT", "rojo") : chip("AEAT sin notificaciones", "verde")}
    ${D.sede.dehu ? chip(D.sede.dehu + " pendientes en la DEHú", "rojo") : ""} ${D.sede.deudas === "con_deudas" ? chip("deudas", "rojo") : ""}`
    : '<span class="tenue">Sin foto de la sede: <span class="mono">gestoria vigia</span> con tu certificado.</span>';
  const ch = D.chequeo ? `<p>🩺 Último chequeo (${fe(D.chequeo.fecha)}): ${chip(`${D.chequeo.rojos} urgente(s), ${D.chequeo.amarillos} por revisar`,
    D.chequeo.rojos ? "rojo" : D.chequeo.amarillos ? "amarillo" : "verde")}</p>` : "";
  const libros = `<p class="nota" style="margin:0 0 8px">Libros registro: ${l.ventas} facturas emitidas y ${l.compras} recibidas · ${l.errores ? chip(l.errores + " error(es)", "rojo") : ""}
    ${l.avisos ? chip(l.avisos + " aviso(s)", "amarillo") : ""} ${!l.errores && !l.avisos ? chip("sin hallazgos", "verde") : ""}</p>`;
  return cab("Resumen") + `<div class="kpis">
    <div class="kpi"><small>Cifra de negocios ${D.ejercicio}</small><b>${eur(k.ingresos)}</b><span>ventas sin IVA</span></div>
    <div class="kpi"><small>Gastos</small><b>${eur(-k.gastos)}</b><span>compras y servicios</span></div>
    <div class="kpi"><small>Resultado</small><b>${eur(k.resultado)}</b><span>antes de impuestos${imp ? " · IS " + eur(D.impuesto.cuota) : ""}</span></div>
    <div class="kpi"><small>Hucha: aparta</small><b>${eur(k.hucha)}</b><span>para lo que vence</span></div>
    <div class="kpi"><small>Banco</small><b>${eur(k.saldo)}</b><span>${k.fecha_saldo ? "a " + fe(k.fecha_saldo) : "sin extracto"}</span></div>
    <div class="kpi"><small>IVA del ${k.iva_periodo}</small><b>${eur(k.iva)}</b><span>[71] del 303</span></div></div>
    <div class="rejilla"><div class="tarjeta"><h2>Ingresos y gastos por mes</h2>${grafico(D.meses)}</div>
    <div class="tarjeta"><h2>Avisos</h2>${libros}${D.avisos.length ? `<ul class="avisos">${D.avisos.map(a => `<li>${e(a)}</li>`).join("")}</ul>` : '<p class="tenue">Ninguno.</p>'}</div></div>
    <div class="rejilla"><div class="tarjeta"><h2>Próximos plazos</h2>${proximos.length ? tabla([["", ""], ["Fecha"], ["Modelo"], ["Qué"]], proximos)
      : '<p class="tenue">Nada obligatorio en los próximos 120 días del calendario de la AEAT.</p>'}</div>
    <div class="tarjeta"><h2>Sede y certificados</h2><p>${sede}</p>${D.certificados.map(c => `<p>🔐 ${e(c.quien)}: ${chip("caduca el " + fe(c.hasta) + " (" + c.dias + " días)", c.dias <= 15 ? "rojo" : c.dias <= 60 ? "amarillo" : "verde")}</p>`).join("")}${ch}</div></div>`;
};
V.plazos = () => {
  const r = D.radares, t347 = r.terceros_347;
  const umbrales = r.umbrales.map(u => `<tr><td>${e(u.nombre)}<div class="nota">si lo pasas, ${e(u.consecuencia)} (${e(u.fuente)})</div></td>
    <td><div class="barra"><i class="${u.pct >= 100 ? "tope" : u.pct >= 80 ? "alto" : ""}" style="width:${Math.min(100, u.pct)}%"></i></div></td>
    <td class="n">${u.pct} %</td><td class="n">${eur(u.medido)} <span class="tenue">de ${eur(u.limite)}</span></td></tr>`);
  return cab("Plazos y hucha") + `<div class="tarjeta"><h2>Plazos (calendario oficial de la AEAT, 120 días)</h2>${tabla([["", ""], ["Fecha"], ["Modelo"], ["Qué"]],
    D.plazos.map(p => `<tr><td>${p.nivel === "✅" ? chip("presentado", "verde") : p.obligatorio ? chip(p.dias + " d", nivel[p.nivel] || "gris") : chip("si te toca", "gris")}</td><td>${fe(p.fecha)}</td><td class="mono">${e(p.modelo)}</td><td>${e(p.texto)}</td></tr>`))}</div>
    <div class="tarjeta"><h2>Hucha: lo que hay que tener apartado</h2>${tabla([["Importe", "n"], ["Modelo"], ["Concepto"], ["Vence"], ["Fuente"]],
    D.hucha.map(h => `<tr><td class="n"><b>${eur(h.importe)}</b></td><td class="mono">${e(h.modelo)}</td><td>${e(h.concepto)}<div class="nota">${e(h.nota)}</div></td><td>${fe(h.vence)}</td><td class="tenue">${e(h.fuente)}</td></tr>`),
    `<tr class="total"><td class="n">${eur(D.kpis.hucha)}</td><td colspan="4">total</td></tr>`)}</div>
    <div class="tarjeta"><h2>Radares: lo que cambia tus obligaciones</h2>
    <p>📡 347: ${t347.length ? `${t347.length} tercero(s) pasan de 3.005,06 € este año y van en el 347 de febrero (art. 33 RGAT): ${t347.map(t => e(t.nombre)).join(", ")}. <a href="#terceros">Ver terceros</a>`
      : "ningún tercero pasa de 3.005,06 € este año (art. 33 RGAT)."}</p>
    ${tabla([["Umbral"], ["Cifra de negocios del año"], ["", "n"], ["", "n"]], umbrales)}
    <p class="nota">Cuando una barra pasa del 80 % conviene saberlo ya: es lo que cambia el año que viene.</p></div>`;
};
V.diario = (q = "") => {
  let marcar = null;
  if (q.startsWith("@")) { marcar = +q.slice(1); q = ""; }
  const f = q.toLowerCase(), filas = [], csvf = [];
  let td = 0, th = 0, n = 0;
  for (const a of D.diario) {
    const texto = (a.concepto + " " + a.fuente + " " + a.apuntes.map(x => x.cuenta + " " + (D.cuentas[x.cuenta] || "")).join(" ")).toLowerCase();
    if (f && !texto.includes(f)) continue;
    n++;
    filas.push(`<tr class="asiento${a.n === marcar ? " destacado" : ""}" id="asiento-${a.n}"><td class="mono">${a.n}</td><td>${fe(a.fecha)}</td><td colspan="3">${e(a.concepto)} <span class="tenue">· ${e(a.fuente)}</span></td></tr>`);
    for (const x of a.apuntes) { td += x.debe; th += x.haber;
      filas.push(`<tr><td></td><td></td><td>${cuenta(x.cuenta)}</td><td class="n">${num(x.debe)}</td><td class="n">${num(x.haber)}</td></tr>`);
      csvf.push([a.n, a.fecha, a.concepto, a.fuente, x.cuenta, D.cuentas[x.cuenta] || "", x.debe || "", x.haber || ""]); }
  }
  return cab("Libro diario", `${D.diario.length} asientos, cada uno con su documento · ejercicio ${D.ejercicio}`) +
    `<div class="tarjeta"><div class="filtro"><input id="q" placeholder="Buscar (factura, cuenta, concepto…)" value="${e(q)}" oninput="V.repintar('diario', this.value)">
    <span class="tenue">${f ? `${n} de ${D.diario.length} asientos` : `${n} asientos`}</span><span class="hueco"></span>${csv("libro_diario", ["Asiento", "Fecha", "Concepto", "Documento", "Cuenta", "Nombre", "Debe", "Haber"], csvf)}</div>` +
    tabla([["Nº"], ["Fecha"], ["Cuenta"], ["Debe", "n"], ["Haber", "n"]], filas, `<tr class="total"><td colspan="3">Total</td><td class="n">${eur(td)}</td><td class="n">${eur(th)}</td></tr>`) + `</div>`;
};
V.mayor = (c) => {
  c = c || cuentaPorDefecto();
  let saldo = 0, td = 0, th = 0;
  const filas = [], csvf = [];
  for (const a of D.diario) for (const x of a.apuntes) if (x.cuenta === c) { saldo += x.debe - x.haber; td += x.debe; th += x.haber;
    filas.push(`<tr><td>${fe(a.fecha)}</td><td class="mono"><a href="#diario/@${a.n}" title="Ver el asiento ${a.n} en el diario">${a.n}</a></td><td>${e(a.concepto)} <span class="tenue">· ${e(a.fuente)}</span></td><td class="n">${num(x.debe)}</td><td class="n">${num(x.haber)}</td><td class="n"><b>${dh(saldo)}</b></td></tr>`);
    csvf.push([a.fecha, a.n, a.concepto, x.debe || "", x.haber || "", Math.round(saldo * 100) / 100]); }
  const opciones = Object.entries(D.cuentas).map(([k, n]) => `<option value="${k}" ${k === c ? "selected" : ""}>${k} · ${e(n)}</option>`).join("");
  return cab("Extracto de cuenta", `${c} · ${e(D.cuentas[c] || "")}`) + `<div class="tarjeta"><div class="filtro"><select onchange="location.hash='mayor/'+this.value">${opciones}</select><span class="hueco"></span>${csv("extracto_" + c, ["Fecha", "Asiento", "Concepto", "Debe", "Haber", "Saldo"], csvf)}</div>` +
    tabla([["Fecha"], ["Asiento"], ["Concepto"], ["Debe", "n"], ["Haber", "n"], ["Saldo", "n"]], filas,
      `<tr class="total"><td colspan="3">Total · ${filas.length} apunte(s)</td><td class="n">${eur(td)}</td><td class="n">${eur(th)}</td><td class="n">${dh(saldo)}</td></tr>`) +
    `<p class="nota">D = saldo deudor · H = saldo acreedor. En el banco y en clientes, D es lo que tienes o te deben; en proveedores, Hacienda o el capital, H es lo que debes. Cada apunte enlaza con su asiento.</p></div>`;
};
V.sumas = () => {
  const t = {debe: 0, haber: 0, deudor: 0, acreedor: 0};
  const filas = D.sumas.map(s => { for (const k in t) t[k] += s[k];
    return `<tr><td>${cuenta(s.cuenta)}</td><td class="n">${num(s.debe)}</td><td class="n">${num(s.haber)}</td><td class="n">${num(s.deudor)}</td><td class="n">${num(s.acreedor)}</td></tr>`; });
  return cab("Sumas y saldos") + `<div class="tarjeta"><div class="cab2"><h2>Balance de comprobación · ${D.sumas.length} cuentas</h2>${csv("sumas_y_saldos", ["Cuenta", "Nombre", "Sumas debe", "Sumas haber", "Saldo deudor", "Saldo acreedor"],
    D.sumas.map(s => [s.cuenta, s.nombre, s.debe, s.haber, s.deudor, s.acreedor]))}</div>` +
    tabla([["Cuenta"], ["Sumas debe", "n"], ["Sumas haber", "n"], ["Saldo deudor", "n"], ["Saldo acreedor", "n"]], filas,
    `<tr class="total"><td>Total ${Math.abs(t.debe - t.haber) < 0.005 ? chip("cuadra", "verde") : chip("no cuadra", "rojo")}</td><td class="n">${eur(t.debe)}</td><td class="n">${eur(t.haber)}</td><td class="n">${eur(t.deudor)}</td><td class="n">${eur(t.acreedor)}</td></tr>`) + `</div>`;
};
V.pyg = () => {
  const filas = D.pyg.map(([n, v]) => `<tr class="${/^[A-Z]\./.test(n) ? "total" : ""}"><td>${e(n)}</td><td class="n">${eur(v)}</td></tr>`), csvf = D.pyg.map(([n, v]) => [n, v]);
  if (D.impuesto && D.impuesto.cuota != null) {
    const r = D.pyg[D.pyg.length - 1][1];
    filas.push(`<tr><td>17. Impuesto sobre beneficios (estimado: ${e(D.impuesto.tipo)})</td><td class="n">${eur(-D.impuesto.cuota)}</td></tr>`);
    filas.push(`<tr class="total"><td>A.4) RESULTADO DEL EJERCICIO (estimado)</td><td class="n">${eur(r - D.impuesto.cuota)}</td></tr>`);
    csvf.push(["17. Impuesto sobre beneficios (estimado)", -D.impuesto.cuota], ["A.4) RESULTADO DEL EJERCICIO (estimado)", r - D.impuesto.cuota]);
  }
  return cab("Pérdidas y ganancias", `Modelo de pymes (PGC) · ejercicio ${D.ejercicio}, hasta ${fe(D.hoy)}`) +
    `<div class="tarjeta" style="max-width:760px"><div class="cab2"><h2>Cuenta de resultados</h2>${csv("perdidas_y_ganancias", ["Partida", "Importe"], csvf)}</div>${tabla([["Partida"], ["Importe", "n"]], filas)}<p class="nota">Aún sin amortizaciones ni variación de existencias. El impuesto es la estimación de la hucha (${e(D.impuesto.fuente || "")}).</p></div>`;
};
V.balance = () => {
  const b = D.balance, lado = (xs) => xs.map(([n, v]) => v == null ? `<tr class="titulo"><td colspan="2">${e(n)}</td></tr>` : `<tr><td>${e(n)}</td><td class="n">${eur(v)}</td></tr>`);
  const csvf = [...b.activo.map(([n, v]) => ["Activo", n, v]), ["Activo", "TOTAL ACTIVO", b.total_activo],
                ...b.pasivo.map(([n, v]) => ["Patrimonio neto y pasivo", n, v]), ["Patrimonio neto y pasivo", "TOTAL PATRIMONIO NETO Y PASIVO", b.total_pasivo]];
  return cab("Balance de situación", `Modelo de pymes (PGC) a ${fe(D.hoy)}`) + `<div class="rejilla">
    <div class="tarjeta"><h2>Activo</h2>${tabla([["Partida"], ["Importe", "n"]], lado(b.activo), `<tr class="total"><td>TOTAL ACTIVO</td><td class="n">${eur(b.total_activo)}</td></tr>`)}</div>
    <div class="tarjeta"><h2>Patrimonio neto y pasivo</h2>${tabla([["Partida"], ["Importe", "n"]], lado(b.pasivo), `<tr class="total"><td>TOTAL PATRIMONIO NETO Y PASIVO</td><td class="n">${eur(b.total_pasivo)}</td></tr>`)}</div></div>
    <div class="cab2" style="margin-top:12px"><p style="margin:0">${b.cuadra ? chip("✓ el balance cuadra", "verde") : chip("el balance no cuadra", "rojo")}</p>${csv("balance", ["Lado", "Partida", "Importe"], csvf)}</div>`;
};
V.iva = (p = "emitidas") => {
  const xs = D.iva[p], emit = p === "emitidas";
  const filas = xs.map(x => `<tr><td>${fe(x.fecha)}</td><td class="mono">${e(x.trimestre)}</td><td class="mono">${e(x.factura)}</td><td>${e(x.cliente || x.proveedor)}</td><td class="mono">${e(x.nif)}</td>
    <td>${e(x.regimen || x.origen)}</td><td class="n">${num(x.base)}</td><td class="n">${x.tipo} %</td><td class="n">${num(x.cuota)}</td><td class="n">${eur(x.total)}</td></tr>`);
  const tb = xs.reduce((a, x) => a + x.base, 0), tc = xs.reduce((a, x) => a + x.cuota, 0);
  return cab("Libro de IVA", "Libros registro de facturas emitidas y recibidas (art. 62 RIVA)") + `<div class="tarjeta"><div class="pestanas">
    <button class="${emit ? "activo" : ""}" onclick="V.repintar('iva','emitidas')">Emitidas (IVA repercutido)</button>
    <button class="${emit ? "" : "activo"}" onclick="V.repintar('iva','recibidas')">Recibidas (IVA soportado)</button><span class="hueco"></span>
    ${csv("libro_iva_" + p, ["Fecha", "Trimestre", "Factura", emit ? "Cliente" : "Proveedor", "NIF", emit ? "Régimen" : "Origen", "Base", "Tipo", "Cuota", "Total"],
      xs.map(x => [x.fecha, x.trimestre, x.factura, x.cliente || x.proveedor, x.nif, x.regimen || x.origen, x.base, x.tipo, x.cuota, x.total]))}</div>` +
    tabla([["Fecha"], ["Trim."], ["Factura"], [emit ? "Cliente" : "Proveedor"], ["NIF"], [emit ? "Régimen" : "Origen"], ["Base", "n"], ["Tipo", "n"], ["Cuota", "n"], ["Total", "n"]], filas,
      `<tr class="total"><td colspan="6">Total</td><td class="n">${eur(tb)}</td><td></td><td class="n">${eur(tc)}</td><td></td></tr>`) +
    `<p class="nota">En el REBU, la base y la cuota son las del margen de cada venta (art. 137 LIVA).</p></div>`;
};
V.facturacion = (p = "emitidas") => {
  const xs = D.facturas[p], pend = xs.filter(x => x.estado === "pendiente"), emit = p === "emitidas";
  const filas = xs.map(x => `<tr><td>${fe(x.fecha)}</td><td class="mono">${e(x.factura)}</td><td>${e(x.cliente || x.proveedor)}</td><td class="n">${eur(x.total)}</td>
    <td>${x.estado === "pendiente" ? chip("pendiente · " + x.dias + " d", x.dias > 60 ? "amarillo" : "gris")
      : chip((x.total < 0 ? (emit ? "devuelta" : "abonada") : x.estado) + " el " + fe(x.fecha_banco), "verde")}</td>
    ${emit ? "" : `<td>${cuenta(x.cuenta)}</td>`}</tr>`);
  return cab("Facturación", "Las facturas de tu programa de facturación, con su cobro o pago en el banco") + `<div class="tarjeta"><div class="pestanas">
    <button class="${emit ? "activo" : ""}" onclick="V.repintar('facturacion','emitidas')">Emitidas</button>
    <button class="${emit ? "" : "activo"}" onclick="V.repintar('facturacion','recibidas')">Recibidas</button><span class="hueco"></span>
    ${csv("facturacion_" + p, ["Fecha", "Factura", emit ? "Cliente" : "Proveedor", "Total", "Estado", "Fecha en el banco"].concat(emit ? [] : ["Cuenta de gasto"]),
      xs.map(x => [x.fecha, x.factura, x.cliente || x.proveedor, x.total, x.estado, x.fecha_banco || ""].concat(emit ? [] : [x.cuenta])))}</div>` +
    tabla([["Fecha"], ["Factura"], [emit ? "Cliente" : "Proveedor"], ["Total", "n"], ["Estado"]].concat(emit ? [] : [["Cuenta de gasto"]]), filas,
      `<tr class="total"><td colspan="3">${xs.length} facturas · ${pend.length} pendientes</td><td class="n">${eur(xs.reduce((a, x) => a + x.total, 0))}</td><td colspan="2"></td></tr>`) +
    `<p class="nota">GestorIA no emite facturas: un programa que las emite tiene que cumplir el reglamento de Verifactu (RD 1007/2023).</p></div>`;
};
V.terceros = (p = "clientes") => {
  const emit = p === "clientes", xs = emit ? D.iva.emitidas : D.iva.recibidas, g = {};
  for (const x of xs) {
    const nombre = emit ? x.cliente : x.proveedor, nif = x.nif || "", k = nif || nombre;
    const t = g[k] || (g[k] = {nombre, nif, n: 0, base: 0, cuota: 0, total: 0, regimenes: new Set()});
    t.n++; t.base += x.base; t.cuota += x.cuota; t.total += x.total; t.regimenes.add(emit ? x.regimen : x.origen);
  }
  const en347 = new Set(D.radares.terceros_347.map(t => t.nif || t.nombre)), lista = Object.values(g).sort((a, b) => b.total - a.total);
  const filas = lista.map(t => `<tr><td>${e(t.nombre)}</td><td class="mono">${t.nif ? e(t.nif) : '<span class="tenue">sin NIF</span>'}</td><td class="n">${t.n}</td>
    <td>${[...t.regimenes].map(r => chip(r, "gris")).join(" ")}</td><td class="n">${eur(t.base)}</td><td class="n">${eur(t.cuota)}</td><td class="n"><b>${eur(t.total)}</b></td>
    <td>${en347.has(t.nif || t.nombre) ? `<span class="chip amarillo" title="Pasa de 3.005,06 € en el año: va en el 347 de febrero (art. 33 RGAT)">347</span>` : ""}</td></tr>`);
  return cab("Terceros", `Cuánto has ${emit ? "vendido a cada cliente" : "comprado a cada proveedor"} este año, según el libro de IVA`) + `<div class="tarjeta"><div class="pestanas">
    <button class="${emit ? "activo" : ""}" onclick="V.repintar('terceros','clientes')">Clientes</button>
    <button class="${emit ? "" : "activo"}" onclick="V.repintar('terceros','proveedores')">Proveedores</button><span class="hueco"></span>
    ${csv("terceros_" + p, ["Nombre", "NIF", "Facturas", "Base", "Cuota", "Total", "347"], lista.map(t => [t.nombre, t.nif, t.n, t.base, t.cuota, t.total, en347.has(t.nif || t.nombre) ? "sí" : ""]))}</div>` +
    (filas.length ? tabla([["Nombre"], ["NIF"], ["Facturas", "n"], [emit ? "Régimen" : "Origen"], ["Base", "n"], ["Cuota", "n"], ["Total", "n"], ["347"]], filas,
      `<tr class="total"><td colspan="2">${lista.length} ${emit ? "clientes" : "proveedores"}</td><td class="n">${xs.length}</td><td></td><td class="n">${eur(lista.reduce((a, t) => a + t.base, 0))}</td><td class="n">${eur(lista.reduce((a, t) => a + t.cuota, 0))}</td><td class="n">${eur(lista.reduce((a, t) => a + t.total, 0))}</td><td></td></tr>`)
      : `<p class="tenue">Sin facturas ${emit ? "emitidas" : "recibidas"} este año.</p>`) +
    `<p class="nota">347: cada persona o entidad con más de 3.005,06 € en el año, entregas y adquisiciones por separado, se declara en febrero (art. 33 RGAT). Quedan fuera las operaciones que ya van en el 349 y las exportaciones. Con tu certificado, <span class="mono">gestoria terceros</span> comprueba cada NIF en el censo.</p></div>`;
};
V.m303 = () => {
  // JavaScript pone las claves «07» y «09» detrás de «10»…«71»: se ordenan por número, como en el formulario
  const nombre = (k) => D.nombres_303[k] || "", csvf = [], casillas = (t) => Object.entries(t.casillas).filter(([k]) => k !== "65").sort((a, b) => +a[0] - +b[0]);
  D.trimestres.forEach(t => casillas(t).forEach(([k, v]) => csvf.push([t.periodo, k, nombre(k), v])));
  return cab("Modelo 303", "IVA de cada trimestre según tus libros") + `<div class="kpis">${D.trimestres.map(t => `<div class="kpi"><small>${t.periodo} ${D.ejercicio} · ${t.cerrado ? "cerrado" : "en curso"}</small>
    <b>${eur(t.resultado)}</b><span>${t.resultado > 0 ? "a ingresar" : t.resultado < 0 ? "a compensar o devolver" : "sin resultado"}</span></div>`).join("")}</div>
    <div class="cab2" style="margin-top:14px"><span class="tenue">Cada casilla, con su nombre en el formulario de la AEAT.</span>${csv("modelo_303", ["Periodo", "Casilla", "Nombre", "Importe"], csvf)}</div>` +
    D.trimestres.map(t => { const cas = casillas(t);
      return `<div class="tarjeta"><h2>${t.periodo} ${D.ejercicio}${t.cerrado ? "" : " · en curso"}</h2>${cas.length ? tabla([["Casilla"], ["Qué es"], ["Importe", "n"]],
        cas.map(([k, v]) => `<tr><td class="mono">[${k}]</td><td>${e(nombre(k))}</td><td class="n">${eur(v)}</td></tr>`)) : '<p class="tenue">Sin operaciones en el trimestre.</p>'}
        ${t.avisos.length ? `<ul class="avisos">${t.avisos.map(a => `<li>${e(a)}</li>`).join("")}</ul>` : ""}
        ${t.cerrado && cas.length ? `<p class="nota no-imprimir">Para presentarlo: <span class="mono">gestoria presentar 303 --ejercicio ${D.ejercicio} --periodo ${t.periodo}</span></p>` : ""}</div>`; }).join("");
};
V.banco = () => {
  const b = D.banco, color = {"casado": "verde", "explicado": "gris", "por explicar": "amarillo"};
  const filas = b.movimientos.map(m => `<tr><td>${fe(m.fecha)}</td><td>${e(m.concepto)}</td><td class="n">${eur(m.importe)}</td><td>${chip(m.estado, color[m.estado])}</td><td class="tenue">${e(m.detalle)}</td></tr>`);
  return cab("Banco", b.saldo == null ? "Sin extractos en banco/" : `Saldo ${eur(b.saldo)} a ${fe(b.fecha)}`) +
    (b.hallazgos.length ? `<div class="tarjeta"><h2>Por explicar</h2><ul class="avisos">${b.hallazgos.map(h => `<li>${e(h)}</li>`).join("")}</ul></div>` : "") +
    `<div class="tarjeta"><div class="cab2"><h2>${b.movimientos.length} movimientos</h2>${csv("banco", ["Fecha", "Concepto", "Importe", "Estado", "Casado con"], b.movimientos.map(m => [m.fecha, m.concepto, m.importe, m.estado, m.detalle]))}</div>${tabla([["Fecha"], ["Concepto"], ["Importe", "n"], ["Estado"], ["Casado con"]], filas)}</div>`;
};
V.repintar = (vista, arg) => { document.getElementById("vista").innerHTML = V[vista](arg);
  if (vista === "diario") { const q = document.getElementById("q"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); } };
function ir() {
  const h = (location.hash.slice(1) || "resumen"), i = h.indexOf("/");
  const vista = i < 0 ? h : h.slice(0, i), arg = i < 0 ? undefined : decodeURIComponent(h.slice(i + 1));
  const v = V[vista] ? vista : "resumen";
  document.getElementById("vista").innerHTML = V[v](arg);
  document.querySelectorAll("nav a").forEach(a => a.classList.toggle("activo", a.dataset.v === v));
  document.getElementById("aside").classList.remove("abierto");
  const marcado = v === "diario" && arg && arg.startsWith("@") ? document.getElementById("asiento-" + arg.slice(1)) : null;
  if (marcado) marcado.scrollIntoView({block: "center"}); else window.scrollTo(0, 0);
}
document.getElementById("empresa").innerHTML = `${e(D.empresa.nombre)}<br>${e(D.empresa.nif)} · ${D.empresa.tipo === "sl" ? "SL" : "autónomo"} · IVA ${e(D.empresa.iva).toUpperCase()}`;
document.getElementById("nav").innerHTML = NAV.map(([t, xs]) => `<h4>${t}</h4>` + xs.map(([v, i, n]) => `<a href="#${v}" data-v="${v}"><span>${i}</span>${n}</a>`).join("")).join("");
document.getElementById("menu").onclick = () => document.getElementById("aside").classList.toggle("abierto");
window.addEventListener("hashchange", ir);
ir();
</script></body></html>"""
