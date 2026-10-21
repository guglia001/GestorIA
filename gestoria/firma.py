"""Firmar con AutoFirma, la aplicación de firma del Gobierno de España, en línea de órdenes.

Dos usos:
- `gestoria firmar <fichero>`: firma un documento con tu certificado, en tu equipo: PAdES si es un
  PDF, Facturae si es una factura electrónica, XAdES si es otro XML y CAdES para lo demás.
- Las sedes que firman con AutoFirma desde la web, con su JavaScript (`AutoScript`, o el antiguo
  `MiniApplet`): `enganchar()` cambia su `sign()` por una llamada a AutoFirma en línea de órdenes
  con tu certificado, sin abrir la aplicación ni pedirte nada. Solo lo hace el navegador de una
  orden que firma (`Navegador(..., firmar=con_certificado(...))`), y cada firma queda apuntada.

La AEAT no la necesita: sus declaraciones se firman en su propio diálogo («Conforme» → «Firmar y
Enviar») con el certificado con el que entras.

AutoFirma 1.9 (`autofirmacl`, paquete oficial de firmaelectronica.gob.es, que trae Java):
`sign -i <entrada> -o <salida> -format cades|pades|xades|facturae -algorithm sha256
-config <propiedades> -store pkcs12:<p12> -password <clave> -alias <alias> -xml`, que contesta
`<afirma><result>true</result>…` o `false` con el motivo (comprobado el 21-oct-2026). La firma
CAdES de AutoFirma lleva `id-smime-aa-contentHint`, y hay sedes que rechazan una CAdES hecha con
`openssl cms`: por eso se firma con AutoFirma y no con otra cosa. La contraseña del certificado va
en la línea de órdenes, porque AutoFirma no la lee de otro sitio: mientras firma, tu usuario la
puede ver con `ps`.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

FORMATOS = ("cades", "pades", "xades", "facturae", "auto")   # auto: PAdES un PDF, XAdES un XML, CAdES lo demás
EXTENSION = {"cades": ".csig", "pades": ".pdf", "xades": ".xsig", "facturae": ".xsig", "auto": ".firma"}
# lo que piden las páginas (AutoScript/MiniApplet) → el formato de la línea de órdenes
_FORMATO_WEB = {"cades": "cades", "cadestri": "cades", "pades": "pades", "padestri": "pades", "xades": "xades",
                "xadestri": "xades", "facturae": "facturae", "facturaetri": "facturae", "auto": "auto"}


class ErrorFirma(RuntimeError):
    """AutoFirma no está o no ha podido firmar; el motivo, en el mensaje."""


def ejecutable() -> str | None:
    return shutil.which("autofirmacl") or shutil.which("autofirma")


def _autofirma(args: list[str]) -> str:
    exe = ejecutable()
    if not exe:
        raise ErrorFirma("no encuentro AutoFirma: instálala desde https://firmaelectronica.gob.es "
                         "(paquete «autofirma», que trae Java)")
    r = subprocess.run([exe, *args, "-xml"], capture_output=True, text=True, timeout=300)
    m = re.search(r"<afirma>.*?</afirma>", (r.stdout or "") + (r.stderr or ""), re.S)
    if not m:
        raise ErrorFirma(f"AutoFirma no ha contestado: {((r.stderr or r.stdout) or '').strip()[-200:]}")
    if re.search(r"<result>\s*(true|ok)\s*</result>", m.group(0)):
        return m.group(0)
    motivo = re.search(r"<msg>(.*?)</msg>", m.group(0), re.S)
    raise ErrorFirma(f"AutoFirma: {(motivo.group(1) if motivo else m.group(0)).strip()}")


def _almacen(pfx) -> list[str]:
    return ["-store", f"pkcs12:{Path(pfx).expanduser()}"]


def alias(pfx, clave: str) -> str:
    """El alias de la clave del certificado dentro del .p12 (AutoFirma lo pide para firmar)."""
    hay = re.findall(r"<alias>(.*?)</alias>", _autofirma(["listaliases", *_almacen(pfx), "-password", clave]))
    if not hay:
        raise ErrorFirma("el certificado no tiene ninguna clave con la que firmar")
    return hay[0]


def formato_de(fichero: Path) -> str:
    fichero = Path(fichero)
    if fichero.suffix.lower() == ".pdf":
        return "pades"
    if fichero.suffix.lower() in (".xml", ".xsig"):
        cabeza = fichero.read_bytes()[:4000]
        return "facturae" if b"Facturae" in cabeza else "xades"
    return "cades"


def firmar_fichero(entrada, pfx, clave: str, salida=None, formato: str | None = None,
                   algoritmo: str = "sha256", config: str = "") -> Path:
    """Firma `entrada` con AutoFirma y devuelve la ruta de la firma (por defecto, al lado:
    `<nombre>_firmado.pdf` en PAdES, `.csig` en CAdES, `.xsig` en XAdES/Facturae)."""
    entrada = Path(entrada).expanduser()
    formato = (formato or formato_de(entrada)).lower()
    if formato not in FORMATOS:
        raise ErrorFirma(f"formato «{formato}»: AutoFirma firma en {', '.join(FORMATOS)}")
    salida = Path(salida) if salida else entrada.with_name(f"{entrada.stem}_firmado{EXTENSION[formato]}")
    args = ["sign", "-i", str(entrada), "-o", str(salida), "-format", formato, "-algorithm", algoritmo,
            *_almacen(pfx), "-password", clave, "-alias", alias(pfx, clave)]
    if config:
        args += ["-config", config]
    _autofirma(args)
    if not salida.is_file() or not salida.stat().st_size:
        raise ErrorFirma("AutoFirma dice que ha firmado, pero no ha dejado el fichero")
    return salida


def firmar_datos(datos: bytes, formato: str, pfx, clave: str, algoritmo: str = "sha256", config: str = "") -> bytes:
    """Firma unos bytes (en una carpeta temporal solo tuya, que se borra al acabar)."""
    with tempfile.TemporaryDirectory(prefix="gestoria-firma-") as d:
        os.chmod(d, 0o700)
        entrada = Path(d) / "datos"
        entrada.write_bytes(datos)
        return firmar_fichero(entrada, pfx, clave, Path(d) / "firma", formato, algoritmo, config).read_bytes()


def certificado_b64(pfx, clave: str) -> str:
    """El certificado (sin la clave) en base64, que es lo que esperan las páginas junto a la firma."""
    from cryptography.hazmat.primitives.serialization import Encoding

    from gestoria.certificado import _cargar

    _, cert, _ = _cargar(Path(pfx), clave)
    return base64.b64encode(cert.public_bytes(Encoding.DER)).decode()


def con_certificado(pfx, clave: str, registro: Path | None = None, fichero: Path | None = None):
    """El `firmar` que se le da al Navegador: atiende el `sign()` de la página con AutoFirma y
    apunta en `registro` (una línea por firma) qué se firmó, cuándo y en qué formato. Si la página
    no da los datos (quiere que elijas un fichero, como haría la aplicación), firma `fichero`."""

    def firmar(operacion: str, datos_b64: str, algoritmo: str, formato: str, params: str) -> tuple[str, str]:
        if operacion != "sign":
            raise ErrorFirma(f"la página pide «{operacion}»: GestorIA solo hace firmas simples")
        fmt = _FORMATO_WEB.get(re.sub(r"[^a-z]", "", (formato or "").lower()))
        if not fmt:
            raise ErrorFirma(f"la página pide una firma «{formato}»: GestorIA firma en {', '.join(FORMATOS)}")
        alg = re.sub(r"with.*$", "", algoritmo or "", flags=re.I).lower() or "sha256"
        if datos_b64:
            datos = base64.b64decode(datos_b64)
        elif fichero:
            datos = Path(fichero).expanduser().read_bytes()
        else:
            raise ErrorFirma("la página quiere que elijas el fichero que firmar: dile a GestorIA cuál "
                             "(o fírmalo con `gestoria firmar <fichero>`)")
        firma = firmar_datos(datos, fmt, pfx, clave, alg, (params or "").replace("\\n", "\n"))
        if registro:
            registro.parent.mkdir(parents=True, exist_ok=True)
            with open(registro, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')} {fmt} {alg} {len(datos)} bytes "
                        f"sha256={hashlib.sha256(datos).hexdigest()}\n")
        return base64.b64encode(firma).decode(), certificado_b64(pfx, clave)

    return firmar


# Se instala antes que el JavaScript de la página: cuando la página define `AutoScript` o
# `MiniApplet` (con `var`, que en el ámbito global pasa por el «set» de window), se envuelve.
GANCHO = r"""
(() => {
  if (window.__gestoriaFirma) return;
  window.__gestoriaFirma = true;
  const fallar = (args, msg) => {
    const ko = [...args].reverse().find(a => typeof a === "function");
    if (ko) ko("es.gob.afirma.core.AOException", msg);
  };
  const firmar = function (...args) {            // sign(datos, algoritmo, formato, params, ok, ko)
    const [datos, algoritmo, formato, params] = args;
    const funciones = args.filter(a => typeof a === "function");
    const ok = funciones[0], ko = funciones[1];
    window.gestoriaFirmar("sign", datos || "", algoritmo || "", formato || "", params || "")
      .then(r => { if (ok) ok(r.firma, r.certificado); })
      .catch(e => { if (ko) ko("es.gob.afirma.core.AOException", String((e && e.message) || e)); });
  };
  const nada = function () {};
  const envolver = (o) => {
    if (!o || (typeof o !== "object" && typeof o !== "function") || o.__gestoria) return o;
    if (typeof o.sign === "function") o.sign = firmar;
    for (const op of ["coSign", "cosign", "counterSign", "countersign", "signBatch", "signAndSaveToFile"]) {
      if (typeof o[op] === "function") o[op] = function (...a) { fallar(a, "GestorIA solo hace firmas simples (sign)"); };
    }
    for (const op of ["cargarMiniApplet", "cargarAppAfirma", "setServlets", "setForceWSMode", "setLocale",
                      "setStickySignatory", "checkTime", "setJnlpService"]) {
      if (typeof o[op] === "function") o[op] = nada;
    }
    try { Object.defineProperty(o, "__gestoria", { value: true }); } catch (e) {}
    return o;
  };
  for (const nombre of ["AutoScript", "MiniApplet"]) {
    let actual;
    try {
      Object.defineProperty(window, nombre, { configurable: true, enumerable: true,
        get() { return actual; }, set(v) { actual = envolver(v); } });
    } catch (e) {}
  }
})();
"""


def enganchar(ctx, firmar) -> None:
    """Instala el gancho en un contexto de Playwright: las páginas que llamen a AutoFirma desde
    su JavaScript reciben la firma de `firmar` (normalmente, `con_certificado(...)`)."""

    def atender(_fuente, operacion, datos, algoritmo, formato, params):
        f, c = firmar(operacion, datos, algoritmo, formato, params)
        return {"firma": f, "certificado": c}

    ctx.expose_binding("gestoriaFirmar", atender)
    ctx.add_init_script(GANCHO)
