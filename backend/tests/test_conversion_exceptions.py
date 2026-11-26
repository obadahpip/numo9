"""C-05-T14 — exceptions hook for K-09: the "opening equity missing" signal is emitted when a
conversion is finalised with no equity line (after commit), not when equity is there; the
providers answer OPENING_EQUITY_MISSING, UNBALANCED_CONVERSION and CONVERSION_SUSPENSE_USED with
deduplicable fingerprints; a receiver's error never undoes the finalise."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.conversion import exceptions, signals
from numo9.conversion.finalise import finalise
from numo9.conversion.fixtures import build
from numo9.conversion.models import ConversionSession
from numo9.conversion.services import set_line
from numo9.ledger.models import Account
from numo9.tenancy.context import org_context
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def received() -> Any:
    got: list[dict[str, Any]] = []

    def receiver(sender: Any, **kwargs: Any) -> None:
        got.append({"sender": sender, **kwargs})

    signals.opening_equity_missing.connect(receiver, weak=False)
    yield got
    signals.opening_equity_missing.disconnect(receiver)


def test_signal_emitted_when_no_equity_lines(
    received: list[dict[str, Any]], django_capture_on_commit_callbacks: Any
) -> None:
    org = sales_books("REFINED Interiors Inc.")["org"]
    session = build(org, "refined")
    with django_capture_on_commit_callbacks(execute=True):
        finalise(session, None)
    (event,) = received
    assert event["sender"] is ConversionSession and event["organisation"] == org
    finding = event["finding"]
    assert finding.code == "OPENING_EQUITY_MISSING" and finding.severity == "warning"
    assert finding.subject_id == str(session.public_id)
    assert finding.fingerprint == f"OPENING_EQUITY_MISSING:{session.public_id}"
    assert finding.amount == Decimal("2500.00")
    assert finding.details["status"] == "finalised" and finding.details["opening_entry"]
    assert exceptions.opening_equity_missing(org)[0].fingerprint == finding.fingerprint


def test_no_signal_with_equity(
    received: list[dict[str, Any]], django_capture_on_commit_callbacks: Any
) -> None:
    org = sales_books("Balanced Ltd")["org"]
    with django_capture_on_commit_callbacks(execute=True):
        finalise(build(org, "balanced"), None)
    assert received == []
    assert exceptions.opening_equity_missing(org) == []


def test_receiver_error_never_undoes_the_finalise(django_capture_on_commit_callbacks: Any) -> None:
    def broken(sender: Any, **kwargs: Any) -> None:
        raise RuntimeError("K-09 is down")

    signals.opening_equity_missing.connect(broken, weak=False)
    try:
        org = sales_books("REFINED Interiors Inc.")["org"]
        with django_capture_on_commit_callbacks(execute=True):
            session = finalise(build(org, "refined"), None)
        assert session.is_finalised
    finally:
        signals.opening_equity_missing.disconnect(broken)


def test_providers() -> None:
    org = sales_books("Unbalanced Ltd")["org"]
    assert {code: provider(org) for code, provider in exceptions.PROVIDERS.items()} == {
        "OPENING_EQUITY_MISSING": [],
        "UNBALANCED_CONVERSION": [],
        "CONVERSION_SUSPENSE_USED": [],
    }  # no conversion yet
    session = build(org, "unbalanced")
    (unbalanced,) = exceptions.unbalanced_conversion(org)
    assert unbalanced.severity == "critical" and unbalanced.amount == Decimal("12.50")
    assert unbalanced.details["difference"] == "12.50"
    assert exceptions.opening_equity_missing(org) == []  # 3200 retained earnings is equity
    with org_context(org):
        suspense = Account.objects.get(system_role="suspense_conversion")
    set_line(session, suspense, credit="12.50")  # the explicit plug balances it…
    assert exceptions.unbalanced_conversion(org) == []
    (plug,) = exceptions.conversion_suspense_used(org)  # …and is flagged
    assert plug.amount == Decimal("12.50") and "2900" in plug.message
    assert plug.fingerprint == f"CONVERSION_SUSPENSE_USED:{session.public_id}"
