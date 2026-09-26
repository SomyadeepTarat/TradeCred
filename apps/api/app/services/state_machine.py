from app.core.errors import APIError
from app.models.domain import ReceivableStatus as Status

TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.DRAFT: frozenset({Status.SUBMITTED}),
    Status.SUBMITTED: frozenset({Status.VERIFIED}),
    Status.VERIFIED: frozenset({Status.REGISTERED}),
    Status.REGISTERED: frozenset({Status.FINANCE_AVAILABLE}),
    Status.FINANCE_AVAILABLE: frozenset({Status.LOCKED}),
    Status.LOCKED: frozenset({Status.FINANCED, Status.RELEASED}),
    Status.FINANCED: frozenset({Status.PAYMENT_CONFIRMED, Status.OVERDUE, Status.DISPUTED}),
    Status.PAYMENT_CONFIRMED: frozenset({Status.REALIZED}),
    Status.REALIZED: frozenset({Status.EBRC_ELIGIBLE}),
    Status.EBRC_ELIGIBLE: frozenset({Status.CLOSED}),
}


def require_transition(current: Status, target: Status) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise APIError(409, "INVALID_STATE_TRANSITION", f"Cannot transition {current} to {target}.")
