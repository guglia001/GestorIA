---
name: normativa-fiscal
description: "Use when answering any Spanish tax, VAT, accounting, company-law or Seguridad Social question — IVA/REBU, modelos 303/349/390/347/200/202/111/130/036/100, ROI/VIES, OSS, Impuesto sobre Sociedades, IRPF, retenciones, RETA, facturación, Veri*factu, plan contable, cuentas anuales, Registro Mercantil, plazos, recargos, sanciones — or when a blog, a gestoría or an earlier answer states a fact nobody has checked against an official source."
---

# Normativa fiscal: fuente oficial primero, y citada

Una respuesta fiscal sin fuente oficial es una opinión. Con el artículo o la página del manual
delante, ya es trabajo de gestor.

## Orden de fuentes (gana la de arriba)

| # | fuente | cómo |
|---|---|---|
| 1 | **BOE consolidado**: el texto vigente del artículo | `gestoria boe <ID> <artículo>` (tabla de abajo) |
| 2 | **Consultas vinculantes de la DGT** | https://petete.tributos.hacienda.gob.es/consultas/ |
| 3 | **Doctrina del TEAC** | https://serviciostelematicosext.hacienda.gob.es/TEAC/DYCTEA/ |
| 4 | **Manuales prácticos de la AEAT** | `gestoria manuales "<texto>" --manual iva` |
| 5 | **INFORMA y fichas de procedimiento** | https://www2.agenciatributaria.gob.es/ES13/S/IAFRIAFRIINF |
| 6 | Blogs y asesorías | solo para saber qué artículo o casilla buscar; si contradicen a 1-5, mandan 1-5 |

| ámbito | norma | ID del BOE |
|---|---|---|
| IVA | Ley 37/1992 · Reglamento (RD 1624/1992) | `BOE-A-1992-28740` · `BOE-A-1992-28925` |
| Sociedades | Ley 27/2014 | `BOE-A-2014-12328` |
| IRPF | Ley 35/2006 · Reglamento (RD 439/2007) | `BOE-A-2006-20764` · `BOE-A-2007-6820` |
| procedimiento | LGT 58/2003 · RGAT (RD 1065/2007) · Ley 39/2015 (notificaciones: arts. 40-44) | `BOE-A-2003-23186` · `BOE-A-2007-15984` · `BOE-A-2015-10565` |
| facturación | RD 1619/2012 · Veri*factu (RD 1007/2023) | `BOE-A-2012-14696` · `BOE-A-2023-24840` |
| mercantil | LSC (RDLeg 1/2010) · Código de Comercio · Ley 14/2013 | `BOE-A-2010-10544` · `BOE-A-1885-6627` · `BOE-A-2013-10074` |
| contabilidad | PGC de pymes (RD 1515/2007) · PGC (RD 1514/2007) | `BOE-A-2007-19966` · `BOE-A-2007-19884` |
| Seguridad Social | LGSS (RDLeg 8/2015; pluriactividad: art. 313) · Estatuto del trabajo autónomo (Ley 20/2007) | `BOE-A-2015-11724` · `BOE-A-2007-13409` |
| haciendas locales | TRLRHL (RDLeg 2/2004; IAE: art. 82) | `BOE-A-2004-4214` |

Un anuncio del Ministerio **no es norma** hasta que sale en el BOE. Para un periodo pasado, la
redacción que estaba vigente entonces (el BOE consolidado guarda las versiones).

## La respuesta tiene esta forma

1. **Respuesta corta**: sí, no o la cifra.
2. **Cada afirmación con su fuente**: artículo o página, URL y «consultado DD-mmm-AAAA». Cita
   literal cuando la palabra exacta importa (plazos, casillas, «se entenderá denegada»).
3. **Marca de certeza**: ✅ fuente oficial leída · ⚠️ solo fuente secundaria o interpretación (y dilo).
4. **Lo que depende de los datos de la persona** (qué tiene presentado, notificaciones, censo,
   poderes, cuota de autónomo) se mira en la sede con su certificado (`gestoria chequeo` o la orden
   concreta), no se supone.

## Errores típicos

| dicho | realidad |
|---|---|
| «La gestoría ya presentó el alta en el ROI» | Se mira en la sede: `gestoria presentados --modelo 036` y `gestoria roi` (la AEAT certifica si constas, con CSV) |
| «Sin VIES, la plataforma te cobra el IVA de su país» | Depende de qué entidad factura y desde dónde: mira la factura (NIF del emisor y tipo aplicado) antes de calcular nada |
| «Retención del 19 % para el socio» | Depende de qué se le paga: procedimiento general de retenciones (arts. 80 y 86 RIRPF) |
| Blogs «contradictorios» sobre una casilla del 036 | La guía oficial del 036 lo aclara (`gestoria manuales "<casilla>" --manual censal`) |
| En REBU, cuota = base × tipo | La base es el margen menos el IVA que lleva dentro: cuota = margen × tipo/(100 + tipo), operación a operación (art. 137 LIVA) |
| «Un ordenador de 1.200 € es bien de inversión» | Para el IVA no: lo es solo si pasa de 3.005,06 € (art. 108.Dos.5.º LIVA). En el IS o el IRPF sí se amortiza |
| «Si no la abro, a los 10 días se da por notificada» | Solo si la vía electrónica es obligatoria o elegida (art. 43.2 Ley 39/2015); si no, llega en papel |

## Qué no se hace

Presentar, firmar, pagar o contestar un requerimiento. Las decisiones de régimen (REBU o general,
OSS, sueldo o dividendo) se presentan como opciones, cada una con su fuente: decide la persona.
