import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DOMAIN = b"TradeCred-settlement-v1\n"


def sign(body: bytes, path: Path) -> str:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("An Ed25519 private key is required.")
    return base64.b64encode(key.sign(DOMAIN + body)).decode("ascii")
