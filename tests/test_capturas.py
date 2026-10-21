"""El octubre inventado de docs/capturas.py (el de las capturas del README) corre entero sin red:
chequeo → vigía → panel → chequeo → cotejo, con las órdenes de verdad y las sedes inventadas."""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).parent.parent


def _capturas():
    spec = importlib.util.spec_from_file_location("capturas", RAIZ / "docs" / "capturas.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_el_mes_de_las_capturas(tmp_path):
    s = _capturas().simular(tmp_path, red=False)
    _, vigia, rc = s["vigia"]
    assert rc == 2 and "2 en rojo, 1 nuevo(s)" in vigia
    assert "🆕 🔴 DEHú: notificación PENDIENTE de Ayuntamiento Demo" in vigia      # la de la víspera no es nueva
    assert "  🔴 DEHú: notificación PENDIENTE de Diputación Demo" in vigia
    _, hoy, rc = s["hoy"]
    assert rc == 2 and "Hucha: aparta 199,04 €" in hoy and "DEHú: 2 notificación(es) pendiente(s)" in hoy
    assert "(hace 16 h)" in hoy and "Último chequeo (2026-10-01)" in hoy and "(en 48 días)" in hoy
    titulo, informe = s["chequeo"]
    assert titulo == "~/.gestoria/bicis-demo/salida/chequeo_2026-10-21.md"
    assert informe.startswith("# 🔴 Chequeo con certificado · BICIS DEMO SL (B00000000) · 2026-10-21")
    for trozo in ("Transportes Demo SL (B00000026): NO está en el censo", "GESTORIA DEMO SL (B00000067) puede recibir y ABRIR",
                  "no coincide con tus libros en 8 casilla(s)", "la sede te tiene de alta en el 111", "SL unipersonal"):
        assert trozo in informe, trozo
    assert "Diputación Demo" not in informe                                        # se abrió el 15-oct
    _, cotejo, rc = s["cotejar"]
    assert rc == 1 and "se dedujo 20,00 € MÁS IVA" in cotejo and "en calidad de colaborador social" in cotejo
    assert "~/.gestoria/bicis-demo/salida/presentado/" in cotejo
    _, revision, rc = s["presentar"]
    assert rc == 1 and "PRESENTAR 303 3T 2026 B00000000 67,60" in revision and "⛔" not in revision  # solo el aviso REBU
    assert "✅ pago: domiciliado" in revision and "✅ simulador" in revision and "--pruebas --conforme" in revision
    _, banco, rc = s["banco"]
    assert rc == 1 and "9 casados con una factura" in banco and "BIZUM DE PEDRO DEMO" in banco
    assert "BICIS DEMO SL" in s["web"] and '"cuadra": true' in s["web"]
    _, deducciones, rc = s["deducciones"]
    assert rc == 0 and "✅ Tipo del 15 % de nueva creación" in deducciones and "6 ✅ ya lo usas" in deducciones
    _, ayudas, rc = s["ayudas"]
    assert rc == 0 and "🟢 abierta hasta el dom 15-nov-2026 · AYUNTAMIENTO DEMO (local)" in ayudas
    assert "habla de: bicicleta" in ayudas and "🔴 cerrada el mié 30-sep-2026 · MINISTERIO DEMO" in ayudas
    assert "4 convocatoria(s) con detalle de 4 encontradas: 2 abiertas" in ayudas
    assert not any(str(tmp_path) in str(x) for v in s.values() for x in (v if isinstance(v, tuple) else (v,)))


def test_markdown_a_html_escapa_y_marca():
    h = _capturas().markdown_a_html("# Título\n\n- **AEAT**: `gestoria recargo <importe>` _(art. 27 LGT)_\n---")
    assert "<h1>Título</h1>" in h and "<strong>AEAT</strong>" in h and "<em>(art. 27 LGT)</em>" in h
    assert "<code>gestoria recargo &lt;importe&gt;</code>" in h and h.endswith("<hr>")
