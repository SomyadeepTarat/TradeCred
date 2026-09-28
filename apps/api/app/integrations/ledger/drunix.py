"""Fabric-compatible Drunix adapter. Never falls back or manufactures a committed receipt."""

import hashlib
import json
import secrets
import ssl
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import APIError
from app.integrations.ledger.base import (
    LedgerActor,
    LedgerAsset,
    LedgerHistoryEntry,
    LedgerReceipt,
    Registration,
)
from app.models.domain import ReceivableStatus as S
from app.models.drunix import LedgerArtifact


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class DrunixLedgerClient:
    def __init__(self, session: AsyncSession, settings: Settings, actor: LedgerActor) -> None:
        self.session, self.settings, self.actor = session, settings, actor
        if not all(
            (
                settings.drunix_gateway_url,
                settings.drunix_gateway_token,
                settings.drunix_network_id,
                settings.drunix_channel,
            )
        ):
            raise APIError(503, "LEDGER_UNAVAILABLE", "Drunix gateway configuration is incomplete.")

    def operation_id(self, key: str) -> str:
        namespace = [
            self.settings.drunix_network_id,
            self.settings.drunix_channel,
            self.settings.drunix_chaincode_name,
            key,
        ]
        return hashlib.sha256(canonical(namespace).encode()).hexdigest()

    async def saved(self, key: str) -> dict[str, Any] | None:
        async with async_sessionmaker(self.session.bind, expire_on_commit=False)() as durable:
            artifact = await durable.get(LedgerArtifact, self.operation_id(key))
            return artifact.payload if artifact else None

    async def persist(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        # No FKs to caller-locked rows: this commit must survive projection rollback.
        async with async_sessionmaker(self.session.bind, expire_on_commit=False)() as durable:
            async with durable.begin():
                await durable.execute(
                    insert(LedgerArtifact)
                    .values(
                        key=self.operation_id(key),
                        payload=payload,
                    )
                    .on_conflict_do_nothing(index_elements=["key"])
                )
                row = await durable.get(LedgerArtifact, self.operation_id(key))
                assert row is not None
                return row.payload

    async def _request(
        self,
        method: str,
        args: list[str],
        *,
        submit: bool = False,
        key: str = "",
        transient: dict[str, str] | None = None,
        endorsers: list[str] | None = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "networkId": self.settings.drunix_network_id,
            "channel": self.settings.drunix_channel,
            "chaincode": self.settings.drunix_chaincode_name,
            "orgId": self.actor.organization_id,
            "role": self.actor.role.value,
            "method": method,
            "arguments": args,
            "transient": transient or {},
            "operationId": self.operation_id(key) if submit else "",
            "endorserOrgs": endorsers or [self.actor.organization_id],
        }
        if submit:
            saved = await self.persist("operation:" + key, payload)
            if saved != payload:
                raise APIError(
                    409, "OPERATION_CONFLICT", "A different durable ledger request exists."
                )
        token = self.settings.drunix_gateway_token
        assert token is not None
        try:
            verify: bool | ssl.SSLContext = True
            if self.settings.drunix_gateway_ca_path:
                verify = ssl.create_default_context(
                    cafile=str(self.settings.drunix_gateway_ca_path)
                )
            async with httpx.AsyncClient(
                timeout=self.settings.drunix_timeout_seconds,
                verify=verify,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self.settings.drunix_gateway_url.rstrip("/")
                    + ("/submit" if submit else "/evaluate"),
                    json=payload,
                    headers={"Authorization": "Bearer " + token.get_secret_value()},
                )
            if response.status_code != 200:
                code = response.json().get("error", "LEDGER_UNAVAILABLE")
                allowed = {
                    "ASSET_NOT_FOUND": 404,
                    "OPERATION_NOT_FOUND": 404,
                    "UNAUTHORIZED_ROLE": 403,
                    "DUPLICATE_RECEIVABLE": 409,
                    "OPERATION_CONFLICT": 409,
                    "REGISTRATION_CONFLICT": 409,
                    "INVALID_STATE_TRANSITION": 409,
                    "PAYMENT_EVENT_REPLAY": 409,
                    "PAYMENT_AMOUNT_MISMATCH": 409,
                    "PAYMENT_CURRENCY_MISMATCH": 409,
                    "PRIVATE_DETAILS_MISMATCH": 409,
                    "INVALID_FINANCING_TERMS": 409,
                    "OFFER_EXPIRED_OR_INVALID": 409,
                    "INVALID_AGREEMENT_TIME": 409,
                }
                if code in allowed:
                    raise APIError(allowed[code], code, "Ledger rejected the operation.")
                raise APIError(
                    503,
                    "LEDGER_UNAVAILABLE",
                    "Ledger outcome is unavailable; retry the same action.",
                )
            envelope = response.json()
            if envelope.get("backend") != "drunix" or envelope.get("committed") is not submit:
                raise ValueError("Unconfirmed or incorrectly labeled gateway response")
            return envelope["result"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
            raise APIError(
                503, "LEDGER_UNAVAILABLE", "Ledger outcome could not be confirmed."
            ) from exc

    def _asset(self, raw: dict[str, Any]) -> LedgerAsset:
        try:
            return LedgerAsset(
                asset_id=raw["assetId"],
                invoice_fingerprint=raw["invoiceFingerprint"],
                document_hash=raw["documentHash"],
                exporter_org_id=raw["exporterOrgId"],
                owner_org_id=raw["ownerOrgId"] or None,
                currency=raw["currency"],
                face_value_bucket=raw["faceValueBucket"],
                due_date=raw["dueDate"],
                agreement_hash=raw["agreementHash"] or None,
                status=raw["status"],
                updated_at=raw["updatedAt"],
                backend="drunix",
            )
        except (KeyError, TypeError, ValidationError) as exc:
            raise APIError(503, "LEDGER_UNAVAILABLE", "Invalid ledger projection.") from exc

    async def _execute(
        self,
        method: str,
        args: list[str],
        key: str,
        transient: dict[str, str] | None = None,
        endorsers: list[str] | None = None,
    ) -> LedgerReceipt:
        result = await self._request(
            method, args, submit=True, key=key, transient=transient, endorsers=endorsers
        )
        try:
            if (result["actorOrgId"], result["actorRole"]) != (
                self.actor.organization_id,
                self.actor.role.value,
            ):
                raise ValueError("Receipt identity mismatch")
            raw = result["asset"]
            txid = raw["transactionId"]
            if (
                not isinstance(txid, str)
                or len(txid) != 64
                or any(c not in "0123456789abcdef" for c in txid)
            ):
                raise ValueError("Invalid Fabric transaction ID")
            return LedgerReceipt(
                asset=self._asset(raw), transaction_id=txid, replayed=result.get("replayed", False)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(503, "LEDGER_UNAVAILABLE", "Invalid committed receipt.") from exc

    async def _invoice(self, registration: Registration | None, asset_id: str) -> str:
        if registration:
            payload = {
                "assetId": asset_id,
                "amountMinor": registration.face_value_minor,
                "currency": registration.currency,
                "salt": secrets.token_hex(32),
            }
            saved = await self.persist("invoice:" + asset_id, payload)
            if any(saved[k] != payload[k] for k in ("assetId", "amountMinor", "currency")):
                raise APIError(409, "REGISTRATION_CONFLICT", "Private invoice commitment changed.")
        else:
            stored = await self.saved("invoice:" + asset_id)
            if stored is None:
                raise APIError(
                    503, "LEDGER_UNAVAILABLE", "Private invoice commitment is unavailable."
                )
            saved = stored
        return canonical(saved)

    def _registration(self, r: Registration) -> str:
        return canonical(
            {
                "assetId": r.asset_id,
                "invoiceFingerprint": r.invoice_fingerprint,
                "documentHash": r.document_hash,
                "exporterOrgId": r.exporter_org_id,
                "currency": r.currency,
                "dueDate": r.due_date.isoformat(),
            }
        )

    async def verify_receivable(self, registration: Registration) -> LedgerReceipt:
        return await self._execute(
            "VerifyReceivable",
            [self._registration(registration)],
            "verify:" + registration.asset_id,
            {"invoice": await self._invoice(registration, registration.asset_id)},
        )

    async def register_receivable(self, registration: Registration) -> LedgerReceipt:
        receipt = await self._execute(
            "RegisterReceivable",
            [self._registration(registration)],
            "register:" + registration.asset_id,
            {"invoice": await self._invoice(registration, registration.asset_id)},
        )
        current = await self.get_receivable(registration.asset_id)
        if current is None or current.invoice_fingerprint != registration.invoice_fingerprint:
            raise APIError(503, "LEDGER_UNAVAILABLE", "Committed asset is unavailable.")
        receipt.asset = current
        return receipt

    async def get_receivable(self, asset_id: str) -> LedgerAsset | None:
        try:
            asset = self._asset(await self._request("GetReceivable", [asset_id]))
            if asset.asset_id != asset_id:
                raise APIError(503, "LEDGER_UNAVAILABLE", "Wrong asset in ledger response.")
            return asset
        except APIError as exc:
            if exc.code == "ASSET_NOT_FOUND":
                return None
            raise

    async def find_by_fingerprint(self, fingerprint: str) -> LedgerAsset | None:
        try:
            asset = self._asset(await self._request("GetReceivableByFingerprint", [fingerprint]))
            if asset.invoice_fingerprint != fingerprint:
                raise APIError(503, "LEDGER_UNAVAILABLE", "Wrong fingerprint in ledger response.")
            return asset
        except APIError as exc:
            if exc.code == "ASSET_NOT_FOUND":
                return None
            raise

    async def recovery_matches(self, key: str, asset: LedgerAsset) -> bool:
        saved = await self.saved("operation:" + key)
        if saved is None:
            return False
        try:
            result = await self._request("GetOperationReceipt", [self.operation_id(key)])
        except APIError as exc:
            if exc.code == "OPERATION_NOT_FOUND":
                return False
            raise
        try:
            if (result["actorOrgId"], result["actorRole"]) != (
                self.actor.organization_id,
                self.actor.role.value,
            ):
                raise ValueError("Wrong receipt owner")
            return self._asset(result["asset"]) == asset
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(503, "LEDGER_UNAVAILABLE", "Invalid recovery receipt.") from exc

    async def acceptance_payload(
        self, offer_id: UUID, payload: dict[str, str | int], expires_at: datetime
    ) -> dict[str, str | int]:
        entry = {"payload": payload, "expiresAt": expires_at.isoformat()}
        saved = await self.persist("acceptance:" + str(offer_id), entry)
        expected = {k: v for k, v in payload.items() if k != "acceptedAt"}
        actual = {k: v for k, v in saved["payload"].items() if k != "acceptedAt"}
        if actual != expected or saved["expiresAt"] != entry["expiresAt"]:
            raise APIError(409, "OPERATION_CONFLICT", "Accepted offer terms changed.")
        return dict(saved["payload"])

    async def lock_receivable(
        self,
        asset_id: str,
        financier_org_id: str,
        agreement_hash: str,
        *,
        payload: dict[str, str | int] | None = None,
        offer_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> LedgerReceipt:
        if payload is None or offer_id is None or expires_at is None:
            raise APIError(
                422, "INVALID_FINANCING_TERMS", "Private agreement and offer are required."
            )
        return await self._execute(
            "LockReceivable",
            [asset_id, financier_org_id, agreement_hash],
            "lock:" + str(offer_id),
            {
                "invoice": await self._invoice(None, asset_id),
                "agreement": canonical(payload),
                "offer": canonical({"offerId": str(offer_id), "expiresAt": expires_at.isoformat()}),
            },
            [self.actor.organization_id, financier_org_id],
        )

    async def transition_receivable(self, asset_id: str, target: S) -> LedgerReceipt:
        methods = {
            S.FINANCE_AVAILABLE: "OpenForFinancing",
            S.FINANCED: "RecordFinancing",
            S.RELEASED: "ReleaseLock",
            S.REALIZED: "MarkRealized",
            S.EBRC_ELIGIBLE: "MarkEbrcEligible",
            S.CLOSED: "CloseReceivable",
            S.DISPUTED: "RaiseDispute",
            S.OVERDUE: "MarkOverdue",
        }
        if target not in methods:
            raise APIError(409, "INVALID_STATE_TRANSITION", "Dedicated ledger operation required.")
        return await self._execute(
            methods[target], [asset_id], "transition:" + asset_id + ":" + target.value
        )

    async def confirm_payment(
        self, asset_id: str, event_id: str, amount_minor: int, currency: str, reference: str
    ) -> LedgerReceipt:
        payload = {
            "eventId": event_id,
            "amountMinor": amount_minor,
            "currency": currency,
            "reference": reference,
            "salt": secrets.token_hex(32),
        }
        saved = await self.persist("payment:" + event_id, payload | {"assetId": asset_id})
        if any(saved[k] != v for k, v in (payload | {"assetId": asset_id}).items() if k != "salt"):
            raise APIError(409, "OPERATION_CONFLICT", "Payment event terms changed.")
        return await self._execute(
            "ConfirmPayment",
            [asset_id],
            "payment:" + event_id,
            {
                "invoice": await self._invoice(None, asset_id),
                "payment": canonical({k: v for k, v in saved.items() if k != "assetId"}),
            },
        )

    async def get_history(self, asset_id: str) -> list[LedgerHistoryEntry]:
        raw = await self._request("GetHistory", [asset_id])
        try:
            entries = []
            previous = S.SUBMITTED
            for item in raw:
                asset = item["asset"]
                entry = LedgerHistoryEntry(
                    transaction_id=item["transactionId"],
                    asset_id=asset_id,
                    revision=asset["revision"],
                    from_status=previous,
                    to_status=asset["status"],
                    actor_org_id=asset["actorOrgId"],
                    created_at=item["timestamp"],
                    backend="drunix",
                )
                entries.append(entry)
                previous = entry.to_status
            return entries
        except (KeyError, TypeError, ValidationError) as exc:
            raise APIError(503, "LEDGER_UNAVAILABLE", "Ledger history is invalid.") from exc
