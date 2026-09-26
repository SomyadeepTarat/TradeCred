import pytest

from app.core.errors import APIError
from app.integrations.ledger.mock import value_bucket
from app.models.domain import ReceivableStatus as S
from app.services.state_machine import require_transition

EDGES = {
    ("DRAFT", "SUBMITTED"),
    ("SUBMITTED", "VERIFIED"),
    ("VERIFIED", "REGISTERED"),
    ("REGISTERED", "FINANCE_AVAILABLE"),
    ("FINANCE_AVAILABLE", "LOCKED"),
    ("LOCKED", "FINANCED"),
    ("LOCKED", "RELEASED"),
    ("FINANCED", "PAYMENT_CONFIRMED"),
    ("FINANCED", "OVERDUE"),
    ("FINANCED", "DISPUTED"),
    ("PAYMENT_CONFIRMED", "REALIZED"),
    ("REALIZED", "EBRC_ELIGIBLE"),
    ("EBRC_ELIGIBLE", "CLOSED"),
}


@pytest.mark.parametrize("current", list(S))
@pytest.mark.parametrize("target", list(S))
def test_prd_transition_matrix(current: S, target: S) -> None:
    if (current.value, target.value) in EDGES:
        require_transition(current, target)
    else:
        with pytest.raises(APIError) as error:
            require_transition(current, target)
        assert error.value.status_code == 409


@pytest.mark.parametrize(
    "amount,currency,bucket",
    [
        (999999, "EUR", "0-10000"),
        (1000000, "EUR", "10000-25000"),
        (2500000, "EUR", "25000-100000"),
        (100000, "JPY", "100000-1000000"),
        (1000000000, "KWD", "1000000+"),
    ],
)
def test_private_amount_buckets(amount: int, currency: str, bucket: str) -> None:
    assert value_bucket(amount, currency) == bucket
