"""La hucha: cuánto dinero hay que tener apartado hoy para pagar lo que viene, sacado de los
libros, obligación por obligación y con su fecha. Es lo que un gestor te dice «ve guardando».

Lo que calcula y de dónde sale cada regla (BOE consolidado, leído el 20-oct-2026):
- IVA (303): el trimestre cerrado que aún no ha vencido y el trimestre en curso hasta hoy, con
  las mismas casillas que el borrador del 303 (arts. 135-139 LIVA para el REBU).
- Sociedades (SL): resultado estimado del ejercicio × tipo del art. 29.1 LIS: 15 % las entidades
  de nueva creación (primer período con base positiva y el siguiente); microempresas (cifra de
  negocios < 1 M€) la escala transitoria de la DT 44ª LIS (2025: 21 %/22 %; 2026: 19 %/21 %)
  y después la del art. 29.1 (17 %/20 %, con 50.000 € de primer tramo prorrateados si el
  ejercicio es más corto); reducida dimensión (< 10 M€, art. 101) 24 % en 2025, 23 % en 2026,
  20 % después; general 25 %. Las pérdidas no pagan y se compensan en ejercicios siguientes
  (art. 26 LIS). Las compras de inversión no se restan enteras: se amortizan (art. 12 LIS).
- Pago fraccionado del IS (202): 18 % de la cuota del último 200 presentado (art. 40.2 LIS) en
  abril, octubre y diciembre (art. 40.1). Sin 200 presentado no hay 202.
- IRPF del autónomo (130): 20 % del rendimiento neto acumulado desde el 1 de enero, menos las
  retenciones soportadas, los 130 ya pagados este año y la minoración por rendimientos bajos del
  año anterior (≤ 9.000 € → 100; ≤ 10.000 → 75; ≤ 11.000 → 50; ≤ 12.000 → 25) (art. 110 RIRPF).
- Cuota de autónomos (RETA): la que diga perfil.toml; la fija la Orden de cotización del año
  por tramos de rendimiento neto (comprobable en Importass). No se estima aquí.
Lo que NO calcula: la renta de junio del autónomo (depende de su situación personal; el 130 ya
adelanta el 20 %) y el IVA de operaciones que no estén en los libros.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from gestoria import D2, plazos
from gestoria.libros import Compra, Venta, pagado
from gestoria.modelos import m303
from gestoria.numeros import eur

CERO = D2(0)
MINORACION_130 = ((Decimal("9000"), Decimal("100")), (Decimal("10000"), Decimal("75")),
                  (Decimal("11000"), Decimal("50")), (Decimal("12000"), Decimal("25")))


@dataclass
class Partida:
    modelo: str
    concepto: str
    importe: Decimal
    vence: date
    fuente: str
    nota: str = ""
    periodo: str = ""
    detalle: dict = field(default_factory=dict)


def ingresos_gastos(ventas: list[Venta], compras: list[Compra], desde: date, hasta: date) -> tuple[Decimal, Decimal, list[str]]:
    """Ingresos y gastos contables (sin IVA) entre dos fechas (fin excluido), para estimar el
    IS o el rendimiento neto del IRPF. Devuelve también los avisos de lo que ha tenido que suponer."""
    ingresos, gastos, avisos = CERO, CERO, []
    por_numero = {v.factura: v for v in ventas}

    def neto(v: Venta) -> tuple[Decimal, Decimal]:
        """(ingreso sin IVA, coste de lo vendido) de una venta."""
        if v.regimen == "rebu":
            total, coste = v.total or CERO, v.coste
            if coste is None:
                avisos.append(f"{v.factura}: venta REBU sin coste; se toma 0 (el IS/IRPF sale de más)")
                coste = CERO
            _, cuota = m303.rebu(total, coste, v.tipo)
            return D2(total - cuota), coste
        base = v.base if v.base is not None else (v.total or CERO)
        return D2(base), CERO

    for v in (v for v in ventas if desde <= v.fecha < hasta):
        if v.rectifica and v.regimen == "rebu" and v.rectifica in por_numero:
            ing, coste = neto(por_numero[v.rectifica])
            ingresos -= ing
            gastos -= coste
            continue
        ing, coste = neto(v)
        ingresos += ing
        gastos += coste
    for c in (c for c in compras if desde <= c.fecha < hasta):
        if c.gasto == "inversion":
            avisos.append(f"{c.factura}: inversión de {eur(c.base)}; se amortiza, no se resta entera (art. 12 LIS; art. 28.1 LIRPF)")
            continue
        gastos += c.base + ((c.cuota or CERO) if not c.deducible else CERO)
    return D2(ingresos), D2(gastos), avisos


def tipo_is(perfil, ejercicio: int, base: Decimal) -> tuple[Decimal, str, str]:
    """(cuota, descripción del tipo, fuente) según el art. 29.1 LIS y la DT 44ª."""
    if base <= 0:
        return CERO, "sin cuota: base negativa o cero (las pérdidas se compensan después, art. 26 LIS)", "art. 26 LIS"
    if perfil.is_tipo is not None:
        return D2(base * perfil.is_tipo / 100), f"{perfil.is_tipo} % (tipo fijado en perfil.toml)", "perfil.toml"
    if perfil.is_nueva_creacion:
        return D2(base * 15 / 100), "15 % (entidad de nueva creación: primer período con base positiva y el siguiente)", "art. 29.1 LIS"
    cifra = perfil.cifra_negocios_anterior
    if cifra is None:
        return D2(base * 25 / 100), "25 % general (pon cifra_negocios_anterior en perfil.toml si eres microempresa)", "art. 29.1 LIS"
    if cifra < 1_000_000:
        bajo, alto = {2025: (21, 22), 2026: (19, 21)}.get(ejercicio, (17, 20))
        tramo = Decimal(50_000)
        if perfil.ejercicio_inicio and perfil.ejercicio_inicio.year == ejercicio and perfil.ejercicio_inicio != date(ejercicio, 1, 1):
            dias = (date(ejercicio + 1, 1, 1) - perfil.ejercicio_inicio).days
            tramo = D2(tramo * dias / 365)
        primero = min(base, tramo)
        cuota = D2(primero * bajo / 100 + (base - primero) * alto / 100)
        fuente = "DT 44.ª LIS" if ejercicio in (2025, 2026) else "art. 29.1 LIS (comprueba la DT 44.ª para ese año)"
        return cuota, f"{bajo} % hasta {tramo} € y {alto} % el resto (microempresa, cifra de negocios < 1 M€)", fuente
    if cifra < 10_000_000:
        t = {2025: 24, 2026: 23}.get(ejercicio, 20)
        return D2(base * t / 100), f"{t} % (reducida dimensión, cifra de negocios < 10 M€)", "art. 29.1 y 101 LIS; DT 44.ª"
    return D2(base * 25 / 100), "25 % (tipo general)", "art. 29.1 LIS"


def _iva(ventas, compras, aj, hoy: date, presentados: set[tuple[int, str]]) -> list[Partida]:
    """El 303 del trimestre cerrado (si no ha vencido ni está presentado) y el del trimestre en curso."""
    ej, per = plazos.trimestre_de(hoy)
    pendientes = []
    ej0, per0 = plazos.trimestre_anterior(ej, per)
    if hoy <= plazos.vence("303", ej0, per0) and (ej0, per0) not in presentados:
        pendientes.append((ej0, per0, "cerrado, pendiente de presentar"))
    pendientes.append((ej, per, "en curso, con lo facturado hasta hoy"))
    compensar = Decimal(str(aj.get("compensar_pendiente", "0")))
    out = []
    for e, p, etiqueta in pendientes:
        desde, hasta = m303.periodo_fechas(e, p)
        try:
            cas, avisos = m303.casillas(ventas, compras, desde, min(hasta, hoy + timedelta(days=1)), compensar)
        except ValueError as err:
            out.append(Partida("303", f"IVA {p} {e} ({etiqueta})", CERO, plazos.vence("303", e, p), "art. 71.4 RIVA",
                               nota=f"no se puede calcular: {err}", periodo=f"{e}-{p}"))
            continue
        resultado = cas.get("71", CERO)
        compensar = cas.get("87", CERO) if resultado >= 0 else cas.get("87", CERO) + (-resultado)
        nota = "sale a compensar: no hay que apartar nada" if resultado < 0 else ""
        if avisos:
            nota = (nota + "; " if nota else "") + f"{len(avisos)} aviso(s) en el borrador"
        out.append(Partida("303", f"IVA {p} {e} ({etiqueta})", max(resultado, CERO), plazos.vence("303", e, p),
                           "art. 71.4 RIVA; casillas del 303", nota=nota, periodo=f"{e}-{p}",
                           detalle={"71": resultado, "27": cas.get("27", CERO), "45": cas.get("45", CERO)}))
    return out


def _sociedades(perfil, ventas, compras, aj, hoy: date) -> list[Partida]:
    ej = hoy.year
    inicio = perfil.ejercicio_inicio if perfil.ejercicio_inicio and perfil.ejercicio_inicio.year == ej else date(ej, 1, 1)
    ingresos, gastos, avisos = ingresos_gastos(ventas, compras, inicio, hoy + timedelta(days=1))
    base = D2(ingresos - gastos)
    cuota, tipo, fuente = tipo_is(perfil, ej, base)
    out = [Partida("200", f"Impuesto sobre Sociedades {ej} (estimado con lo contabilizado hasta hoy)", cuota,
                   plazos.vence("200", ej), fuente,
                   nota=f"ingresos {eur(ingresos)} − gastos {eur(gastos)} = base {eur(base)}; tipo {tipo}"
                        + ("; " + "; ".join(avisos[:3]) if avisos else ""),
                   periodo=str(ej), detalle={"ingresos": ingresos, "gastos": gastos, "base": base})]
    cuota_200 = Decimal(str(aj.get("cuota_200_anterior", "0")))
    pagados_202 = pagado(aj, "202")
    if cuota_200 > 0:
        for mes, fecha in plazos.plazos_202(ej):
            if fecha >= hoy:
                out.append(Partida("202", f"Pago fraccionado del IS, {mes} {ej}", D2(cuota_200 * 18 / 100), fecha,
                                   "art. 40.1 y 40.2 LIS", nota=f"18 % de la cuota del último 200 ({eur(cuota_200)})"
                                   + (f"; ya pagados este año {eur(pagados_202)}" if pagados_202 else ""), periodo=mes))
    else:
        proximo = next((f for _, f in plazos.plazos_202(ej) if f >= hoy), None)
        out.append(Partida("202", f"Pago fraccionado del IS ({ej})", CERO, proximo or plazos.vence("200", ej), "art. 40.2 LIS",
                           nota="no aplica: sin 200 presentado con cuota (ajustes.toml → cuota_200_anterior)"))
    return out


def minoracion_130(rendimiento_anterior: Decimal | None) -> Decimal:
    if rendimiento_anterior is None:
        return CERO
    for tope, importe in MINORACION_130:
        if rendimiento_anterior <= tope:
            return importe
    return CERO


def _irpf_autonomo(perfil, ventas, compras, aj, hoy: date, presentados: set[tuple[int, str]]) -> list[Partida]:
    if perfil.estimacion != "directa":
        return [Partida("130", "Pago fraccionado del IRPF", CERO, hoy, "art. 110.1.b RIRPF",
                        nota="estimación objetiva (módulos): no soportada; calcúlalo con tus datos-base")]
    ej, per = plazos.trimestre_de(hoy)
    pendientes = []
    ej0, per0 = plazos.trimestre_anterior(ej, per)
    if ej0 == ej and hoy <= plazos.vence("130", ej0, per0) and (ej0, per0) not in presentados:
        pendientes.append((per0, "cerrado, pendiente de presentar"))
    pendientes.append((per, "en curso, con lo facturado hasta hoy"))
    ya = pagado(aj, "130")
    out = []
    for p, etiqueta in pendientes:
        _, hasta = m303.periodo_fechas(ej, p)
        hasta = min(hasta, hoy + timedelta(days=1))
        ingresos, gastos, avisos = ingresos_gastos(ventas, compras, date(ej, 1, 1), hasta)
        rn = D2(ingresos - gastos)
        retenciones = sum((v.retencion or CERO for v in ventas if date(ej, 1, 1) <= v.fecha < hasta), CERO)
        bruto = D2(rn * 20 / 100) if rn > 0 else CERO
        minor = minoracion_130(perfil.rendimiento_neto_anterior)
        importe = max(D2(bruto - retenciones - ya - minor), CERO)
        out.append(Partida("130", f"IRPF {p} {ej} ({etiqueta})", importe, plazos.vence("130", ej, p), "art. 110 y 111 RIRPF",
                           nota=f"20 % de {eur(rn)} (ingresos {eur(ingresos)} − gastos {eur(gastos)}) = {eur(bruto)}; − retenciones {eur(retenciones)}"
                                f" − pagado {eur(ya)}" + (f" − minoración {eur(minor)}" if minor else "")
                                + ("; " + "; ".join(avisos[:2]) if avisos else ""), periodo=f"{ej}-{p}",
                           detalle={"rn": rn, "retenciones": retenciones}))
        ya += importe  # el siguiente trimestre ya descuenta este pago
    if perfil.reta_mensual:
        fin_mes = (date(hoy.year + (hoy.month == 12), hoy.month % 12 + 1, 1) - timedelta(days=1))
        out.append(Partida("RETA", "Cuota de autónomos de este mes", D2(perfil.reta_mensual), fin_mes,
                           "Orden de cotización del año (tramos de rendimiento neto)", nota="cargo en cuenta a fin de mes; cada mes igual"))
    else:
        out.append(Partida("RETA", "Cuota de autónomos", CERO, hoy, "Orden de cotización del año",
                           nota="pon reta_mensual en perfil.toml (la cuota que te carga la Seguridad Social) para contarla"))
    return out


def calcular(perfil, ventas: list[Venta], compras: list[Compra], aj: dict, hoy: date,
             presentados: set[tuple[int, str]] | None = None) -> list[Partida]:
    """Todas las partidas de la hucha a fecha de hoy, ordenadas por vencimiento.
    `presentados`: (ejercicio, periodo) de los 303/130 que la sede ya da por presentados."""
    pres = presentados or set()
    partidas = _iva(ventas, compras, aj, hoy, pres)
    if perfil.tipo == "sl":
        partidas += _sociedades(perfil, ventas, compras, aj, hoy)
    else:
        partidas += _irpf_autonomo(perfil, ventas, compras, aj, hoy, pres)
    # las que no aplican (importe 0 y «no aplica…») van al final
    return sorted(partidas, key=lambda p: (p.importe == 0 and p.nota.startswith("no aplica"), p.vence, p.modelo))


def total(partidas: list[Partida]) -> Decimal:
    return D2(sum((p.importe for p in partidas), CERO))
