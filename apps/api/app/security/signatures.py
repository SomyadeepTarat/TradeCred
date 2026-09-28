"""Ed25519 signs the exact HTTP body with protocol domain separation."""

import base64
import binascii
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.errors import APIError

DOMAIN = b"TradeCred-settlement-v1\n"


def verify_signature(body: bytes, signature: str, public_key_path: Path) -> None:
    try:
        key = serialization.load_pem_public_key(public_key_path.read_bytes())
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("Ed25519 key required")
    except (OSError, ValueError, TypeError) as exc:
        raise APIError(503, "SETTLEMENT_UNAVAILABLE", "Trusted bank key is unavailable.") from exc
    try:
        raw = base64.b64decode(signature, validate=True)
        key.verify(raw, DOMAIN + body)
    except (InvalidSignature, ValueError, binascii.Error) as exc:
        raise APIError(401, "INVALID_PAYMENT_SIGNATURE", "Payment signature rejected.") from exc
