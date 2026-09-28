"""Prevent the Go contract's lifecycle and currency profile drifting from the API."""

import json
from pathlib import Path

from iso4217 import Currency

from app.services.state_machine import TRANSITIONS

CHAINCODE = Path(__file__).resolve().parents[3] / "blockchain" / "chaincode" / "tradecred"


def test_chaincode_state_matrix_matches_application():
    expected = json.loads((CHAINCODE / "state_transitions.json").read_text())
    assert {status: sorted(targets) for status, targets in TRANSITIONS.items()} == expected


def test_chaincode_currency_units_match_application():
    expected = json.loads((CHAINCODE / "currency_exponents.json").read_text())
    assert {c.code: c.exponent for c in Currency if isinstance(c.exponent, int)} == expected
