"""Ningún dato real en el repo: solo los NIF inventados de los ejemplos, ningún certificado ni clave.
Se miran los ficheros que git sigue Y los nuevos que aún no se han añadido (los ignorados por
.gitignore no, que ahí viven salida/ y los certificados): así un fichero recién creado no se
publica sin pasar por aquí."""
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).parent.parent


def _ficheros() -> list[str]:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=RAIZ,
                         capture_output=True, text=True).stdout.split("\n")
    return sorted({f for f in out if f})
NIF = re.compile(r"\b[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]\b|\b\d{8}[A-Z]\b|\b[XYZ]\d{7}[A-Z]\b")
IBAN = re.compile(r"\bES\d{2}[ ]?\d{4}[ ]?\d{4}[ ]?\d{2}[ ]?\d{10}\b")
CORREO = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
PERMITIDOS = {"B00000000", "00000000T", "B00000018", "B00000026", "B00000034", "A00000042", "B00000059", "B00000067",
              "12345678Z", "X1234567L", "B12345674", "B12345670", "Q1234567D", "Q12345674", "B00000001", "12345678A", "X1234567A"}  # inventados
CORREOS_PERMITIDOS = {"gestoria@localhost", "demo@example.com", "noreply@anthropic.com"}
UID_CALENDARIO = re.compile(r"^[0-9a-z]{26}@google\.com$")  # UID de evento del calendario público de la AEAT
BINARIOS = (".xlsx", ".xls", ".png", ".webp", ".pdf")


def test_sin_nif_iban_ni_correos_reales():
    ficheros = _ficheros()
    assert "README.md" in ficheros and "gestoria/web.py" in ficheros
    malos = []
    for f in ficheros:
        p = RAIZ / f
        if p.suffix in BINARIOS or not p.is_file():
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        malos += [(f, m) for m in NIF.findall(t) if m not in PERMITIDOS]
        malos += [(f, m) for m in IBAN.findall(t)]
        malos += [(f, m) for m in CORREO.findall(t)
                  if m not in CORREOS_PERMITIDOS and not (f.endswith(".ics") and UID_CALENDARIO.match(m))]
    assert not malos, malos


def test_sin_certificados_ni_claves_privadas():
    ficheros = _ficheros()
    assert not [f for f in ficheros if f.lower().endswith((".p12", ".pfx", ".pem", ".key"))]
    clave = re.compile("-----BEGIN [A-Z ]*" + "PRIVATE" + " KEY-----")   # partido: si no, se encuentra a sí mismo
    for f in ficheros:
        p = RAIZ / f
        if p.is_file() and p.suffix not in BINARIOS:
            assert not clave.search(p.read_text(encoding="utf-8", errors="ignore")), f
