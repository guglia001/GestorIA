"""Las skills solo nombran órdenes que existen: si se renombra una orden, esto avisa."""
import argparse
import re
from pathlib import Path

from gestoria import ordenes

RAIZ = Path(__file__).parent.parent


def _ordenes_registradas() -> set[str]:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers()
    ordenes.registrar(sub)
    return set(sub.choices)


def test_las_skills_citan_ordenes_que_existen():
    existentes = _ordenes_registradas()
    citadas = set()
    for f in RAIZ.glob("skills/*/SKILL.md"):
        citadas |= set(re.findall(r"`gestoria ([a-z0-9-]+)", f.read_text(encoding="utf-8")))
    assert citadas, "ninguna skill cita una orden"
    assert citadas <= existentes, citadas - existentes


def test_cada_skill_tiene_frontmatter_y_la_regla_de_presentar():
    for f in RAIZ.glob("skills/*/SKILL.md"):
        t = f.read_text(encoding="utf-8")
        assert t.startswith("---\nname: ") and "description:" in t, f
        assert re.search(r"presenta|presentar", t, re.I), f
    # presentar solo con las tres llaves, y sin reintentar a ciegas
    p = (RAIZ / "skills" / "presentar-declaraciones" / "SKILL.md").read_text(encoding="utf-8")
    assert all(x in p for x in ("revisión", "ensayo", "conformidad", "gestoria presentados", "se reintenta"))
