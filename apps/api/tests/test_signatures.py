import base64
import runpy
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.errors import APIError
from app.security.signatures import DOMAIN, verify_signature

ROOT = Path(__file__).resolve().parents[3]


def test_generated_keys_and_simulator_interoperate_without_overwriting(tmp_path):
    generator = runpy.run_path(str(ROOT / "scripts/generate_keys.py"))
    main = generator["main"]
    main.__globals__["ROOT"] = tmp_path
    main()
    private = tmp_path / "data/bank-keys/bank-private.pem"
    public = tmp_path / "data/bank-public/bank-public.pem"
    original = private.read_bytes()
    assert private.stat().st_mode & 0o777 == 0o600
    signing = runpy.run_path(str(ROOT / "services/bank-simulator/signing.py"))
    signature = signing["sign"](b'{"eventId":"test"}', private)
    verify_signature(b'{"eventId":"test"}', signature, public)
    token_before = (tmp_path / ".env").read_text()
    main()
    assert (tmp_path / ".env").read_text() == token_before
    assert private.read_bytes() == original
    with pytest.raises(APIError) as error:
        verify_signature(b'{"eventId":"tampered"}', signature, public)
    assert error.value.code == "INVALID_PAYMENT_SIGNATURE"


@pytest.mark.parametrize("case", ["wrong_key", "wrong_domain", "malformed", "missing_key"])
def test_signature_failures(tmp_path, case):
    key = Ed25519PrivateKey.generate()
    public = tmp_path / "public.pem"
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    body = b"test"
    signature = base64.b64encode(key.sign(DOMAIN + body)).decode()
    if case == "wrong_key":
        signature = base64.b64encode(Ed25519PrivateKey.generate().sign(DOMAIN + body)).decode()
    elif case == "wrong_domain":
        signature = base64.b64encode(key.sign(body)).decode()
    elif case == "malformed":
        signature = "not base64!"
    elif case == "missing_key":
        public.unlink()
    with pytest.raises(APIError) as error:
        verify_signature(body, signature, public)
    assert error.value.status_code == (503 if case == "missing_key" else 401)
