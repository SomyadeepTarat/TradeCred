import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_database_engine
from app.core.errors import APIError
from app.integrations.ledger.base import LedgerActor
from app.main import create_app
from app.models.domain import Receivable, Role, User
from app.models.financing import FinancingAgreement, FinancingOffer, MockDisbursement
from app.models.ledger import LedgerTransaction, MockLedgerAsset
from app.security.passwords import hash_password
from app.services.financing_service import FinancingService
from tests.helpers import PASSWORD, login
from tests.test_ledger_api import prepared

pytestmark = pytest.mark.integration


def terms(**changes):
    return (
        dict(
            advanceAmount="9750.00",
            currency="EUR",
            discountRateBps=250,
            tenorDays=60,
            expiresAt=(datetime.now(UTC) + timedelta(days=2)).isoformat(),
        )
        | changes
    )


def setup(client, pdf_bytes):
    owner, admin, draft, path = prepared(client, pdf_bytes)
    assert client.post(path + "/register", headers=owner).status_code == 200
    assert client.post(path + "/open-financing", headers=owner).status_code == 200
    bank = login(client, "bank@tradecred.demo")
    nbfc = login(client, "nbfc@tradecred.demo")
    return owner, admin, bank, nbfc, draft, path


def offer(client, path, bank, **changes):
    response = client.post(path + "/offers", headers=bank, json=terms(**changes))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_two_lenders_private_terms_acceptance_and_mock_payout(database, storage_root, pdf_bytes):
    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
        market = client.get("/api/v1/receivables?view=available", headers=bank).json()
        assert market["total"] == 1
        assert market["items"][0]["face_value"] is None
        assert (
            market["items"][0]["buyer_id"] is None and market["items"][0]["invoice_number"] is None
        )
        assert market["items"][0]["invoice_date"] is None
        assert market["items"][0]["face_value_bucket"] == "10000-25000"
        first = offer(client, path, bank)
        second = offer(client, path, nbfc, advanceAmount="9500.00", discountRateBps=300)
        assert len(client.get(path + "/offers", headers=owner).json()["offers"]) == 2
        private = client.get(path + "/offers", headers=bank).json()
        assert [o["id"] for o in private["offers"]] == [first]
        assert client.get(path + "/offers", headers=admin).json()["offers"] == []
        response = client.post(f"/api/v1/offers/{first}/accept", headers=owner)
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted["status"] == "LOCKED" and accepted["transaction_id"].startswith("MOCK-")
        assert client.post(f"/api/v1/offers/{second}/accept", headers=owner).status_code == 409
        assert client.post(path + "/offers", headers=nbfc, json=terms()).status_code == 409
        view = client.get(path + "/offers", headers=owner).json()
        assert {o["id"]: o["status"] for o in view["offers"]} == {
            first: "ACCEPTED",
            second: "REJECTED",
        }
        agreement = view["agreement"]
        assert (
            hashlib.sha256(agreement["canonical_payload"].encode()).hexdigest()
            == accepted["agreement_hash"]
        )
        payload = json.loads(agreement["canonical_payload"])
        assert payload["advanceAmountMinor"] == 975000 and payload["currency"] == "EUR"
        assert payload["financierOrgId"] == "ORG_BANK_CITI_DEMO"
        assert client.get(path + "/offers", headers=nbfc).json()["agreement"] is None
        assert client.post(path + "/disbursement/mock", headers=nbfc).status_code == 403
        payout = client.post(path + "/disbursement/mock", headers=bank)
        assert payout.status_code == 200, payout.text
        payout = payout.json()
        assert payout["status"] == "FINANCED"
        assert payout["payment"]["transaction_id"].startswith("MOCKPAY-")
        assert payout["payment"]["status"] == "SIMULATED_SUCCEEDED"
        retry = client.post(path + "/disbursement/mock", headers=bank).json()
        assert retry["replayed"] and retry["payment"] == payout["payment"]
        accepted_retry = client.post(f"/api/v1/offers/{first}/accept", headers=owner).json()
        assert accepted_retry["replayed"] and accepted_retry["status"] == "FINANCED"
        assert accepted_retry["transaction_id"] == accepted["transaction_id"]
        registry = client.get(
            "/api/v1/registry/fingerprint/" + draft["invoice_fingerprint"], headers=nbfc
        ).json()
        assert registry["financed"] and not registry["eligible"]
        assert registry["reason"] == "RECEIVABLE_ALREADY_FINANCED"
        assert client.get("/api/v1/receivables?view=assigned", headers=bank).json()["total"] == 1
        assert client.get("/api/v1/receivables?view=assigned", headers=nbfc).json()["total"] == 0
        assert client.get(path + "/document", headers=bank).status_code == 403
        history = client.get(path + "/history", headers=bank).json()
        assert history["events"] == []
        assert [t["to_status"] for t in history["ledger"]] == [
            "REGISTERED",
            "FINANCE_AVAILABLE",
            "LOCKED",
            "FINANCED",
        ]
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(MockDisbursement)) == 1
        assert session.scalar(select(func.count()).select_from(FinancingAgreement)) == 1
        row = session.get(Receivable, UUID(draft["id"]))
        asset = session.get(MockLedgerAsset, row.asset_id)
        assert row.status == asset.status == "FINANCED"
        assert asset.agreement_hash == row.financing_agreement_hash == accepted["agreement_hash"]


@pytest.mark.parametrize(
    "changes",
    [
        {"advanceAmount": "0"},
        {"advanceAmount": "10800.01"},
        {"advanceAmount": "1.001"},
        {"advanceAmount": 100},
        {"currency": "INR"},
        {"discountRateBps": -1},
        {"discountRateBps": 2.5},
        {"tenorDays": 0},
        {"expiresAt": "2020-01-01T00:00:00Z"},
        {"expiresAt": "2099-01-01T00:00:00"},
        {"financierOrgId": "FORGED"},
    ],
)
def test_invalid_offer_terms(database, storage_root, pdf_bytes, changes):
    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
        response = client.post(path + "/offers", headers=bank, json=terms(**changes))
        assert response.status_code == 422, response.text
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(FinancingOffer)) == 0


def test_expiry_rejection_and_rbac(database, storage_root, pdf_bytes):
    with Session(database) as session, session.begin():
        session.add(
            User(
                email="beta@tradecred.demo",
                display_name="Other exporter",
                role=Role.EXPORTER,
                organization_id="ORG_EXPORTER_BETA",
                password_hash=hash_password(PASSWORD),
            )
        )
    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
        beta = login(client, "beta@tradecred.demo")
        settlement = login(client, "settlement@tradecred.demo")
        first = offer(client, path, bank)
        for headers in (owner, admin, settlement):
            assert client.post(path + "/offers", headers=headers, json=terms()).status_code == 403
            assert client.post(path + "/disbursement/mock", headers=headers).status_code == 403
        for headers in (bank, admin, settlement):
            assert client.post(f"/api/v1/offers/{first}/accept", headers=headers).status_code == 403
            assert client.post(f"/api/v1/offers/{first}/reject", headers=headers).status_code == 403
        assert client.post(f"/api/v1/offers/{first}/accept", headers=beta).status_code == 404
        assert client.get(path + "/offers", headers=beta).status_code == 404
        assert client.get(path + "/offers", headers=settlement).status_code == 403
        assert client.post(path + "/offers", json=terms()).status_code == 401
        assert (
            client.post(f"/api/v1/offers/{first}/reject", headers=owner).json()["status"]
            == "REJECTED"
        )
        assert client.post(f"/api/v1/offers/{first}/accept", headers=owner).status_code == 409
        expired = offer(client, path, bank)
        with Session(database) as session, session.begin():
            session.get(FinancingOffer, UUID(expired)).expires_at = datetime.now(UTC) - timedelta(
                seconds=1
            )
        view = client.get(path + "/offers", headers=owner).json()
        assert next(o["status"] for o in view["offers"] if o["id"] == expired) == "EXPIRED"
        assert (
            client.post(f"/api/v1/offers/{expired}/accept", headers=owner).json()["error"]["code"]
            == "OFFER_EXPIRED"
        )
    with Session(database) as session:
        assert session.get(FinancingOffer, UUID(expired)).status == "EXPIRED"
        assert session.scalar(select(func.count()).select_from(FinancingAgreement)) == 0


@pytest.mark.parametrize("stage", ["lock", "payment", "finance", "drunix", "agreement"])
def test_failures_never_report_financing_success(
    database, storage_root, pdf_bytes, monkeypatch, stage
):
    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
        first = offer(client, path, bank)
        if stage != "lock":
            assert client.post(f"/api/v1/offers/{first}/accept", headers=owner).status_code == 200
        if stage == "agreement":
            with Session(database) as session, session.begin():
                agreement = session.scalar(select(FinancingAgreement))
                agreement.payload = agreement.payload | {"advanceAmountMinor": 1}
        if stage == "drunix":
            monkeypatch.setenv("LEDGER_BACKEND", "drunix")
        endpoint = (
            f"/api/v1/offers/{first}/accept" if stage == "lock" else path + "/disbursement/mock"
        )
    with TestClient(create_app()) as client:
        if stage in {"lock", "finance", "payment"}:
            target = (
                "app.integrations.payments.mock_npci.MockNPCIPaymentAdapter.disburse_financing"
                if stage == "payment"
                else "app.integrations.ledger.mock.MockLedgerClient._record"
            )
            with patch(target, side_effect=APIError(503, "INJECTED_FAILURE", "Unavailable")):
                response = client.post(endpoint, headers=owner if stage == "lock" else bank)
        else:
            response = client.post(endpoint, headers=bank)
        assert response.status_code == (409 if stage == "agreement" else 503), response.text
    with Session(database) as session:
        row = session.get(Receivable, UUID(draft["id"]))
        assert row.status == ("FINANCE_AVAILABLE" if stage == "lock" else "LOCKED")
        assert session.get(MockLedgerAsset, row.asset_id).status == row.status
        assert session.scalar(select(func.count()).select_from(MockDisbursement)) == 0
        assert session.scalar(select(func.count()).select_from(LedgerTransaction)) == (
            2 if stage == "lock" else 3
        )
        if stage == "lock":
            assert session.get(FinancingOffer, UUID(first)).status == "OFFERED"
            assert session.scalar(select(func.count()).select_from(FinancingAgreement)) == 0


@pytest.mark.parametrize("same_offer", [False, True])
def test_concurrent_acceptance_and_payout(database, storage_root, pdf_bytes, same_offer):
    with TestClient(create_app()) as client:
        owner, admin, bank, nbfc, draft, path = setup(client, pdf_bytes)
        first = offer(client, path, bank)
        second = first if same_offer else offer(client, path, nbfc)
    with Session(database) as session:
        actors = {
            u.email: LedgerActor(user_id=u.id, organization_id=u.organization_id, role=u.role)
            for u in session.scalars(select(User))
        }

    async def race():
        engine = create_database_engine(str(Settings().database_url))
        sessions = async_sessionmaker(engine, expire_on_commit=False)

        async def accept(offer_id):
            async with sessions() as session:
                try:
                    return await FinancingService(
                        session, Settings(), actors["exporter@tradecred.demo"], "concurrent-test"
                    ).accept(UUID(offer_id))
                except APIError as error:
                    assert error.status_code == 409
                    return None

        async def disburse(actor):
            async with sessions() as session:
                return await FinancingService(
                    session, Settings(), actor, "concurrent-test"
                ).disburse(UUID(draft["id"]))

        try:
            results = await asyncio.gather(accept(first), accept(second))
            successful = [r for r in results if r is not None]
            assert len(successful) == (2 if same_offer else 1)
            if same_offer:
                assert sum(r.replayed for r in successful) == 1
            winner = successful[0].offer_id
            actor = actors["bank@tradecred.demo" if str(winner) == first else "nbfc@tradecred.demo"]
            payments = await asyncio.gather(disburse(actor), disburse(actor))
            assert sum(p.replayed for p in payments) == 1
            assert payments[0].payment.transaction_id == payments[1].payment.transaction_id
        finally:
            await engine.dispose()

    asyncio.run(race())
    with Session(database) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(FinancingOffer)
                .where(FinancingOffer.status == "ACCEPTED")
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(FinancingAgreement)) == 1
        assert session.scalar(select(func.count()).select_from(MockDisbursement)) == 1
