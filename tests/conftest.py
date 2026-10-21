"""Piezas comunes de los tests."""
import pytest


@pytest.fixture
def p12_rsa(tmp_path):
    """Un certificado de prueba autofirmado (RSA, como los de la FNMT), con su clave. Inventado."""
    x509 = pytest.importorskip("cryptography.x509")
    from datetime import datetime, timedelta, timezone

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
                        x509.NameAttribute(NameOID.COMMON_NAME, "00000000T ANA DEMO PEREZ")])
    ahora = datetime.now(timezone.utc)
    c = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(k.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(ahora - timedelta(days=1))
         .not_valid_after(ahora + timedelta(days=30))
         .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=True,
                                      data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                                      encipher_only=False, decipher_only=False), critical=True)
         .sign(k, hashes.SHA256()))
    f = tmp_path / "prueba.p12"
    f.write_bytes(pkcs12.serialize_key_and_certificates(b"prueba", k, c, None,
                                                        serialization.BestAvailableEncryption(b"clave-demo")))
    return f, "clave-demo"
