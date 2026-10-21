"""El certificado electrónico (.p12/.pfx) leído en local: de quién es, qué tipo es y cuándo
caduca. No sale a la red. Con el certificado caducado no se entra en ninguna sede, así que
GestorIA avisa con tiempo (60 días: lo que tarda en hacerse sin prisas una renovación).

También prepara la conexión TLS con certificado de cliente para los servicios web que no son
páginas (la comprobación de NIF de la AEAT): la clave privada se escribe un instante en una
carpeta temporal con permisos 700/600, se carga en memoria y se borra.

Atributos que se leen (los de la FNMT y la mayoría de prestadores cualificados españoles):
O (entidad representada), organizationIdentifier «VATES-B00000000» (su NIF), serialNumber
«IDCES-00000000T» (NIF de la persona), givenName/surname, la política del certificado
(«representante de persona jurídica» o de persona física) y, en los de la FNMT, el cargo.
"""
from __future__ import annotations

import os
import shutil
import ssl
import tempfile
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path

AVISO_DIAS = 60
ROJO_DIAS = 15
_CARGO_FNMT = "1.3.6.1.4.1.5734.1.20"
_ORG_ID = "2.5.4.97"


@dataclass
class Certificado:
    ruta: str
    tipo: str               # representante | persona | otro
    titular: str            # la persona que firma
    nif_titular: str
    entidad: str            # la sociedad representada ("" en uno de persona física)
    nif_entidad: str
    cargo: str
    emisor: str
    desde: date
    hasta: date

    @property
    def nif(self) -> str:
        """El NIF con el que entra en la sede: el de la entidad si es de representante."""
        return self.nif_entidad or self.nif_titular

    def dias(self, hoy: date | None = None) -> int:
        return (self.hasta - (hoy or date.today())).days

    def nivel(self, hoy: date | None = None) -> str:
        d = self.dias(hoy)
        return "🔴" if d <= ROJO_DIAS else "🟡" if d <= AVISO_DIAS else "🟢"

    def describir(self, hoy: date | None = None) -> str:
        quien = (f"representante de {self.entidad} ({self.nif_entidad}): {self.titular}"
                 + (f", {self.cargo}" if self.cargo else "")) if self.tipo == "representante" \
            else f"persona física: {self.titular} ({self.nif_titular})"
        d = self.dias(hoy)
        cuando = f"CADUCADO hace {-d} días" if d < 0 else f"caduca el {self.hasta.isoformat()} (en {d} días)"
        return f"{self.nivel(hoy)} {quien} · {self.emisor} · {cuando}"


def _cargar(ruta: Path, clave: str):
    from cryptography.hazmat.primitives.serialization import pkcs12

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # algunos .p12 de la FNMT vienen en BER, no en DER
        return pkcs12.load_key_and_certificates(Path(ruta).expanduser().read_bytes(), clave.encode())


def _attr(nombre, oid: str) -> str:
    from cryptography.x509.oid import ObjectIdentifier

    v = nombre.get_attributes_for_oid(ObjectIdentifier(oid))
    return str(v[0].value).strip() if v else ""


def _quitar_prefijo(nif: str) -> str:
    """«VATES-B00000000» → «B00000000» · «IDCES-00000000T» → «00000000T»."""
    return nif.split("-", 1)[1] if "-" in nif and nif[:2].isalpha() else nif


def describir_x509(c, ruta: str = "") -> Certificado:
    from cryptography import x509
    from cryptography.x509.oid import ExtensionOID, NameOID

    s = c.subject
    entidad = _attr(s, NameOID.ORGANIZATION_NAME.dotted_string)
    nif_entidad = _quitar_prefijo(_attr(s, _ORG_ID))
    nif_titular = _quitar_prefijo(_attr(s, NameOID.SERIAL_NUMBER.dotted_string))
    nombre = " ".join(x for x in (_attr(s, NameOID.GIVEN_NAME.dotted_string),
                                  _attr(s, NameOID.SURNAME.dotted_string)) if x) \
        or _attr(s, NameOID.COMMON_NAME.dotted_string)
    politicas = ""
    cargo = ""
    try:
        for p in c.extensions.get_extension_for_oid(ExtensionOID.CERTIFICATE_POLICIES).value:
            for q in p.policy_qualifiers or []:
                politicas += " " + (q if isinstance(q, str) else (q.explicit_text or ""))
    except x509.ExtensionNotFound:
        pass
    try:
        for g in c.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value:
            if isinstance(g, x509.DirectoryName):
                cargo = cargo or _attr(g.value, _CARGO_FNMT)
    except x509.ExtensionNotFound:
        pass
    if "representante" in politicas.lower() or (entidad and nif_entidad):
        tipo = "representante"
    elif nif_titular:
        tipo = "persona"
    else:
        tipo = "otro"
    emisor = _attr(c.issuer, NameOID.COMMON_NAME.dotted_string) or _attr(c.issuer, NameOID.ORGANIZATION_NAME.dotted_string)
    org_emisor = _attr(c.issuer, NameOID.ORGANIZATION_NAME.dotted_string)
    return Certificado(ruta=ruta, tipo=tipo, titular=nombre, nif_titular=nif_titular,
                       entidad=entidad if tipo == "representante" else "",
                       nif_entidad=nif_entidad if tipo == "representante" else "", cargo=cargo,
                       emisor=f"{emisor} ({org_emisor})" if org_emisor and org_emisor not in emisor else emisor,
                       desde=c.not_valid_before_utc.date(), hasta=c.not_valid_after_utc.date())


def leer(ruta: str | Path, clave: str) -> Certificado:
    _, c, _ = _cargar(Path(ruta), clave)
    if c is None:
        raise ValueError(f"{ruta}: el fichero no trae certificado")
    return describir_x509(c, str(ruta))


def contexto_tls(ruta: str | Path, clave: str) -> ssl.SSLContext:
    """Contexto TLS con el certificado de cliente, para urllib. La clave sin cifrar existe en
    disco solo mientras se carga (carpeta 700, fichero 600) y se borra antes de devolverlo."""
    from cryptography.hazmat.primitives import serialization

    k, c, extra = _cargar(Path(ruta), clave)
    d = Path(tempfile.mkdtemp(prefix="gestoria_"))
    try:
        os.chmod(d, 0o700)
        cf, kf = d / "c.pem", d / "k.pem"
        cf.write_bytes(c.public_bytes(serialization.Encoding.PEM)
                       + b"".join(e.public_bytes(serialization.Encoding.PEM) for e in extra or []))
        kf.touch(mode=0o600)
        kf.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(cf, kf)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return ctx
