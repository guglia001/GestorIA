"""GestorIA: tu agente de IA hace de gestor en España. Lleva tus cuentas, prepara y revisa tus impuestos y los
presenta solo con tu conformidad; las consultas a las sedes son de solo lectura."""
from decimal import ROUND_HALF_UP, Decimal

__version__ = "0.2.0"


def D2(x) -> Decimal:
    """Importe a 2 decimales con redondeo «medio hacia arriba», el de la AEAT."""
    return Decimal(str(x if x is not None else 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
