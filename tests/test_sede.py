import pytest

from gestoria import sede

# Texto real de la página del simulador tras importar un fichero sin página DID (20-oct-2026)
RECHAZO = """Volver a la página principal
Errores y avisos
Tipo
\t
Número línea
\t
Código
\t
Descripción
\t
Ir a aviso/error
\t
Visto / Leído
\t
-
\t
FRECH
\t
El fichero se rechazó.No se importó ningún registro.
\t


\t
6
\t
E060010
\t
Contenido incorrecto en 'Pagina DID'
\t


Volver a la página principal
Agencia Tributaria"""


def test_tabla_errores_del_simulador():
    filas = sede.tabla_errores(RECHAZO)
    assert [f["codigo"] for f in filas] == ["FRECH", "E060010"]
    assert filas[1]["linea"] == "6" and "Pagina DID" in filas[1]["descripcion"]
    errores, avisos = sede._clasificar(filas)
    assert len(errores) == 2 and avisos == []


AVISO = """Errores y avisos
Tipo
\t
Número línea
\t
Código
\t
Descripción
\t
1
\t
E010541
\t
La casilla 'Tipo % [169]' sólo admite valor 0,5
\t
1
\t
31190
\t
Revise si, en su caso, debe completar las casillas relativas al apartado "Información adicional".
\t
Volver a la página principal"""


def test_codigo_numerico_es_aviso():
    errores, avisos = sede._clasificar(sede.tabla_errores(AVISO))
    assert len(errores) == 1 and errores[0].startswith("E010541")
    assert len(avisos) == 1 and avisos[0].startswith("31190")


def test_00001_es_la_confirmacion_no_un_aviso():
    texto = AVISO.replace("Volver a la página principal",
                          "-\n\t\n00001\n\t\nNo existen errores.\n\t\nVolver a la página principal")
    filas = sede.tabla_errores(texto)
    errores, avisos = sede._clasificar(filas)
    assert not any(a.startswith("00001") for a in avisos)
    assert sede.sin_errores(filas) is True


def test_diferencias_entre_fichero_y_formulario():
    from decimal import Decimal as D
    fichero = {"07": D("1234.56"), "09": D("259.26"), "71": D("-45.67"), "14": D("0")}
    aeat = {"07": D("1234.56"), "09": D("259.26"), "71": D("-45.68"), "08": D("21.00")}
    # el tipo [08] es una constante del formulario: no cuenta; [14] vale 0 en los dos
    assert sede.diferencias(fichero, aeat, constantes={"08"}) == [("71", D("-45.67"), D("-45.68"))]


def test_no_pulsa_presentar():
    with pytest.raises(RuntimeError):
        sede._pulsar(None, "Firmar y enviar")
