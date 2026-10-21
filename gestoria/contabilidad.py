"""La contabilidad por partida doble, con el Plan General de Contabilidad de pymes (RD 1515/2007),
sacada de tus libros registro y de tu banco.

Cada asiento sale de un documento y lo dice: la factura, el movimiento del banco o la liquidación
del trimestre. No hay apuntes a mano. Lo que GestorIA no sabe explicar va a la cuenta 555
«Partidas pendientes de aplicación», que existe para eso, así que cada saldo en la 555 es una
pregunta para ti.

- **Facturas emitidas.** Van a 430 Clientes contra 700 Ventas de mercaderías (705 Prestaciones de
  servicios para un autónomo) y 477 IVA repercutido. En el REBU la cuota es la del margen, y el
  coste del bien usado vendido va a la 600 contra la 555 hasta que se sepa cómo se pagó. Las
  rectificativas van a la 708 Devoluciones de ventas.
- **Facturas recibidas.** El gasto va a su cuenta, que se deduce del proveedor (manda `[cuentas]`
  de ajustes.toml), o al inmovilizado si es una inversión. El IVA va a la 472 IVA soportado,
  contra 400 Proveedores, 410 Acreedores o 523 Proveedores de inmovilizado. En las adquisiciones
  intracomunitarias el IVA se autorrepercute: 472 y 477 a la vez.
- **Banco.** Cada cobro o pago casado con su factura salda la 430, 400, 410 o 523 contra la 572. Las
  comisiones van a la 626, los pagos a Hacienda que cuadran con un 303 a la 4750, la Seguridad
  Social a la 642 y el socio a la 551. Lo demás va a la 555.
- **Cierre de cada trimestre.** Se liquida el IVA: 477 contra 472, y la diferencia a la 4750 si sale a
  ingresar o a la 4700 si sale a compensar o devolver.
- **Apertura.** El capital social, desde `[contabilidad] capital_social`.

De ahí salen el libro diario, el mayor (extracto de cada cuenta), sumas y saldos, la cuenta de
pérdidas y ganancias y el balance de situación, con los modelos de pymes. No es la contabilidad
legalizada: el libro diario de una sociedad se legaliza en el Registro Mercantil (arts. 25-27 del
Código de Comercio). Es la que sale de tus documentos, para revisarla y llevarla al día. Aún no
calcula amortizaciones ni existencias finales, y lo avisa.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from gestoria import D2
from gestoria.numeros import eur

CERO = D2(0)
CUENTAS = {
    "100": "Capital social", "112": "Reserva legal", "113": "Reservas voluntarias", "129": "Resultado del ejercicio",
    "213": "Maquinaria", "216": "Mobiliario", "217": "Equipos para procesos de información", "218": "Elementos de transporte",
    "300": "Mercaderías", "400": "Proveedores", "410": "Acreedores por prestaciones de servicios", "430": "Clientes",
    "4700": "Hacienda Pública, deudora por IVA", "472": "Hacienda Pública, IVA soportado",
    "473": "Hacienda Pública, retenciones y pagos a cuenta", "4750": "Hacienda Pública, acreedora por IVA",
    "4752": "Hacienda Pública, acreedora por impuesto sobre sociedades", "476": "Organismos de la Seguridad Social, acreedores",
    "477": "Hacienda Pública, IVA repercutido", "523": "Proveedores de inmovilizado a corto plazo",
    "551": "Cuenta corriente con socios y administradores", "555": "Partidas pendientes de aplicación",
    "572": "Bancos e instituciones de crédito c/c vista, euros", "600": "Compras de mercaderías",
    "621": "Arrendamientos y cánones", "622": "Reparaciones y conservación", "623": "Servicios de profesionales independientes",
    "624": "Transportes", "625": "Primas de seguros", "626": "Servicios bancarios y similares",
    "627": "Publicidad, propaganda y relaciones públicas", "628": "Suministros", "629": "Otros servicios",
    "640": "Sueldos y salarios", "642": "Seguridad Social a cargo de la empresa", "662": "Intereses de deudas",
    "700": "Ventas de mercaderías", "705": "Prestaciones de servicios", "708": "Devoluciones de ventas y operaciones similares",
    "769": "Otros ingresos financieros",
}
# La cuenta del gasto por el nombre del proveedor (ajustes.toml [cuentas] manda sobre esto)
GASTOS = ((r"TRANSPORT|MENSAJER|PAQUETER|LOGISTIC|CORREOS|SEUR|MRW|\bGLS\b|\bDHL\b|\bUPS\b", "624"),
          (r"GESTORIA|ASESOR|ABOGAD|NOTAR|CONSULTOR", "623"), (r"ALQUILER|ARRENDA|INMOBILIAR", "621"),
          (r"SEGURO|ASEGURADORA|MUTUA", "625"), (r"PUBLICIDAD|MARKETING|ANUNCI", "627"),
          (r"ELECTRIC|ENERG|\bAGUA\b|\bGAS\b|TELEFON|MOVIL|INTERNET|FIBRA", "628"),
          (r"REPARACI|MANTENIM|LIMPIEZA", "622"), (r"RECAMBIO|REPUESTO|MERCANC|MAYORISTA|DISTRIBU", "600"),
          (r"SOFTWARE|INFORMATIC|HOSTING|SAAS|CLOUD|DOMINIO", "629"))
INMOVILIZADO = ((r"ORDENADOR|PORTATIL|INFORMATIC|\bPC\b|SERVIDOR|TABLET|IMPRESORA", "217"),
                (r"COCHE|FURGONETA|VEHICUL|\bMOTO", "218"), (r"MUEBLE|MOBILIARIO|ESTANTER|MOSTRADOR", "216"))
BANCO = {"Hacienda": "4750", "Seguridad Social": "642", "comisiones e intereses del banco": "626", "nóminas": "640",
         "socio": "551"}


@dataclass
class Apunte:
    cuenta: str
    debe: Decimal = CERO
    haber: Decimal = CERO


@dataclass
class Asiento:
    n: int
    fecha: date
    concepto: str
    apuntes: list[Apunte]
    fuente: str = ""

    @property
    def cuadra(self) -> bool:
        return sum((a.debe for a in self.apuntes), CERO) == sum((a.haber for a in self.apuntes), CERO)


@dataclass
class Contabilidad:
    ejercicio: int
    asientos: list[Asiento] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    nombres: dict = field(default_factory=lambda: dict(CUENTAS))

    def saldos(self, hasta: date | None = None) -> dict[str, tuple[Decimal, Decimal]]:
        """cuenta → (suma debe, suma haber)."""
        s: dict[str, list[Decimal]] = defaultdict(lambda: [CERO, CERO])
        for a in self.asientos:
            if hasta and a.fecha > hasta:
                continue
            for p in a.apuntes:
                s[p.cuenta][0] += p.debe
                s[p.cuenta][1] += p.haber
        return {k: (D2(v[0]), D2(v[1])) for k, v in sorted(s.items())}

    def saldo(self, prefijos: tuple[str, ...], signo: int = 1) -> Decimal:
        """Saldo deudor (signo 1) o acreedor (signo -1) de las cuentas que empiezan por esos prefijos."""
        x = D2(signo * sum((d - h for c, (d, h) in self.saldos().items() if c.startswith(prefijos)), CERO))
        return x if x else CERO          # sin «-0,00»

    def mayor(self, cuenta: str) -> list[dict]:
        """El extracto de una cuenta, con su saldo después de cada apunte."""
        out, saldo = [], CERO
        for a in self.asientos:
            for p in a.apuntes:
                if p.cuenta == cuenta:
                    saldo += p.debe - p.haber
                    out.append({"n": a.n, "fecha": a.fecha, "concepto": a.concepto, "debe": p.debe, "haber": p.haber,
                                "saldo": D2(saldo), "fuente": a.fuente})
        return out


# ─── de los documentos a los asientos ───────────────────────────────────────────────────────

def _por_nombre(nombre: str, tabla) -> str | None:
    from gestoria.banco import _sin_acentos

    n = _sin_acentos(nombre)
    return next((cuenta for patron, cuenta in tabla if re.search(patron, n)), None)


def cuenta_de_compra(c, cuentas: dict[str, str]) -> str:
    if c.proveedor in cuentas:
        return str(cuentas[c.proveedor])
    if c.gasto == "inversion":
        return _por_nombre(c.proveedor, INMOVILIZADO) or "213"
    return _por_nombre(c.proveedor, GASTOS) or "629"


def generar(pf, ventas, compras, ajustes: dict, ejercicio: int, hoy: date, extractos=None) -> Contabilidad:
    """Todos los asientos del ejercicio, en orden de fecha."""
    from gestoria.modelos import m303

    k = Contabilidad(ejercicio)
    cont = ajustes.get("contabilidad") or {}
    cuentas = {str(a): str(b) for a, b in (ajustes.get("cuentas") or {}).items()}
    cuenta_ventas = str(cont.get("cuenta_ventas") or ("705" if pf.tipo == "autonomo" else "700"))
    ini, fin = date(ejercicio, 1, 1), date(ejercicio + 1, 1, 1)
    if pf.ejercicio_inicio and pf.ejercicio_inicio.year == ejercicio:
        ini = pf.ejercicio_inicio
    borrador: list[tuple[date, str, list[Apunte], str]] = []
    nuevo = lambda fecha, concepto, apuntes, fuente: borrador.append((fecha, concepto, [a for a in apuntes if a.debe or a.haber], fuente))
    por_numero = {v.factura: v for v in ventas}

    # apertura
    movs = sorted((m for e in (extractos or []) for m in e.movimientos if ini <= m.fecha < fin), key=lambda m: m.fecha)
    saldo_inicial = next((e.saldo_inicial for e in (extractos or []) if e.saldo_inicial is not None and e.desde and e.desde.year == ejercicio), None)
    capital = D2(cont.get("capital_social") or 0)
    if capital or saldo_inicial:
        f0 = min([m.fecha for m in movs] + [e.desde for e in (extractos or []) if e.desde] or [ini])
        banco0 = D2(saldo_inicial or 0)
        nuevo(f0, "Apertura: capital social" + (" y saldo inicial del banco" if banco0 else ""),
              [Apunte("572", debe=banco0), Apunte("100", haber=capital)] +
              ([Apunte("555", haber=banco0 - capital)] if banco0 > capital else [Apunte("555", debe=capital - banco0)] if capital > banco0 else []),
              "[contabilidad] capital_social de ajustes.toml" + (" · saldo inicial del extracto" if banco0 else ""))

    # facturas emitidas
    for v in (v for v in ventas if ini <= v.fecha < fin):
        if v.regimen in ("intracomunitaria", "exportacion", "no_sujeta"):
            b = v.base if v.base is not None else (v.total or CERO)
            nuevo(v.fecha, f"Factura {v.factura} a {v.cliente} ({v.regimen.replace('_', ' ')})",
                  [Apunte("430", debe=b), Apunte(cuenta_ventas, haber=b)], f"ventas.csv · {v.factura}")
            continue
        orig = por_numero.get(v.rectifica) if v.rectifica else None
        b, q = m303._base_cuota(orig if (orig and v.regimen == "rebu") else v)
        signo = -1 if (orig and v.regimen == "rebu") else 1
        b, q = D2(signo * b), D2(signo * q)
        total = D2(v.total) if v.total is not None else D2(b + q)
        ret = D2(v.retencion or 0)
        ingreso = D2(total - q) if v.regimen == "rebu" else b    # en el REBU, todo lo que no es IVA es venta
        rectificativa = total < 0
        if rectificativa:
            ap = [Apunte("708", debe=-ingreso), Apunte("477", debe=-q), Apunte("430", haber=-(total - ret))]
            if ret:
                ap.append(Apunte("473", haber=-ret))
        else:
            ap = [Apunte("430", debe=total - ret), Apunte(cuenta_ventas, haber=ingreso), Apunte("477", haber=q)]
            if ret:
                ap.append(Apunte("473", debe=ret))
        nuevo(v.fecha, f"Factura {v.factura}{' (rectifica ' + v.rectifica + ')' if v.rectifica else ''} · {v.cliente}", ap,
              f"ventas.csv · {v.factura}" + (" · REBU: IVA del margen (art. 137 LIVA)" if v.regimen == "rebu" else ""))
        if v.regimen == "rebu":
            coste = D2((orig.coste if orig else v.coste) or 0) * signo
            if coste > 0:
                nuevo(v.fecha, f"Coste del bien usado vendido en {v.factura}", [Apunte("600", debe=coste), Apunte("555", haber=coste)],
                      "coste de ventas.csv · ¿cómo se pagó la compra? (queda en la 555)")
            elif coste < 0:
                nuevo(v.fecha, f"Vuelve el bien usado de {v.factura}", [Apunte("555", debe=-coste), Apunte("600", haber=-coste)],
                      "coste de ventas.csv")

    # facturas recibidas
    for c in (c for c in compras if ini <= c.fecha < fin):
        cuenta = cuenta_de_compra(c, cuentas)
        cuota = D2(c.cuota if c.cuota is not None else c.base * c.tipo / 100)
        acreedor = "523" if c.gasto == "inversion" else "400" if cuenta.startswith("60") else "410"
        if c.origen == "intracomunitaria":
            ap = [Apunte(cuenta, debe=D2(c.base)), Apunte("472", debe=cuota), Apunte("477", haber=cuota), Apunte(acreedor, haber=D2(c.base))]
            fuente = f"compras.csv · {c.factura} · inversión del sujeto pasivo (art. 84.Uno.2.º LIVA)"
        elif c.deducible:
            ap = [Apunte(cuenta, debe=D2(c.base)), Apunte("472", debe=cuota), Apunte(acreedor, haber=D2(c.base + cuota))]
            fuente = f"compras.csv · {c.factura}"
        else:
            ap = [Apunte(cuenta, debe=D2(c.base + cuota)), Apunte(acreedor, haber=D2(c.base + cuota))]
            fuente = f"compras.csv · {c.factura} · IVA no deducible: va al gasto"
        nuevo(c.fecha, f"Factura {c.factura} de {c.proveedor}", ap, fuente)
        if c.gasto == "inversion":
            k.avisos.append(f"{c.factura}: inmovilizado de {eur(c.base)} en la {cuenta}; la amortización no se calcula todavía")

    # banco
    if extractos:
        from gestoria import banco as bn
        from gestoria.libros import Venta

        r = bn.conciliar(extractos, ventas, compras, hoy)
        for m, f in r.casados:
            if not ini <= m.fecha < fin:
                continue
            if isinstance(f, Venta):
                ap = [Apunte("572", debe=m.importe), Apunte("430", haber=m.importe)] if m.importe > 0 else \
                     [Apunte("430", debe=-m.importe), Apunte("572", haber=-m.importe)]
                nuevo(m.fecha, f"{'Cobro' if m.importe > 0 else 'Devolución'} de la factura {f.factura} · {f.cliente}", ap,
                      f"banco · {m.concepto[:40]}")
            else:
                acreedor = "523" if f.gasto == "inversion" else "400" if cuenta_de_compra(f, cuentas).startswith("60") else "410"
                ap = [Apunte(acreedor, debe=-m.importe), Apunte("572", haber=-m.importe)] if m.importe < 0 else \
                     [Apunte("572", debe=m.importe), Apunte(acreedor, haber=m.importe)]
                nuevo(m.fecha, f"Pago de la factura {f.factura} · {f.proveedor}", ap, f"banco · {m.concepto[:40]}")
        for m, cat, nota in r.explicados:
            if not ini <= m.fecha < fin:
                continue
            cuenta = BANCO.get(cat, "555")
            if cat == "Hacienda" and not nota.startswith("cuadra"):
                cuenta = "555"
            if cat == "comisiones e intereses del banco" and m.importe > 0:
                cuenta = "769"
            ap = [Apunte(cuenta, debe=-m.importe), Apunte("572", haber=-m.importe)] if m.importe < 0 else \
                 [Apunte("572", debe=m.importe), Apunte(cuenta, haber=m.importe)]
            nuevo(m.fecha, f"{m.concepto[:50]} ({cat})", ap, "banco" + (f" · {nota}" if nota else ""))
        for m in r.cobros_sin_factura + r.pagos_sin_factura:
            if not ini <= m.fecha < fin:
                continue
            ap = [Apunte("572", debe=m.importe), Apunte("555", haber=m.importe)] if m.importe > 0 else \
                 [Apunte("555", debe=-m.importe), Apunte("572", haber=-m.importe)]
            nuevo(m.fecha, f"{m.concepto[:50]} (sin factura: por explicar)", ap, "banco · `gestoria banco`")

    # liquidación del IVA de cada trimestre cerrado
    for n in range(1, 5):
        d, h = date(ejercicio, 3 * n - 2, 1), (date(ejercicio + 1, 1, 1) if n == 4 else date(ejercicio, 3 * n + 1, 1))
        cierre = h - timedelta(days=1)
        if cierre >= hoy or h <= ini:
            continue
        rep = sum((p.haber - p.debe for f, _, ap, _ in borrador if d <= f < h for p in ap if p.cuenta == "477"), CERO)
        sop = sum((p.debe - p.haber for f, _, ap, _ in borrador if d <= f < h for p in ap if p.cuenta == "472"), CERO)
        if not rep and not sop:
            continue
        dif = D2(rep - sop)
        ap = [Apunte("477", debe=rep), Apunte("472", haber=sop)] + \
             ([Apunte("4750", haber=dif)] if dif > 0 else [Apunte("4700", debe=-dif)] if dif < 0 else [])
        nuevo(cierre, f"Liquidación del IVA del {n}T {ejercicio}", ap, f"303 del {n}T: [27] {eur(rep)} − [45] {eur(sop)}")
        cas, _ = m303.casillas(ventas, compras, d, h, CERO)
        if (D2(cas.get("27", CERO)), D2(cas.get("45", CERO))) != (D2(rep), D2(sop)):
            k.avisos.append(f"{n}T: la contabilidad da [27] {eur(rep)} y [45] {eur(sop)}; el 303 de los libros, "
                            f"{eur(cas.get('27', CERO))} y {eur(cas.get('45', CERO))}")

    for i, (f, concepto, ap, fuente) in enumerate(sorted(borrador, key=lambda x: x[0]), start=1):
        k.asientos.append(Asiento(i, f, concepto, ap, fuente))
    descuadrados = [a.n for a in k.asientos if not a.cuadra]
    if descuadrados:
        k.avisos.append(f"asientos que no cuadran: {descuadrados}")
    p555 = k.saldo(("555",), -1)
    if p555:
        k.avisos.append(f"la 555 «Partidas pendientes de aplicación» tiene un saldo {'acreedor' if p555 > 0 else 'deudor'} de "
                        f"{eur(abs(p555))}: cobros, pagos o compras sin documento que hay que explicar")
    return k


# ─── los estados ────────────────────────────────────────────────────────────────────────────

def sumas_y_saldos(k: Contabilidad) -> list[dict]:
    return [{"cuenta": c, "nombre": k.nombres.get(c, ""), "debe": d, "haber": h,
             "deudor": D2(max(d - h, CERO)), "acreedor": D2(max(h - d, CERO))} for c, (d, h) in k.saldos().items()]


def perdidas_y_ganancias(k: Contabilidad) -> list[tuple[str, Decimal]]:
    """Modelo de pymes (PGC, tercera parte), con las partidas que GestorIA genera."""
    cifra = k.saldo(("70",), -1)
    aprov = -k.saldo(("60", "61"))
    personal = -k.saldo(("64",))
    otros = -k.saldo(("62", "63", "65"))
    amort = -k.saldo(("68",))
    explot = D2(cifra + aprov + personal + otros + amort)
    ing_fin, gas_fin = k.saldo(("76",), -1), -k.saldo(("66",))
    fin = D2(ing_fin + gas_fin)
    return [("1. Importe neto de la cifra de negocios", cifra), ("4. Aprovisionamientos", aprov),
            ("6. Gastos de personal", personal), ("7. Otros gastos de explotación", otros),
            ("8. Amortización del inmovilizado", amort), ("A.1) RESULTADO DE EXPLOTACIÓN", explot),
            ("12. Ingresos financieros", ing_fin), ("13. Gastos financieros", gas_fin),
            ("A.2) RESULTADO FINANCIERO", fin), ("A.3) RESULTADO ANTES DE IMPUESTOS", D2(explot + fin))]


def balance(k: Contabilidad) -> dict:
    """Activo y patrimonio neto y pasivo (modelo de pymes). Las cuentas con saldo de los dos lados
    (IVA del trimestre abierto, socio, 555) van al que les toca por su saldo."""
    s = {c: d - h for c, (d, h) in k.saldos().items()}
    resultado = perdidas_y_ganancias(k)[-1][1]
    deudoras = lambda prefijos: D2(sum((v for c, v in s.items() if c.startswith(prefijos) and v > 0), CERO))
    acreedoras = lambda prefijos: D2(-sum((v for c, v in s.items() if c.startswith(prefijos) and v < 0), CERO))
    otros = ("47", "551", "555", "46", "44")
    activo = [("A) ACTIVO NO CORRIENTE", None), ("II. Inmovilizado material", deudoras(("21",)) - acreedoras(("281",))),
              ("B) ACTIVO CORRIENTE", None), ("II. Existencias", deudoras(("30", "31", "32"))),
              ("III. Deudores comerciales y otras cuentas a cobrar", D2(deudoras(("43",)) + deudoras(otros))),
              ("VI. Efectivo y otros activos líquidos equivalentes", deudoras(("57",)))]
    pasivo = [("A) PATRIMONIO NETO", None), ("I. Capital", acreedoras(("10",))), ("III. Reservas", acreedoras(("11",))),
              ("VII. Resultado del ejercicio", D2(resultado + acreedoras(("129",)) - deudoras(("129",)))),
              ("C) PASIVO CORRIENTE", None),
              ("V. 1. Proveedores", D2(acreedoras(("40",)) + acreedoras(("523",)))),
              ("V. 2. Otros acreedores", D2(acreedoras(("41",)) + acreedoras(otros))),
              ("Efectivo en descubierto", acreedoras(("57",)))]
    total_a = D2(sum((v for _, v in activo if v is not None), CERO))
    total_p = D2(sum((v for _, v in pasivo if v is not None), CERO))
    return {"activo": activo, "pasivo": pasivo, "total_activo": total_a, "total_pasivo": total_p, "cuadra": total_a == total_p}


def libro_iva(ventas, compras, ejercicio: int) -> dict:
    """Los libros registro de IVA del ejercicio: emitidas (con la base y la cuota que van al 303) y recibidas."""
    from gestoria.modelos import m303

    por_numero = {v.factura: v for v in ventas}
    emitidas, recibidas = [], []
    for v in sorted((v for v in ventas if v.fecha.year == ejercicio), key=lambda x: (x.fecha, x.factura)):
        try:
            if v.regimen in ("intracomunitaria", "exportacion", "no_sujeta"):
                b, q = (v.base if v.base is not None else (v.total or CERO)), CERO
            elif v.rectifica and v.regimen == "rebu" and v.rectifica in por_numero:
                b, q = (-x for x in m303._base_cuota(por_numero[v.rectifica]))
            else:
                b, q = m303._base_cuota(v)
        except ValueError:
            b, q = CERO, CERO
        emitidas.append({"fecha": v.fecha, "trimestre": f"{(v.fecha.month - 1) // 3 + 1}T", "factura": v.factura, "cliente": v.cliente,
                         "nif": v.nif_cliente, "regimen": v.regimen, "tipo": v.tipo, "base": D2(b), "cuota": D2(q),
                         "total": D2(v.total) if v.total is not None else D2(b + q), "rectifica": v.rectifica})
    for c in sorted((c for c in compras if c.fecha.year == ejercicio), key=lambda x: (x.fecha, x.factura)):
        cuota = D2(c.cuota if c.cuota is not None else c.base * c.tipo / 100)
        recibidas.append({"fecha": c.fecha, "trimestre": f"{(c.fecha.month - 1) // 3 + 1}T", "factura": c.factura,
                          "proveedor": c.proveedor, "nif": c.nif_proveedor, "origen": c.origen, "gasto": c.gasto, "tipo": c.tipo,
                          "base": D2(c.base), "cuota": cuota, "deducible": c.deducible,
                          "total": D2(c.base + (CERO if c.origen == "intracomunitaria" else cuota))})
    return {"emitidas": emitidas, "recibidas": recibidas}
