"""Dígito de control de un NIF español: DNI, NIE y NIF de personas jurídicas (el antiguo CIF).

Un NIF con la letra o el dígito de control mal es una errata segura en el libro, y una factura
con el NIF del destinatario mal no es una factura completa (art. 6.1.d RD 1619/2012).
Algoritmos: letra del DNI/NIE (módulo 23, art. 11 RD 1553/2005) y dígito de control de las
personas jurídicas (Orden EHA/451/2008). Los NIF de otros países (prefijo de país, p. ej. IE…)
no se comprueban aquí: para ellos está el VIES.
"""
from __future__ import annotations

import re

LETRAS = "TRWAGMYFPDXBNJZSQVHLCKE"
LETRAS_CIF = "JABCDEFGHI"
SOLO_DIGITO = "ABEH"     # el control es un número
SOLO_LETRA = "KPQSNW"    # el control es una letra


def normalizar(nif: str) -> str:
    return re.sub(r"[\s\-.]", "", (nif or "")).upper()


def es_espanol(nif: str) -> bool:
    s = normalizar(nif)
    return bool(re.fullmatch(r"\d{8}[A-Z]|[XYZ]\d{7}[A-Z]|[A-HJ-NP-SUVW]\d{7}[0-9A-J]", s))


def valido(nif: str) -> bool:
    """True si el control cuadra. Para un NIF que no es español devuelve False: compruébalo en el VIES."""
    s = normalizar(nif)
    if re.fullmatch(r"\d{8}[A-Z]", s):
        return s[8] == LETRAS[int(s[:8]) % 23]
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", s):
        return s[8] == LETRAS[int(str("XYZ".index(s[0])) + s[1:8]) % 23]
    if re.fullmatch(r"[A-HJ-NP-SUVW]\d{7}[0-9A-J]", s):
        d = [int(c) for c in s[1:8]]
        pares = d[1] + d[3] + d[5]
        impares = sum(sum(divmod(x * 2, 10)) for x in (d[0], d[2], d[4], d[6]))
        control = (10 - (pares + impares) % 10) % 10
        letra, tipo = s[8], s[0]
        if tipo in SOLO_DIGITO:
            return letra == str(control)
        if tipo in SOLO_LETRA:
            return letra == LETRAS_CIF[control]
        return letra == str(control) or letra == LETRAS_CIF[control]
    return False
