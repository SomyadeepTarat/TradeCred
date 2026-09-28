import json
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.models.domain import Receivable, User
from app.models.domain import ReceivableStatus as S
from app.models.simulator import SimulatorEvent
from app.schemas.demo import SimulatorAsset, SimulatorInput, SimulatorResult
from app.schemas.settlement import PaymentEventInput
from app.services.settlement_service import SettlementService


class SimulatorService:
    def __init__(
        self, session: AsyncSession, settings: Settings, user: User, request_id: str
    ) -> None:
        self.session, self.settings, self.user, self.request_id = (
            session,
            settings,
            user,
            request_id,
        )

    def enabled(self) -> None:
        if not self.settings.simulator_enabled:
            raise APIError(
                404, "SIMULATOR_DISABLED", "The sandbox settlement simulator is disabled."
            )

    async def assets(self) -> list[SimulatorAsset]:
        self.enabled()
        rows = await self.session.scalars(
            select(Receivable)
            .where(
                Receivable.asset_id.is_not(None),
                Receivable.status.in_(
                    [S.FINANCED, S.PAYMENT_CONFIRMED, S.REALIZED, S.EBRC_ELIGIBLE, S.CLOSED]
                ),
                Receivable.ledger_backend == self.settings.ledger_backend,
                or_(
                    Receivable.ledger_backend == "mock",
                    Receivable.ledger_network == self.settings.drunix_network_id,
                ),
            )
            .order_by(Receivable.created_at.desc())
            .limit(100)
        )
        return [
            SimulatorAsset(asset_id=r.asset_id or "", currency=r.currency, status=r.status)
            for r in rows
        ]

    async def send(self, payload: SimulatorInput) -> SimulatorResult:
        self.enabled()
        token = self.settings.simulator_token
        trusted = self.settings.bank_trusted_keys.get(self.settings.simulator_key_id)
        if not token or not trusted or trusted.organization_id != self.user.organization_id:
            raise APIError(
                503, "SIMULATOR_UNAVAILABLE", "Simulator signing configuration is unavailable."
            )
        event = PaymentEventInput(
            eventId="PAY-" + uuid4().hex,
            assetId=payload.asset_id,
            bankId=trusted.bank_id,
            bankReference=payload.reference,
            amountMinor=payload.amount_minor,
            currency=payload.currency,
            timestamp=datetime.now(UTC),
            nonce=secrets.token_hex(24),
        )
        body = event.model_dump_json()
        try:
            async with httpx.AsyncClient(
                timeout=10, trust_env=False, follow_redirects=False
            ) as client:
                response = await client.post(
                    self.settings.simulator_url + "/sign",
                    content=body,
                    headers={
                        "Authorization": "Bearer " + token.get_secret_value(),
                        "Content-Type": "application/json",
                    },
                )
            response.raise_for_status()
            signature = response.json()["signature"]
            if not isinstance(signature, str) or len(signature) != 88:
                raise ValueError("Invalid signer response")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise APIError(
                503, "SIMULATOR_UNAVAILABLE", "Signing service unavailable; no event submitted."
            ) from exc
        if payload.mode == "invalid":
            signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        row = SimulatorEvent(
            actor_user_id=self.user.id,
            body=body,
            signature=signature,
            key_id=self.settings.simulator_key_id,
        )
        self.session.add(row)
        await self.session.flush()
        row_id = row.id
        await self.session.commit()
        return await self.replay(row_id)

    async def replay(self, row_id: UUID) -> SimulatorResult:
        self.enabled()
        row = await self.session.scalar(
            select(SimulatorEvent).where(
                SimulatorEvent.id == row_id, SimulatorEvent.actor_user_id == self.user.id
            )
        )
        if row is None:
            raise APIError(404, "SIMULATOR_EVENT_NOT_FOUND", "Simulator event not found.")
        body, signature, key_id = row.body, row.signature, row.key_id
        event = json.loads(body)
        base = dict(id=row_id, event_id=event["eventId"], asset_id=event["assetId"])
        try:
            result = await SettlementService(self.session, self.settings, self.request_id).process(
                body.encode(), signature, key_id
            )
            return SimulatorResult(
                **base,
                accepted=True,
                code="PAYMENT_CONFIRMED",
                transaction_id=result.transaction_id,
                backend=result.backend,
            )
        except APIError as exc:
            return SimulatorResult(
                **base, accepted=False, uncertain=exc.status_code >= 500, code=exc.code
            )
