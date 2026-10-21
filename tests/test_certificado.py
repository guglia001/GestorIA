"""El certificado se lee en local: tipo, titular, entidad, cargo y caducidad. Se fabrica uno de
prueba con los mismos atributos que pone la FNMT (todo inventado)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from gestoria import certificado

x509 = pytest.importorskip("cryptography.x509")


def _p12(tmp_path, representante: bool, dias: int = 400) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID, ObjectIdentifier

    clave = ec.generate_private_key(ec.SECP256R1())
    attrs = [x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
             x509.NameAttribute(NameOID.SERIAL_NUMBER, "IDCES-00000000T"),
             x509.NameAttribute(NameOID.GIVEN_NAME, "ANA"), x509.NameAttribute(NameOID.SURNAME, "DEMO PEREZ")]
    texto = "Certificado cualificado de firma electrónica"
    san = []
    if representante:
        attrs += [x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BICIS DEMO SL"),
                  x509.NameAttribute(ObjectIdentifier("2.5.4.97"), "VATES-B00000000")]
        texto = "Certificado cualificado de representante de p. jurídica"
        san = [x509.DirectoryName(x509.Name([x509.NameAttribute(ObjectIdentifier("1.3.6.1.4.1.5734.1.20"), "Administrador único")]))]
    attrs.append(x509.NameAttribute(NameOID.COMMON_NAME, "00000000T ANA DEMO PEREZ"))
    emisor = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AC Demo"), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CA DEMO")])
    ahora = datetime.now(timezone.utc)
    b = (x509.CertificateBuilder().subject_name(x509.Name(attrs)).issuer_name(emisor).public_key(clave.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(ahora - timedelta(days=1))
         .not_valid_after(ahora + timedelta(days=dias))
         .add_extension(x509.CertificatePolicies([x509.PolicyInformation(ObjectIdentifier("1.3.6.1.4.1.99999.1"),
                                                                         [x509.UserNotice(None, texto)])]), critical=False))
    if san:
        b = b.add_extension(x509.SubjectAlternativeName(san), critical=False)
    cert = b.sign(clave, hashes.SHA256())
    f = tmp_path / ("rep.p12" if representante else "pf.p12")
    f.write_bytes(pkcs12.serialize_key_and_certificates(b"demo", clave, cert, None,
                                                        serialization.BestAvailableEncryption(b"clave-demo")))
    return str(f)


def test_representante_de_persona_juridica(tmp_path):
    c = certificado.leer(_p12(tmp_path, True), "clave-demo")
    assert (c.tipo, c.entidad, c.nif_entidad, c.nif_titular, c.cargo) == ("representante", "BICIS DEMO SL", "B00000000", "00000000T", "Administrador único")
    assert c.nif == "B00000000" and c.titular == "ANA DEMO PEREZ"
    assert c.nivel() == "🟢" and "representante de BICIS DEMO SL" in c.describir()


def test_persona_fisica_y_caducidad(tmp_path):
    c = certificado.leer(_p12(tmp_path, False, dias=30), "clave-demo")
    assert c.tipo == "persona" and c.nif == "00000000T" and c.entidad == ""
    assert c.nivel() == "🟡" and c.nivel(date.today() + timedelta(days=20)) == "🔴"
    assert "CADUCADO" in c.describir(date.today() + timedelta(days=40))


def test_clave_mal(tmp_path):
    with pytest.raises(ValueError):
        certificado.leer(_p12(tmp_path, False), "otra")


def test_contexto_tls_no_deja_la_clave_en_disco(tmp_path, monkeypatch):
    import ssl
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    ctx = certificado.contexto_tls(_p12(tmp_path, True), "clave-demo")
    assert isinstance(ctx, ssl.SSLContext)
    assert list((tmp_path / "tmp").iterdir()) == []
