"""Generate a local demo signing key and public registry; never overwrite keys."""

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    directory = ROOT / "data" / "bank-keys"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_path = directory / "bank-private.pem"
    public_dir = ROOT / "data" / "bank-public"
    public_dir.mkdir(parents=True, exist_ok=True)
    public_path = public_dir / "bank-public.pem"
    if private_path.exists() or public_path.exists():
        raise SystemExit("Keys already exist; refusing to overwrite. See bank-simulator/README.md.")
    key = Ed25519PrivateKey.generate()
    with os.fdopen(
        os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
    ) as output:
        output.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    registry = {
        "demo-bank-1": {
            "bank_id": "BANK_SETTLEMENT_01",
            "organization_id": "ORG_SETTLEMENT_BANK",
            "public_key_path": str(public_path),
        }
    }
    print("Keys generated. Add this public-only registry to .env for host API development:")
    print("BANK_TRUSTED_KEYS='" + json.dumps(registry, separators=(",", ":")) + "'")
    print("Docker uses the mounted public key automatically. No private key is mounted in the API.")


if __name__ == "__main__":
    main()
