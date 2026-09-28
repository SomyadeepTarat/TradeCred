"""Explicit bank simulation CLI: sends real signed HTTP events, never moves funds."""

import argparse
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from signing import sign


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/settlement/events")
    parser.add_argument("--private-key", type=Path, default=Path("data/bank-keys/bank-private.pem"))
    parser.add_argument("--key-id", default="demo-bank-1")
    parser.add_argument("--bank-id", default="BANK_SETTLEMENT_01")
    parser.add_argument("--asset-id")
    parser.add_argument("--amount-minor", type=int)
    parser.add_argument("--currency")
    parser.add_argument("--reference")
    parser.add_argument(
        "--save",
        type=Path,
        help="Save exact event bytes for replay (private local file).",
    )
    parser.add_argument("--replay", type=Path, help="Re-sign and submit a previously saved event.")
    parser.add_argument("--invalid-signature", action="store_true")
    args = parser.parse_args()
    if args.replay:
        body = args.replay.read_bytes()
    else:
        if not all((args.asset_id, args.amount_minor, args.currency, args.reference)):
            parser.error("asset-id, amount-minor, currency and reference are required")
        body = json.dumps(
            dict(
                eventId="PAY-" + uuid4().hex,
                assetId=args.asset_id,
                bankId=args.bank_id,
                bankReference=args.reference,
                amountMinor=args.amount_minor,
                currency=args.currency,
                timestamp=datetime.now(UTC).isoformat(),
                nonce=uuid4().hex,
            ),
            separators=(",", ":"),
        ).encode()
    if args.save:
        with args.save.open("xb") as output:
            args.save.chmod(0o600)
            output.write(body)
    signature = sign(body, args.private_key)
    if args.invalid_signature:
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    request = urllib.request.Request(
        args.url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-TradeCred-Key-Id": args.key_id,
            "X-TradeCred-Signature": signature,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            print("BANK SIMULATION — no funds moved")
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as error:
        print(error.code, error.read().decode())
        raise SystemExit(1) from error
    except urllib.error.URLError as error:
        raise SystemExit("Settlement endpoint unavailable; no success recorded.") from error


if __name__ == "__main__":
    main()
