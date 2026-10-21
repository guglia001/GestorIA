"""Navegador con certificado para las sedes electrónicas: de SOLO LECTURA salvo al presentar.

Un Chromium sin ventana que presenta el certificado del contribuyente como certificado de
cliente TLS en cada servidor que lo pide (Playwright `client_certificates`, un origen por
servidor: no admite comodines). Sirve para la AEAT, la Seguridad Social (Import@ss) y todo lo que
entra por Cl@ve (la DEHú, por ejemplo).

Lo único que pulsa son botones de consulta («Buscar», «Consultar», «Aceptar» de un formulario de
búsqueda) y enlaces de navegación. Antes de cada pulsación se comprueba el nombre contra
PROHIBIDO: firmar, presentar, pagar, comparecer (abrir una notificación), revocar, renunciar,
confirmar, modificar, dar de alta o de baja, domiciliar, solicitar, aportar, contestar… Si una
pantalla pide algo de eso para seguir, GestorIA se para y lo dice.

La única excepción es `gestoria presentar` (gestoria/presentar.py): abre el navegador con
`presentar=True` y solo entonces `pulsar_para_presentar()` acepta los botones de PRESENTAR, y
ninguno más. El certificado se carga solo para los servidores de esa presentación: los de pruebas
(`aeat_pruebas`) en el ensayo, los de verdad en la presentación.

Servidores comprobados el 21-oct-2026: la AEAT pide el certificado en www1, www2 y www12; la
Seguridad Social en ipce.seg-social.es (después de idp.seg-social.es); Cl@ve en
pasarela-ident.clave.gob.es. La DEHú rechaza el agente «HeadlessChrome»: se usa uno normal.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

ORIGENES = {
    "aeat": ("https://www1.agenciatributaria.gob.es", "https://www2.agenciatributaria.gob.es",
             "https://www12.agenciatributaria.gob.es", "https://sede.agenciatributaria.gob.es"),
    "seguridad_social": ("https://idp.seg-social.es", "https://ipce.seg-social.es",
                         "https://portal.seg-social.gob.es", "https://sp.seg-social.es"),
    "clave": ("https://pasarela.clave.gob.es", "https://pasarela-ident.clave.gob.es",
              "https://pasarela-ident-sistemas.clave.gob.es"),
    "dehu": ("https://dehu.redsara.es",),
    # entorno de pruebas de la AEAT (preproducción): lo presentado ahí «no tiene en ningún caso
    # trascendencia tributaria» (https://preportal.aeat.es, 21-oct-2026)
    "aeat_pruebas": ("https://prewww1.aeat.es", "https://prewww2.aeat.es"),
}
# Los botones que solo `gestoria presentar` puede pulsar (diálogo de firma de la AEAT: «Firmar y
# Enviar» → «Conforme» → «Firmar y Enviar»; «Confirmar» abre la ventana censal del modelo).
PRESENTAR = ("Confirmar", "Presentar declaración", "Firmar y Enviar", "Conforme")
# y para llegar de la ventana censal al formulario, solo enlaces de navegación como estos
PRESENTAR_NAVEGAR = re.compile(r"(continuar( con la presentaci[oó]n( del modelo \d{3})?)?|ir al formulario|"
                               r"formulario( del modelo)?( \d{3})?|cumplimentar( la)? declaraci[oó]n)", re.I)
AGENTE = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/141.0.0.0 Safari/537.36")
PROHIBIDO = re.compile(
    r"firm|present|\bpag(ar|o|a)\b|compare|revoc|renunci|confirm|pr[oó]rrog|modific|rectific|anul|"
    r"\bbaja\b|\balta\b|domicili|solicit|aport|contest|alega|elimin|borra|cancel|suscrib|"
    r"descarg.*documento|acceder al contenido", re.I)


class Prohibido(RuntimeError):
    """Una pantalla pedía pulsar algo que cambia cosas: GestorIA no lo hace."""


def comprobar(nombre: str) -> None:
    if PROHIBIDO.search(nombre or ""):
        raise Prohibido(f"GestorIA no pulsa «{nombre}»: solo lee (eso lo hace la persona)")


class Navegador:
    """`with Navegador(pfx, clave) as nav:` · `nav.texto(url)` · `nav.pulsar(pg, "Buscar")`."""

    def __init__(self, pfx: Path, clave: str, capturas: Path | None = None,
                 sitios: tuple[str, ...] = ("aeat", "seguridad_social", "clave", "dehu"),
                 presentar: bool = False, firmar=None):
        self.pfx, self.clave, self.capturas = str(Path(pfx).expanduser()), clave, capturas
        self.origenes = [o for s in sitios for o in ORIGENES[s]]
        self.presentar = presentar
        self.firmar = firmar    # si una sede pide AutoFirma: (operación, datos, algoritmo, formato, params) → (firma, cert)
        self._p = self._nav = self.ctx = None

    def __enter__(self) -> "Navegador":
        from playwright.sync_api import sync_playwright

        self._p = sync_playwright().start()
        self._nav = self._p.chromium.launch(headless=True)
        self.ctx = self._nav.new_context(
            locale="es-ES", user_agent=AGENTE, accept_downloads=True,
            client_certificates=[{"origin": o, "pfxPath": self.pfx, "passphrase": self.clave}
                                 for o in self.origenes])
        if self.firmar:
            from gestoria import firma
            firma.enganchar(self.ctx, self.firmar)
        return self

    def __exit__(self, *exc) -> None:
        try:
            self._nav.close()
        finally:
            self._p.stop()

    def abrir(self, url: str, espera: int = 2000):
        pg = self.ctx.new_page()
        pg.goto(url, timeout=90000, wait_until="networkidle")
        pg.wait_for_timeout(espera)
        return pg

    def pulsar(self, pg, nombre: str, rol: str = "button", espera: int = 5000):
        """Pulsa un botón (o enlace) de consulta por su nombre visible. Si abre otra pestaña,
        devuelve esa. El nombre pasa antes por PROHIBIDO."""
        comprobar(nombre)
        return self._pulsar(pg, nombre, rol, espera)

    def pulsar_para_presentar(self, pg, nombre: str, rol: str = "button", espera: int = 5000):
        """Los botones de PRESENTAR, solo dentro de `gestoria presentar` y solo esos."""
        if not self.presentar:
            raise Prohibido(f"«{nombre}» solo se pulsa dentro de `gestoria presentar`")
        if nombre not in PRESENTAR and not PRESENTAR_NAVEGAR.fullmatch(nombre.strip()):
            raise Prohibido(f"«{nombre}» no es un botón de la presentación: GestorIA no lo pulsa")
        return self._pulsar(pg, nombre, rol, espera)

    def _pulsar(self, pg, nombre: str, rol: str, espera: int):
        n = len(self.ctx.pages)
        loc = pg.get_by_role(rol, name=nombre)
        if not loc.count():
            loc = pg.get_by_text(nombre, exact=True)
        loc.first.click()
        pg.wait_for_timeout(espera)
        if len(self.ctx.pages) > n:
            pg = self.ctx.pages[-1]
        try:
            pg.wait_for_load_state("networkidle", timeout=30000)
        except Exception:  # alguna sede no llega nunca a «networkidle»
            pass
        return pg

    def rellenar(self, pg, selector: str, valor: str) -> None:
        pg.locator(selector).first.fill(valor)

    def texto(self, url: str, pulsar: tuple[str, ...] = (), enlaces: tuple[str, ...] = (),
              rellenar: dict[str, str] | None = None, etiqueta: str = "") -> str:
        """Abre `url`, rellena los campos de búsqueda, pulsa los enlaces y botones de consulta
        indicados y devuelve el texto de la página (y la captura, si hay carpeta)."""
        pg = self.abrir(url)
        try:
            for css, valor in (rellenar or {}).items():
                self.rellenar(pg, css, valor)
            for e in enlaces:
                pg = self.pulsar(pg, e, rol="link")
            for b in pulsar:
                pg = self.pulsar(pg, b)
            self.captura(pg, etiqueta)
            return pg.inner_text("body")
        finally:
            for p in list(self.ctx.pages):
                p.close()

    def html(self, url: str, enlaces: tuple[str, ...] = ()) -> str:
        pg = self.abrir(url)
        try:
            for e in enlaces:
                pg = self.pulsar(pg, e, rol="link")
            return pg.content()
        finally:
            for p in list(self.ctx.pages):
                p.close()

    def captura(self, pg, etiqueta: str) -> None:
        if not (self.capturas and etiqueta):
            return
        self.capturas.mkdir(parents=True, exist_ok=True)
        sello = datetime.now().strftime("%Y%m%dT%H%M%S")
        pg.screenshot(path=str(self.capturas / f"{sello}_{etiqueta}.png"), full_page=True)
