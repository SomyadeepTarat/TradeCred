"""Internal sandbox signer. Only this service mounts the bank private key."""

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError
from signing import sign

from app.schemas.settlement import PaymentEventInput

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sign")
async def sign_event(request: Request) -> dict[str, str]:
    token = os.environ.get("SIMULATOR_TOKEN", "")
    if len(token) < 32 or not secrets.compare_digest(
        request.headers.get("Authorization", ""), "Bearer " + token
    ):
        raise HTTPException(403, "Signing is not authorized")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 8192:
            raise HTTPException(413, "Event too large")
    try:
        event = PaymentEventInput.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(422, "Invalid event") from exc
    if event.bankId != "BANK_SETTLEMENT_01":
        raise HTTPException(403, "Unknown sandbox bank")
    try:
        signature = sign(bytes(body), Path(os.environ["BANK_PRIVATE_KEY_PATH"]))
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Signing key unavailable") from exc
    return {"signature": signature}
