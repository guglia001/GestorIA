"""perfil.toml: quién es el contribuyente, de qué está dado de alta (su censo, modelo 036/037) y
los datos que la hucha necesita y no están en los libros (cuota de autónomos, cifra del año
anterior, si la SL es de nueva creación).

Certificados: `[sede]` es el principal (el de la empresa, o el tuyo si eres autónomo) y
`[sede.personal]`, opcional, el de persona física del administrador o del titular: con él se
miran sus notificaciones, su Seguridad Social y la DEHú. Las contraseñas nunca van aquí.

`[pago] iban` es la cuenta para domiciliar lo que salga a ingresar y para las devoluciones (va en
la página DID del fichero del 303). `[banco]` dice de dónde salen los movimientos del banco para
conciliar: los ficheros que dejes en `banco/` y, si quieres, la descarga con las cookies de tu
sesión (`cookies`, `url_descarga`, `url_movimientos`). `[ayudas]` dice dónde estás (`region`, con el
nombre que usa la Base de Datos Nacional de Subvenciones: «Madrid», «Mallorca», «Comunidad
Valenciana»…) y qué te describe (`palabras`), para `gestoria ayudas`."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass
class Perfil:
    nif: str
    nombre: str
    tipo: str
    iva_regimen: str = "general"
    forma_pago: str = "I"
    modelos: list[str] = field(default_factory=list)
    certificado: str | None = None
    clave_fichero: str | None = None
    personal: dict = field(default_factory=dict)   # [sede.personal]: certificado y clave_fichero
    iban: str | None = None                     # [pago] iban: domiciliación y devoluciones
    banco: dict = field(default_factory=dict)   # [banco]: cookies, url_descarga, url_movimientos
    ayudas: dict = field(default_factory=dict)  # [ayudas]: region (como la llama la BDNS) y palabras que te describen
    # SL (Impuesto sobre Sociedades)
    is_nueva_creacion: bool = False
    is_tipo: Decimal | None = None              # tipo forzado a mano, en %
    cifra_negocios_anterior: Decimal | None = None
    ejercicio_inicio: date | None = None        # si el primer ejercicio no empezó el 1 de enero
    # autónomo (IRPF y Seguridad Social)
    estimacion: str = "directa"                 # directa | objetiva (módulos, no soportado)
    reta_mensual: Decimal | None = None
    rendimiento_neto_anterior: Decimal | None = None

    def tiene_certificado(self, cual: str = "principal") -> bool:
        return bool(self.certificado if cual == "principal" else self.personal.get("certificado"))

    def ruta_certificado(self, cual: str = "principal") -> Path:
        ruta = self.certificado if cual == "principal" else self.personal.get("certificado")
        if not ruta:
            seccion = "[sede]" if cual == "principal" else "[sede.personal]"
            raise ValueError(f"perfil.toml no tiene {seccion} certificado = \"ruta al .p12/.pfx\"")
        return Path(ruta).expanduser()

    def clave_certificado(self, cual: str = "principal") -> str:
        """La contraseña del certificado: $GESTORIA_CERT_CLAVE ($GESTORIA_CERT_CLAVE_PERSONAL para el
        personal) o el fichero de clave_fichero (con permisos 600, fuera de cualquier repo). Nunca
        va en perfil.toml."""
        import os

        var = "GESTORIA_CERT_CLAVE" if cual == "principal" else "GESTORIA_CERT_CLAVE_PERSONAL"
        if os.environ.get(var):
            return os.environ[var]
        fichero = self.clave_fichero if cual == "principal" else self.personal.get("clave_fichero")
        if fichero:
            return Path(fichero).expanduser().read_text().strip()
        seccion = "[sede]" if cual == "principal" else "[sede.personal]"
        raise ValueError(f"falta la clave del certificado: ${var} o {seccion} clave_fichero")


def _dec(x) -> Decimal | None:
    return None if x is None or x == "" else Decimal(str(x))


def cargar(carpeta: Path) -> Perfil:
    f = Path(carpeta) / "perfil.toml"
    if not f.is_file():
        raise FileNotFoundError(f"no hay {f}: copia ejemplos/sl-demo/perfil.toml y rellénalo")
    d = tomllib.loads(f.read_text(encoding="utf-8"))
    tipo = d.get("tipo", "")
    if tipo not in ("sl", "autonomo"):
        raise ValueError(f"perfil.toml: tipo = «{tipo}»; tiene que ser «sl» o «autonomo»")
    iva, sede, is_, au = d.get("iva", {}), d.get("sede", {}), d.get("is", {}), d.get("autonomo", {})
    iban = (d.get("pago", {}).get("iban") or iva.get("iban") or "").replace(" ", "").upper() or None
    inicio = is_.get("ejercicio_inicio")
    return Perfil(nif=d["nif"].strip().upper(), nombre=d["nombre"], tipo=tipo,
                  iva_regimen=iva.get("regimen", "general"), forma_pago=iva.get("forma_pago", "I"),
                  modelos=[str(m) for m in d.get("obligaciones", {}).get("modelos", [])],
                  certificado=sede.get("certificado"), clave_fichero=sede.get("clave_fichero"),
                  personal=dict(sede.get("personal") or {}), iban=iban, banco=dict(d.get("banco") or {}),
                  ayudas=dict(d.get("ayudas") or {}),
                  is_nueva_creacion=bool(is_.get("nueva_creacion", False)),
                  is_tipo=_dec(is_.get("tipo")),
                  cifra_negocios_anterior=_dec(is_.get("cifra_negocios_anterior")),
                  ejercicio_inicio=inicio if isinstance(inicio, date) else (date.fromisoformat(inicio) if inicio else None),
                  estimacion=au.get("estimacion", "directa"), reta_mensual=_dec(au.get("reta_mensual")),
                  rendimiento_neto_anterior=_dec(au.get("rendimiento_neto_anterior")))
