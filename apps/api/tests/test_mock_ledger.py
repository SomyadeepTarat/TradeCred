import asyncio
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.database import create_database_engine
from app.core.errors import APIError
from app.integrations.ledger.base import LedgerActor, Registration
from app.integrations.ledger.mock import MockLedgerClient
from app.models.domain import ReceivableStatus as S
from app.models.domain import Role
from app.models.ledger import MockLedgerAsset

pytestmark = pytest.mark.integration
EXPORTER = LedgerActor(user_id=uuid4(), organization_id="ORG_EXPORTER_ALPHA", role=Role.EXPORTER)
BANK = LedgerActor(user_id=uuid4(), organization_id="ORG_BANK_CITI_DEMO", role=Role.FINANCIER)
OTHER_BANK = BANK.model_copy(update={"organization_id": "ORG_BANK_NBFC_DEMO"})
SETTLEMENT = LedgerActor(
    user_id=uuid4(), organization_id="ORG_SETTLEMENT_BANK", role=Role.SETTLEMENT_OPERATOR
)
REGISTRATION = Registration(
    asset_id="TC-test",
    invoice_fingerprint="a" * 64,
    document_hash="b" * 64,
    exporter_org_id=EXPORTER.organization_id,
    currency="EUR",
    face_value_minor=1080000,
    due_date=date(2026, 11, 25),
)


@pytest.fixture
async def sessions(database):
    engine = create_database_engine(str(Settings().database_url))
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_registration_idempotency_duplicate_and_rollback(sessions):
    async with sessions.begin() as session:
        ledger = MockLedgerClient(session, EXPORTER)
        first = await ledger.register_receivable(REGISTRATION)
        retry = await ledger.register_receivable(REGISTRATION)
        assert first.transaction_id == retry.transaction_id and retry.replayed
        assert "face_value_minor" not in first.asset.model_dump()
        assert first.asset.face_value_bucket == "10000-25000"
    for change, code in [
        ({"asset_id": "TC-other"}, "DUPLICATE_RECEIVABLE"),
        ({"document_hash": "c" * 64}, "REGISTRATION_CONFLICT"),
    ]:
        with pytest.raises(APIError) as error:
            async with sessions.begin() as session:
                await MockLedgerClient(session, EXPORTER).register_receivable(
                    REGISTRATION.model_copy(update=change)
                )
        assert error.value.code == code
    async with sessions() as session:
        await MockLedgerClient(session, EXPORTER).register_receivable(
            REGISTRATION.model_copy(
                update={"asset_id": "TC-rollback", "invoice_fingerprint": "d" * 64}
            )
        )
        await session.rollback()
    async with sessions() as session:
        assert await session.get(MockLedgerAsset, "TC-rollback") is None
        ledger = MockLedgerClient(session, BANK)
        assert (await ledger.find_by_fingerprint("a" * 64)).asset_id == "TC-test"
        assert (await ledger.get_receivable("TC-test")).status == S.REGISTERED
        assert len(await ledger.get_history("TC-test")) == 1


async def test_concurrent_registration_and_lock_have_one_winner(sessions):
    async def register(asset_id):
        try:
            async with sessions.begin() as session:
                await MockLedgerClient(session, EXPORTER).register_receivable(
                    REGISTRATION.model_copy(update={"asset_id": asset_id})
                )
            return asset_id
        except APIError as error:
            assert error.code == "DUPLICATE_RECEIVABLE"
            return None

    results = await asyncio.gather(register("TC-one"), register("TC-two"))
    assert sum(r is not None for r in results) == 1
    winner = next(r for r in results if r is not None)
    async with sessions.begin() as session:
        await MockLedgerClient(session, EXPORTER).transition_receivable(winner, S.FINANCE_AVAILABLE)

    async def lock(org):
        try:
            async with sessions.begin() as session:
                await MockLedgerClient(session, EXPORTER).lock_receivable(winner, org, "c" * 64)
            return org
        except APIError as error:
            assert error.status_code == 409
            return None

    locks = await asyncio.gather(lock(BANK.organization_id), lock(OTHER_BANK.organization_id))
    assert sum(r is not None for r in locks) == 1
    async with sessions() as session:
        asset = await session.get(MockLedgerAsset, winner)
        assert asset.owner_org_id == next(r for r in locks if r is not None)
        assert asset.status == S.LOCKED
        assert len(await MockLedgerClient(session, BANK).get_history(winner)) == 3


async def test_guarded_lifecycle_ownership_payment_and_terminal_state(sessions):
    async def action(actor, method, *args):
        async with sessions.begin() as session:
            return await getattr(MockLedgerClient(session, actor), method)("TC-test", *args)

    async with sessions.begin() as session:
        await MockLedgerClient(session, EXPORTER).register_receivable(REGISTRATION)
    await action(EXPORTER, "transition_receivable", S.FINANCE_AVAILABLE)
    with pytest.raises(APIError) as error:
        await action(EXPORTER, "transition_receivable", S.LOCKED)
    assert error.value.code == "GUARDED_LEDGER_OPERATION"
    with pytest.raises(APIError) as error:
        await action(EXPORTER, "lock_receivable", BANK.organization_id, "")
    assert error.value.code == "INVALID_AGREEMENT_HASH"
    await action(EXPORTER, "lock_receivable", BANK.organization_id, "c" * 64)
    for actor in (EXPORTER, OTHER_BANK):
        with pytest.raises(APIError) as error:
            await action(actor, "transition_receivable", S.FINANCED)
        assert error.value.status_code == 403
    await action(BANK, "transition_receivable", S.FINANCED)
    with pytest.raises(APIError) as error:
        await action(SETTLEMENT, "transition_receivable", S.PAYMENT_CONFIRMED)
    assert error.value.code == "GUARDED_LEDGER_OPERATION"
    for amount, currency, code in [
        (1, "EUR", "PAYMENT_AMOUNT_MISMATCH"),
        (1080000, "USD", "PAYMENT_CURRENCY_MISMATCH"),
    ]:
        with pytest.raises(APIError) as error:
            await action(SETTLEMENT, "confirm_payment", "event-1", amount, currency, "private-ref")
        assert error.value.code == code
    with pytest.raises(APIError) as error:
        await action(BANK, "confirm_payment", "event-1", 1080000, "EUR", "private-ref")
    assert error.value.status_code == 403
    await action(SETTLEMENT, "confirm_payment", "event-1", 1080000, "EUR", "private-ref")
    with pytest.raises(APIError) as error:
        await action(SETTLEMENT, "confirm_payment", "event-1", 1080000, "EUR", "private-ref")
    assert error.value.code == "PAYMENT_EVENT_REPLAY"
    for target in (S.REALIZED, S.EBRC_ELIGIBLE, S.CLOSED):
        await action(SETTLEMENT, "transition_receivable", target)
    with pytest.raises(APIError) as error:
        await action(EXPORTER, "transition_receivable", S.FINANCE_AVAILABLE)
    assert error.value.status_code == 409
    async with sessions() as session:
        history = await MockLedgerClient(session, BANK).get_history("TC-test")
        assert [h.revision for h in history] == list(range(1, 9))
        assert "private-ref" not in str(history)
        assert history[-1].to_status == S.CLOSED
