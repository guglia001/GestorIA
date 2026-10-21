"""El README y INSTALAR.md no se quedan atrás: cada orden que citan existe, cada enlace y cada ancla llevan a
algo, y los dos mensajes de instalación mandan al agente a las instrucciones que tiene que seguir."""
import argparse
import re
from pathlib import Path

from gestoria import ordenes

RAIZ = Path(__file__).parent.parent
DOCS = ("README.md", "INSTALAR.md")


def _leer(doc: str) -> str:
    return (RAIZ / doc).read_text(encoding="utf-8")


def _sin_bloques(texto: str) -> str:
    return re.sub(r"```.*?```", "", texto, flags=re.S)


def _codigo(texto: str) -> list[str]:
    """Lo que va entre comillas invertidas: los bloques y el código en línea."""
    return re.findall(r"```[^\n]*\n(.*?)```", texto, re.S) + re.findall(r"`([^`\n]+)`", _sin_bloques(texto))


def _anclas(texto: str) -> set[str]:
    """Las anclas que GitHub les da a los títulos: minúsculas, sin puntuación y con guiones."""
    return {re.sub(r"[^\w\- ]", "", t.strip().lower()).replace(" ", "-")
            for t in re.findall(r"^#{1,6} (.+)$", _sin_bloques(texto), re.M)}


def test_cada_orden_citada_existe():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers()
    ordenes.registrar(sub)
    for doc in DOCS:
        for trozo in _codigo(_leer(doc)):
            for m in re.finditer(r"\bgestoria(?:\s+--carpeta\s+\S+)?\s+([a-z0-9][a-z0-9-]*)", trozo):
                assert m.group(1) in sub.choices, f"{doc}: `gestoria {m.group(1)}` no es una orden"


def test_los_enlaces_y_las_anclas_llevan_a_algo():
    for doc in DOCS:
        texto = _leer(doc)
        for destino in re.findall(r'(?:\]\(|src="|href=")([^)"\s]+)', _sin_bloques(texto)):
            if destino.startswith(("http://", "https://")):
                continue
            fichero, _, ancla = destino.partition("#")
            assert not fichero or (RAIZ / fichero).exists(), f"{doc}: {destino} no existe"
            if ancla:
                assert ancla in _anclas(_leer(fichero) if fichero else texto), f"{doc}: {destino} no lleva a ningún título"


def test_los_mensajes_de_instalacion_llevan_a_instalar_md():
    mensajes = [b for b in re.findall(r"```text\n(.*?)```", _leer("README.md"), re.S) if "Instala GestorIA" in b]
    assert len(mensajes) == 2 and "con el panel" in mensajes[0] and "sin el panel" in mensajes[1]
    assert all("INSTALAR.md" in m and "no te inventes ningún dato" in m for m in mensajes)
    instalar = _leer("INSTALAR.md")
    for paso in ("instalar-skills", "web --fichero", "PENDIENTE", "CLAUDE.md", "no se pide nunca en el chat",
                 "presentar` no va nunca en el cron"):
        assert paso in instalar, paso
