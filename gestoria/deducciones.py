"""Qué te puedes deducir y qué no, comprobado contra tus libros y tu banco, cada regla con su artículo.

Una gestoría con ochenta clientes no repasa factura a factura qué deduce y qué no. Esto sí: toma las
reglas de la Ley del IRPF, la del IVA y la del Impuesto sobre Sociedades (leídas en el BOE el
21-oct-2026 y citadas una a una), las cruza con `libros/compras.csv` y con el banco y dice, regla a
regla:

- ✅ ya la usas (consta en tus libros);
- ⚠️ parece que te la estás dejando, o que te pasas de un límite: pregúntatelo;
- ℹ️ depende de datos que los libros no llevan (metros de la vivienda, uso del coche, plantilla…);
- ⛔ algo de lo que tienes NO deduce.

Con `--comprobar` vuelve a leer cada artículo en el BOE en ese momento y comprueba que la cifra sigue
ahí: si Hacienda cambia un límite, se ve el mismo día (el workflow nocturno lo prueba también).

No decide por ti: que un bien está afecto, que el coche es de uso exclusivo o que un gasto está
correlacionado con los ingresos es una prueba que tiene que poder aportar la persona (art. 106.4 LGT).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from gestoria import D2
from gestoria.numeros import eur

CERO = D2(0)
TIPOS = {"gasto": "Gastos que deducen", "reduccion": "Reducciones de la base", "deduccion": "Deducciones y tipos",
         "no": "Lo que no deduce"}


@dataclass(frozen=True)
class Regla:
    clave: str
    nombre: str
    aplica: tuple[str, ...]        # ("autonomo",), ("sl",) o las dos
    tipo: str                      # gasto | reduccion | deduccion | no
    que: str                       # la regla, en una frase
    fuente: str                    # el artículo (lo que se cita)
    boe: tuple[str, str]           # (identificador del BOE, artículo) para --comprobar
    cifra: str                     # texto literal que tiene que seguir en ese artículo
    patron: str | None = None      # qué proveedores lo parecen (sobre el nombre en mayúsculas y sin acentos)
    manual: str | None = None      # qué buscar en los manuales de la AEAT para leer más


REGLAS: tuple[Regla, ...] = (
    # ─── gastos del autónomo (estimación directa) ─────────────────────────────────────────────
    Regla("reta", "Cuota de autónomos (RETA)", ("autonomo",), "gasto",
          "Las cotizaciones del titular a la Seguridad Social son gasto de la actividad: el rendimiento neto se "
          "calcula con las normas del Impuesto sobre Sociedades, y ahí es un gasto más.",
          "art. 28.1 LIRPF; art. 10.3 LIS", ("BOE-A-2006-20764", "28"), "normas del Impuesto sobre Sociedades",
          patron=r"SEGURIDAD SOCIAL|\bTGSS\b|\bRETA\b|CUOTA AUTONOM", manual="cotizaciones titular Seguridad Social"),
    Regla("seguro_salud", "Seguro de enfermedad", ("autonomo",), "gasto",
          "Las primas del seguro de enfermedad del titular, de su cónyuge y de los hijos menores de 25 años que "
          "convivan con él: hasta 500 € por persona y año (1.500 € con discapacidad).",
          "art. 30.2.5.ª.a LIRPF", ("BOE-A-2006-20764", "30"), "500 euros",
          patron=r"SANITAS|ADESLAS|\bDKV\b|ASISA|ASISTENCIA SANITARIA|SEGURO.*(SALUD|MEDIC|ENFERMEDAD)|(SALUD|MEDIC).*SEGURO|"
                 r"MAPFRE SALUD|AXA SALUD|CIGNA|AEGON SALUD"),
    Regla("suministros", "Suministros de la vivienda en la que trabajas", ("autonomo",), "gasto",
          "Si trabajas en parte de tu vivienda habitual, el agua, el gas, la luz, el teléfono e internet deducen "
          "en el 30 % de la proporción de metros cuadrados que dedicas a la actividad (un local solo para la "
          "actividad deduce el 100 %).",
          "art. 30.2.5.ª.b LIRPF", ("BOE-A-2006-20764", "30"), "30 por ciento",
          patron=r"IBERDROLA|ENDESA|NATURGY|HOLALUZ|OCTOPUS|TOTALENERGIES|REPSOL (LUZ|GAS|ENERG)|ENERGIA|ELECTRIC|MOVISTAR|"
                 r"TELEFONICA|VODAFONE|ORANGE|\bDIGI\b|MASMOVIL|YOIGO|PEPEPHONE|JAZZTEL|\bO2\b|TELEFON|FIBRA|\bAGUAS?\b|"
                 r"CANAL DE ISABEL|AQUALIA|EMASESA|\bGAS\b"),
    Regla("manutencion", "Comidas por la actividad (manutención)", ("autonomo",), "gasto",
          "Tus comidas por la actividad, en restaurantes y hostelería y pagadas con tarjeta u otro medio "
          "electrónico: hasta 26,67 € al día en España y 48,08 € en el extranjero (el doble si pernoctas fuera).",
          "art. 30.2.5.ª.c LIRPF; art. 9.A.3 RIRPF (las cuantías)", ("BOE-A-2007-6820", "9"), "26,67",
          patron=r"RESTAURAN|\bBAR\b|CAFETER|\bCAFE\b|COMIDA|MENU DEL DIA|HOSTELER|TABERNA|\bMESON\b|PIZZER|BURGER|SUSHI"),
    Regla("dificil", "Gastos de difícil justificación", ("autonomo",), "gasto",
          "En estimación directa simplificada, el 5 % del rendimiento neto positivo se deduce sin factura, con el "
          "tope de 2.000 € al año (y se pierde si aplicas la reducción del art. 32.2.1.º).",
          "art. 30.2.4.ª LIRPF; art. 30.2.ª RIRPF", ("BOE-A-2007-6820", "30"), "5 por ciento"),
    Regla("inicio", "Reducción del 20 % por empezar", ("autonomo",), "reduccion",
          "Si empezaste la actividad sin haber tenido otra el año anterior, declaras un 20 % menos de rendimiento "
          "neto el primer año que sea positivo y el siguiente (hasta 100.000 € de rendimiento), salvo que más de "
          "la mitad de los ingresos vengan de quien fue tu empleador el año anterior.",
          "art. 32.3 LIRPF", ("BOE-A-2006-20764", "32"), "20 por ciento"),
    Regla("plan_pensiones", "Plan de pensiones", ("autonomo",), "reduccion",
          "Lo que aportas a tu plan de pensiones no es gasto de la actividad: reduce la base general de la renta "
          "hasta 1.500 € al año, y hasta 4.250 € más si es un plan de empleo simplificado de autónomos o sectorial.",
          "arts. 51 y 52 LIRPF", ("BOE-A-2006-20764", "52"), "1.500 euros"),
    # ─── SL ──────────────────────────────────────────────────────────────────────────────────
    Regla("sueldo_admin", "Retribución del administrador", ("sl",), "gasto",
          "Lo que la sociedad paga al administrador deduce si los estatutos dicen que el cargo es retribuido (si "
          "no, es gratuito por ley); lo que cobra por alta dirección o por un contrato laboral no es liberalidad.",
          "art. 217 LSC; art. 15.e LIS", ("BOE-A-2010-10544", "217"), "gratuito", patron=r"\bNOMINA"),
    Regla("atenciones", "Atenciones a clientes y proveedores", ("sl",), "gasto",
          "Regalos, comidas e invitaciones a clientes o proveedores deducen en el IS hasta el 1 % de la cifra de "
          "negocios del año; su IVA no se deduce nunca.",
          "art. 15.e LIS; art. 96.Uno.5.º LIVA", ("BOE-A-2014-12328", "15"), "1 por ciento",
          patron=r"RESTAURAN|CATERING|REGALO|OBSEQUIO|\bLOTES?\b|CESTA|INVITACI|\bBAR\b|CAFETER"),
    Regla("nueva_creacion", "Tipo del 15 % de nueva creación", ("sl",), "deduccion",
          "Una sociedad nueva con actividad económica tributa al 15 % el primer ejercicio con base positiva y el "
          "siguiente (no si la actividad la hacía antes un socio con más del 50 % o una entidad vinculada).",
          "art. 29.1 LIS", ("BOE-A-2014-12328", "29"), "15 por ciento"),
    Regla("reducida", "Empresa de reducida dimensión", ("sl",), "deduccion",
          "Con menos de 10 millones de cifra de negocios el año anterior, los elementos nuevos se amortizan al "
          "doble del coeficiente de tablas y se deduce un 1 % de los saldos de clientes por posibles "
          "insolvencias sin esperar a que se demoren.",
          "arts. 101, 103 y 104 LIS", ("BOE-A-2014-12328", "104"), "1 por ciento"),
    Regla("capitalizacion", "Reserva de capitalización", ("sl",), "reduccion",
          "Si dejas el beneficio en la sociedad en vez de repartirlo, el ejercicio siguiente reduces la base en "
          "el 20 % del incremento de fondos propios (23 % o más si además crece la plantilla), manteniéndolo 3 "
          "años; tope del 20 % de la base (25 % si facturas menos de 1 M€).",
          "art. 25 LIS", ("BOE-A-2014-12328", "25"), "20 por ciento"),
    Regla("nivelacion", "Reserva de nivelación", ("sl",), "reduccion",
          "Una empresa de reducida dimensión que tributa al tipo general o a la escala de microempresa puede "
          "minorar la base hasta el 10 % (máximo 1 M€); lo devuelve en los 5 años siguientes contra pérdidas, o "
          "al cabo de 5 años. No vale mientras tributes al 15 % de nueva creación.",
          "art. 105 LIS", ("BOE-A-2014-12328", "105"), "10 por ciento"),
    Regla("idi", "I+D e innovación tecnológica", ("sl",), "deduccion",
          "Los gastos de un proyecto de investigación y desarrollo deducen el 25 % en la cuota (el 42 % sobre lo "
          "que supere la media de los 2 años anteriores) y los de innovación tecnológica el 12 %, individualizados "
          "por proyecto; un informe motivado del Ministerio da seguridad jurídica.",
          "art. 35 LIS", ("BOE-A-2014-12328", "35"), "25 por ciento",
          patron=r"I\+D|INVESTIGACI|\bDESARROLLO\b|PROTOTIP|LABORATORIO|INGENIER"),
    Regla("discapacidad", "Contratar a personas con discapacidad", ("sl",), "deduccion",
          "9.000 € de deducción en la cuota por cada persona/año de aumento de plantilla con discapacidad del 33 "
          "al 65 %, y 12.000 € si es del 65 % o más.",
          "art. 38 LIS", ("BOE-A-2014-12328", "38"), "9.000 euros"),
    # ─── los dos ─────────────────────────────────────────────────────────────────────────────
    Regla("alquiler", "Alquiler del local o del despacho", ("autonomo", "sl"), "gasto",
          "El alquiler de un local afecto deduce, y su IVA también. Si el arrendador es un particular o una "
          "sociedad, le retienes el 19 % y lo ingresas con el modelo 115.",
          "art. 28.1 LIRPF / art. 10.3 LIS; art. 101.8 LIRPF (la retención)", ("BOE-A-2006-20764", "101"),
          "arrendamiento o subarrendamiento de bienes inmuebles urbanos",
          patron=r"ALQUILER|ARRENDA|INMOBILIAR|COWORKING|\bLOCAL\b|OFICINA"),
    Regla("vehiculo", "Vehículo: combustible, taller, seguro, peajes, aparcamiento", ("autonomo", "sl"), "gasto",
          "En el IRPF un turismo solo deduce si es de uso exclusivo para la actividad (el uso privado accesorio "
          "no vale para turismos, salvo transportistas, agentes comerciales, autoescuelas o taxis); en el IVA se "
          "presume afecto al 50 % salvo prueba (100 % en vehículos mixtos de mercancías o de agentes comerciales). "
          "En una SL deduce en la medida en que esté afecto, y el uso privado es retribución en especie.",
          "art. 22.4 RIRPF; art. 95.Tres.2.ª LIVA", ("BOE-A-1992-28740", "95"), "50 por 100",
          patron=r"GASOLINER|REPSOL|CEPSA|\bBP\b|\bGALP\b|SHELL|PETRONOR|CARBURANT|TALLER|NEUMATIC|\bITV\b|PARKING|"
                 r"APARCAMIENTO|PEAJE|AUTOPISTA|RENTING|SEGURO.*(COCHE|AUTO|VEHIC|MOTO)|CONCESIONARIO|LAVADO"),
    Regla("inversiones", "Inversiones: se amortizan, no se restan enteras", ("autonomo", "sl"), "gasto",
          "Un bien que dura más de un año no se deduce entero el año que lo compras: se amortiza por tablas. Los "
          "elementos nuevos de hasta 300 € se amortizan libremente (hasta 25.000 € al año). Para el IVA solo es "
          "bien de inversión si pasa de 3.005,06 €.",
          "art. 12.1 y 12.3.e LIS (al IRPF por el art. 28.1 LIRPF); art. 108.Dos.5.º LIVA", ("BOE-A-2014-12328", "12"),
          "300 euros"),
    Regla("servicios", "Gestoría, software, formación, cuotas, material, publicidad, transporte", ("autonomo", "sl"), "gasto",
          "Deduce todo gasto correlacionado con los ingresos, con factura completa y anotado en los libros: "
          "asesoría, programas y hosting, formación y libros de la actividad, cuota del colegio profesional, "
          "material, publicidad, envíos.",
          "art. 28.1 LIRPF / art. 10.3 LIS; art. 97 LIVA (la factura); art. 106.4 LGT (la prueba)", ("BOE-A-2003-23186", "106"),
          "factura",
          patron=r"GESTOR|ASESOR|SOFTWARE|SAAS|HOSTING|DOMINIO|INFORMATIC|CURSO|FORMACION|ACADEMIA|LIBRER|COLEGIO (OFICIAL|PROFESIONAL|DE)|"
                 r"PAPELER|MATERIAL|PUBLICIDAD|MARKETING|TRANSPORT|MENSAJER|CORREOS|\bSEUR\b|\bMRW\b|\bGLS\b|\bDHL\b|\bUPS\b"),
    Regla("donativos", "Donativos a fundaciones y ONG", ("autonomo", "sl"), "deduccion",
          "Un donativo a una entidad de la Ley 49/2002 no es gasto: en el IS deduce el 40 % en la cuota (más si "
          "repites tres años), con la base limitada al 15 % de la base imponible; en el IRPF deduce también en la "
          "cuota (art. 19 de la misma ley).",
          "art. 20 Ley 49/2002 (IS); art. 19 (IRPF)", ("BOE-A-2002-25039", "20"), "40 %",
          patron=r"FUNDACION|\bONG\b|CARITAS|CRUZ ROJA|UNICEF|ACNUR|MEDICOS SIN|OXFAM|GREENPEACE|AMNISTIA|DONATIVO|DONACION"),
    # ─── lo que no deduce ────────────────────────────────────────────────────────────────────
    Regla("no_deducibles", "Multas, sanciones, recargos y el propio impuesto", ("autonomo", "sl"), "no",
          "No deducen nunca: las multas y sanciones, los recargos de Hacienda, el propio Impuesto sobre "
          "Sociedades, las liberalidades y las pérdidas del juego.",
          "art. 15 LIS (y art. 28.1 LIRPF)", ("BOE-A-2014-12328", "15"), "multas y sanciones",
          patron=r"MULTA|SANCION|RECARGO|\bDGT\b|JEFATURA.*TRAFICO|LOTERIA|APUESTA"),
    Regla("iva_excluido", "IVA que no se deduce", ("autonomo", "sl"), "no",
          "Nunca deduce el IVA de joyas, alimentos, bebidas y tabaco, espectáculos y ocio, atenciones a clientes "
          "o empleados, ni el de viajes y hostelería salvo que el gasto deduzca en el IRPF o en el IS.",
          "art. 96.Uno LIVA", ("BOE-A-1992-28740", "96"), "joyas",
          patron=r"JOYER|VINOTECA|BODEGA|TABAC|ESTANCO|\bCINE\b|TEATRO|ESPECTACULO|CONCIERTO|\bSPA\b|GIMNASIO|VIAJES|HOTEL"),
    Regla("sin_factura", "Compras sin factura completa o sin NIF", ("autonomo", "sl"), "no",
          "Sin factura completa (con el NIF del proveedor y el tuyo) el IVA no se deduce, y el gasto se queda sin "
          "su justificante prioritario.",
          "art. 97.Uno LIVA; art. 106.4 LGT", ("BOE-A-1992-28740", "97"), "factura original"),
)


@dataclass
class Hallazgo:
    regla: Regla
    estado: str                     # ✅ ⚠️ ℹ️ ⛔
    texto: str
    facturas: list = field(default_factory=list)
    importe: Decimal = CERO

    def __str__(self) -> str:
        return f"{self.estado} {self.regla.nombre}: {self.texto} ({self.regla.fuente})"


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()


def _parecen(regla: Regla, compras) -> list:
    """Las compras del año cuyo proveedor parece de esta regla (las inversiones tienen su propia regla)."""
    if not regla.patron:
        return []
    return [c for c in compras if c.gasto != "inversion" and re.search(regla.patron, _norm(c.proveedor))]


def _lista(facturas, n: int = 3) -> str:
    nombres = []
    for c in facturas:
        if c.proveedor not in nombres:
            nombres.append(c.proveedor)
    return ", ".join(nombres[:n]) + (f" y {len(nombres) - n} más" if len(nombres) > n else "")


def revisar(pf, ventas, compras, aj: dict, extractos, hoy: date) -> list[Hallazgo]:
    """Cada regla que te aplica, con lo que dicen tus libros y tu banco de ella."""
    from gestoria import banco, hucha

    ej = hoy.year
    compras_ej = [c for c in compras if c.fecha.year == ej]
    ingresos, gastos, _ = hucha.ingresos_gastos(ventas, compras, date(ej, 1, 1), date(ej + 1, 1, 1))
    neto = D2(ingresos - gastos)
    conc = banco.conciliar(extractos, ventas, compras, hoy) if extractos else None
    por_categoria: dict[str, Decimal] = {}
    for m, cat, _nota in (conc.explicados if conc else []):
        if m.fecha.year == ej:
            por_categoria[cat] = por_categoria.get(cat, CERO) + abs(m.importe)
    out: list[Hallazgo] = []
    for r in REGLAS:
        if pf.tipo not in r.aplica:
            continue
        f = _parecen(r, compras_ej)
        base = D2(sum((c.base for c in f), CERO))
        consta = f"consta: {len(f)} factura(s), {eur(base)} de base ({_lista(f)})"
        h = None
        if r.clave == "reta":
            ss = por_categoria.get("Seguridad Social", CERO)
            if ss or f:
                h = Hallazgo(r, "✅", (f"consta: {eur(ss)} pagados a la Seguridad Social este año según el banco" if ss else consta)
                             + (f"; la hucha cuenta {eur(pf.reta_mensual)} al mes" if pf.reta_mensual else ""), f, ss or base)
            elif pf.reta_mensual:
                h = Hallazgo(r, "✅", f"perfil.toml dice {eur(pf.reta_mensual)} al mes ({eur(pf.reta_mensual * 12)} al año): gasto deducible "
                                     "entero; con el extracto en banco/ se comprueba lo pagado de verdad", importe=D2(pf.reta_mensual * 12))
            else:
                h = Hallazgo(r, "⚠️", "no consta ningún pago a la Seguridad Social ni en el banco ni en compras.csv: si pagas la cuota, "
                                      "es gasto deducible (deja el extracto en banco/ o pon reta_mensual en perfil.toml)")
        elif r.clave == "dificil":
            est = min(D2(neto * Decimal("0.05")), D2(2000)) if neto > 0 and pf.estimacion == "directa" else CERO
            h = Hallazgo(r, "ℹ️", f"con los libros de hoy, rendimiento neto {eur(neto)} → unos {eur(est)} este año; se aplica en la renta, "
                                  "no hace falta factura", importe=est)
        elif r.clave == "inicio":
            if not pf.rendimiento_neto_anterior:
                est = D2(min(neto, D2(100000)) * Decimal("0.20")) if neto > 0 else CERO
                h = Hallazgo(r, "⚠️", f"perfil.toml no trae rendimiento_neto_anterior: si empezaste este año o el pasado, te tocan unos "
                                      f"{eur(est)} menos de rendimiento con los libros de hoy; compruébalo", importe=est)
            else:
                h = Hallazgo(r, "ℹ️", "el año pasado ya tuviste rendimiento: solo vale el primer año positivo y el siguiente")
        elif r.clave == "plan_pensiones":
            h = Hallazgo(r, "ℹ️", "no sale de los libros: si aportas, va en la renta, no en la actividad")
        elif r.clave == "inversiones":
            inv = [c for c in compras_ej if c.gasto == "inversion"]
            if inv:
                libres = [c for c in inv if c.base <= 300]
                h = Hallazgo(r, "✅", f"{len(inv)} inversión(es) por {eur(sum((c.base for c in inv), CERO))} ({_lista(inv)})"
                             + (f"; {len(libres)} de hasta 300 € con libertad de amortización" if libres else "")
                             + "; la amortización no se calcula todavía", inv)
            else:
                h = Hallazgo(r, "ℹ️", "ninguna compra marcada como inversión este año (columna gasto = inversion)")
        elif r.clave == "atenciones":
            limite = D2(ingresos * Decimal("0.01"))
            if f and base > limite:
                h = Hallazgo(r, "⚠️", f"{consta}: pasa del 1 % de la cifra de negocios ({eur(limite)}); el exceso no deduce", f, base)
            elif f:
                h = Hallazgo(r, "✅", f"{consta}; límite este año {eur(limite)}; su IVA no se deduce", f, base)
            else:
                h = Hallazgo(r, "ℹ️", f"nada que lo parezca en compras.csv; el límite de este año sería {eur(limite)}")
        elif r.clave == "nueva_creacion":
            h = Hallazgo(r, "✅", "perfil.toml dice nueva_creacion = true: la hucha ya calcula el IS al 15 %") if pf.is_nueva_creacion \
                else Hallazgo(r, "ℹ️", "no marcado en perfil.toml ([is] nueva_creacion); si la sociedad es nueva y nadie hacía antes la actividad, "
                                      "te toca")
        elif r.clave == "reducida":
            cifra = pf.cifra_negocios_anterior if pf.cifra_negocios_anterior is not None else ingresos
            h = Hallazgo(r, "✅", f"cifra de negocios {eur(cifra)}, muy por debajo de 10 M€: puedes amortizar al doble y dotar el 1 % de clientes") \
                if cifra < 10_000_000 else Hallazgo(r, "ℹ️", f"cifra de negocios {eur(cifra)}: fuera del régimen (10 M€)")
        elif r.clave == "capitalizacion":
            est = D2(max(neto, CERO) * Decimal("0.20"))
            h = Hallazgo(r, "ℹ️", f"resultado de este año hasta hoy {eur(max(neto, CERO))}: si lo dejas en la sociedad, el ejercicio que viene "
                                  f"puedes reducir la base hasta en {eur(est)} (20 %)", importe=est)
        elif r.clave == "nivelacion":
            if pf.is_nueva_creacion:
                h = Hallazgo(r, "ℹ️", "no mientras tributes al 15 % de nueva creación; después, hasta el 10 % de la base")
            else:
                est = D2(max(neto, CERO) * Decimal("0.10"))
                h = Hallazgo(r, "ℹ️", f"con la base de hoy ({eur(max(neto, CERO))}) podrías minorar hasta {eur(est)}, a devolver en 5 años "
                                      "si no hay pérdidas", importe=est)
        elif r.clave == "idi":
            h = Hallazgo(r, "⚠️", f"{consta}: si es un proyecto de I+D o de innovación individualizado, hay deducción del 25 % o del 12 %", f, base) \
                if f else Hallazgo(r, "ℹ️", "nada que lo parezca en compras.csv")
        elif r.clave == "discapacidad":
            h = Hallazgo(r, "ℹ️", "depende de la plantilla, que los libros no llevan")
        elif r.clave == "sueldo_admin":
            nom = por_categoria.get("nóminas", CERO)
            h = Hallazgo(r, "✅", f"hay nóminas en el banco ({eur(nom)} este año): comprueba que los estatutos prevén el cargo retribuido", importe=nom) \
                if nom or f else Hallazgo(r, "ℹ️", "no hay nóminas en el banco: si el administrador cobra, que los estatutos lo digan y pase por nómina")
        elif r.clave == "sin_factura":
            sin_nif = [c for c in compras_ej if not c.nif_proveedor]
            no_ded = [c for c in compras_ej if not c.deducible]
            if sin_nif or no_ded:
                partes = []
                if sin_nif:
                    partes.append(f"{len(sin_nif)} compra(s) sin NIF del proveedor ({_lista(sin_nif)}): su IVA no deduce")
                if no_ded:
                    partes.append(f"{len(no_ded)} marcada(s) por ti como no deducibles ({_lista(no_ded)})")
                h = Hallazgo(r, "⛔", "; ".join(partes), sin_nif + no_ded, D2(sum((c.base for c in sin_nif + no_ded), CERO)))
            else:
                h = Hallazgo(r, "✅", "todas las compras del año llevan el NIF del proveedor y están marcadas como deducibles")
        elif r.tipo == "no":
            h = Hallazgo(r, "⛔", f"{consta}: revisa si deduce de verdad", f, base) if f else Hallazgo(r, "✅", "nada de esto en tus libros")
        elif r.clave == "vehiculo":
            h = Hallazgo(r, "⚠️", f"{consta}: en el IRPF solo deduce si el coche es de uso exclusivo; en el IVA, el 50 % salvo que pruebes más", f, base) \
                if f else Hallazgo(r, "ℹ️", "nada que lo parezca en compras.csv")
        elif r.clave == "donativos":
            h = Hallazgo(r, "ℹ️", f"{consta}: no son gasto, deducen en la cuota si la entidad está acogida a la Ley 49/2002", f, base) \
                if f else Hallazgo(r, "ℹ️", "nada que lo parezca en compras.csv")
        elif f:
            h = Hallazgo(r, "✅", consta, f, base)
        else:
            h = Hallazgo(r, "⚠️", "no consta nada que lo parezca en compras.csv: si lo pagas, pide la factura a tu nombre y anótala")
        out.append(h)
    return out


def comprobar(reglas=REGLAS) -> dict[str, dict]:
    """Lee cada artículo en el BOE AHORA y busca la cifra: {clave: {ok, parrafo, url, consultado}}."""
    from gestoria import boe

    out: dict[str, dict] = {}
    cache: dict[tuple[str, str], dict] = {}
    for r in reglas:
        if r.boe not in cache:
            cache[r.boe] = boe.articulo(*r.boe)
        a = cache[r.boe]
        # el BOE escribe «40 %» con un espacio fino o duro (U+202F, U+00A0): se compara con espacios normales
        texto = a["texto"].replace(" ", " ").replace("\xa0", " ").replace(" ", " ")
        parrafo = next((p for p in texto.splitlines() if r.cifra in p), "")
        out[r.clave] = {"ok": bool(parrafo), "parrafo": parrafo, "url": a["url"], "consultado": a.get("consultado", "")}
    return out


def texto(hallazgos: list[Hallazgo], pf, hoy: date, n_compras: int, n_banco: int, comprobado: dict | None = None) -> str:
    from gestoria import calendario

    cuenta = {e: sum(1 for h in hallazgos if h.estado == e) for e in ("✅", "⚠️", "ℹ️", "⛔")}
    L = [f"🧾 Qué te puedes deducir · {pf.nombre} ({'SL' if pf.tipo == 'sl' else 'autónomo'}) · con los libros de {hoy.year} "
         f"a {calendario.fecha_txt(hoy)}",
         f"   {n_compras} facturas recibidas y {n_banco} movimientos del banco. Cada regla con su artículo"
         + ("; leídos en el BOE ahora mismo." if comprobado else " (`--comprobar` los lee en el BOE ahora mismo).")]
    for tipo, titulo in TIPOS.items():
        hs = [h for h in hallazgos if h.regla.tipo == tipo]
        if not hs:
            continue
        L += ["", f"## {titulo}"]
        for h in hs:
            L.append(f"{h.estado} {h.regla.nombre} — {h.regla.fuente}")
            L.append(f"   {h.regla.que}")
            L.append(f"   → {h.texto}")
            if comprobado and h.regla.clave in comprobado:
                c = comprobado[h.regla.clave]
                L.append(f"   {'✅' if c['ok'] else '⚠️'} BOE {c['consultado']}: " + (f"«{c['parrafo'][:160]}…»" if c["ok"] else
                         f"no encuentro «{h.regla.cifra}» en el art. {h.regla.boe[1]}: la norma puede haber cambiado, léela: {c['url']}"))
            if h.regla.manual:
                L.append(f"   más: gestoria manuales \"{h.regla.manual}\" --manual renta")
    L += ["", f"Resumen: {cuenta['✅']} ✅ ya lo usas · {cuenta['⚠️']} ⚠️ por mirar · {cuenta['ℹ️']} ℹ️ depende de ti · {cuenta['⛔']} ⛔ no deduce",
          "Lo que un gasto deduce lo prueba la persona (art. 106.4 LGT): los metros de la vivienda, el uso del coche, la correlación con los ingresos."]
    return "\n".join(L)


def markdown(t: str, pf, hoy: date) -> str:
    return f"# Deducciones · {pf.nombre} · {hoy.isoformat()}\n\n```\n{t}\n```\n"


def guardar(carpeta: Path, t: str, pf, hoy: date) -> Path:
    salida = Path(carpeta) / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    f = salida / f"deducciones_{hoy.isoformat()}.md"
    f.write_text(markdown(t, pf, hoy), encoding="utf-8")
    return f
