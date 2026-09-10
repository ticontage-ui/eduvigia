from __future__ import annotations

import ipaddress
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _hosts() -> list[str]:
    values = os.getenv("EDUVIGIA_TLS_HOSTS", "localhost,127.0.0.1").split(",")
    result: list[str] = []
    for item in values:
        value = item.strip()
        if value and value not in result:
            result.append(value)
    for required in ("localhost", "127.0.0.1"):
        if required not in result:
            result.append(required)
    return result


def _certificate_is_usable(cert_path: Path, hosts: list[str]) -> bool:
    if not cert_path.exists():
        return False
    try:
        certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
        now = datetime.now(timezone.utc)
        if certificate.not_valid_after_utc <= now + timedelta(days=30):
            return False
        extension = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        names = set(extension.value.get_values_for_type(x509.DNSName))
        addresses = {str(item) for item in extension.value.get_values_for_type(x509.IPAddress)}
        for host in hosts:
            try:
                if str(ipaddress.ip_address(host)) not in addresses:
                    return False
            except ValueError:
                if host not in names:
                    return False
        return True
    except Exception:
        return False


def generate() -> dict:
    cert_dir = Path(os.getenv("EDUVIGIA_TLS_CERT_DIR", "/certs"))
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "eduvigia.crt"
    key_path = cert_dir / "eduvigia.key"
    hosts = _hosts()

    if key_path.exists() and _certificate_is_usable(cert_path, hosts):
        return {
            "ok": True,
            "generated": False,
            "certificate": str(cert_path),
            "key": str(key_path),
            "hosts": hosts,
        }

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EduVigIA"),
            x509.NameAttribute(NameOID.COMMON_NAME, hosts[0]),
        ]
    )
    san_values: list[x509.GeneralName] = []
    for host in hosts:
        try:
            san_values.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            san_values.append(x509.DNSName(host))

    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san_values), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return {
        "ok": True,
        "generated": True,
        "certificate": str(cert_path),
        "key": str(key_path),
        "hosts": hosts,
        "valid_until": certificate.not_valid_after_utc.isoformat(),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(generate(), ensure_ascii=False))
