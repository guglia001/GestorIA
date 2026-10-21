"""Importes escritos a la española («1.234,56 €») o a la inglesa («1234.56») → Decimal."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from gestoria import D2


def eur(x) -> str:
    """Decimal('1234.5') → «1.234,50 €»."""
    s = f"{D2(x):,.2f}".replace(",", "\0").replace(".", ",").replace("\0", ".")
    return f"{s} €"


def importe(txt) -> Decimal | None:
    s = str(txt if txt is not None else "").replace("€", "").replace(" ", "").strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return D2(Decimal(s))
    except InvalidOperation as e:
        raise ValueError(f"importe ilegible: {txt!r}") from e
