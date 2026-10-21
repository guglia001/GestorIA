"""gestoria — tu agente de IA hace de gestor: lleva tus cuentas, te dice qué vence y cuánto apartar, prepara y revisa
tus impuestos y los presenta solo con tu conformidad (`gestoria presentar`). Las consultas a las sedes son de solo lectura."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def carpeta_de(a) -> Path:
    """La carpeta del contribuyente: --carpeta, $GESTORIA_CARPETA o el directorio actual."""
    c = a.carpeta or os.environ.get("GESTORIA_CARPETA") or "."
    return Path(c).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gestoria", description=__doc__)
    ap.add_argument("--carpeta", help="carpeta con perfil.toml y libros/ (o $GESTORIA_CARPETA)")
    sub = ap.add_subparsers(dest="orden", required=True)
    from gestoria import ordenes

    ordenes.registrar(sub)
    a = ap.parse_args(argv)
    if os.environ.get("GESTORIA_DEPURAR"):
        return a.func(a)
    try:
        return a.func(a)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # una sede lenta o caída: el mensaje, no el volcado (GESTORIA_DEPURAR=1 lo enseña)
        primera = (str(e).strip().splitlines() or [""])[0][:300]
        print(f"❌ {type(e).__name__}: {primera}", file=sys.stderr)
        print("   No he cambiado nada. Si es una sede, vuelve a probar en un rato o mírala a mano.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
