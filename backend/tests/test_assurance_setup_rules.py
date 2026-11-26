"""K-09-T14 — set-up rules: UNMAPPED_GIFI, MISSING_BN, MISSING_LOCK_DATE, UNBALANCED_CONVERSION.

Acceptance (teardown): 0 GIFI mapped, a GST/HST registration without BN, no lock date and an
empty conversion are all flagged; mapping, a BN, a lock date and balanced opening balances with
equity clear them; a probe registered for C-05-T14 replaces the computed conversion state.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.assurance.rules import setup
from numo9.assurance.rules.base import evaluate, registry
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, refined

pytestmark = pytest.mark.django_db


def test_teardown_has_no_gifi_no_bn_no_lock_date_and_an_empty_conversion() -> None:
    books = refined()
    org = books["org"]
    (gifi,) = evaluate(org, "UNMAPPED_GIFI", now=NOW)
    assert gifi.subject_type == "tenancy.Organisation"
    assert gifi.details["unmapped"] == gifi.details["total"] == 7
    (bn,) = evaluate(org, "MISSING_BN", now=NOW)
    assert "GST/HST program account (RT)" in registry.get("MISSING_BN").explain(bn.details)
    (lock,) = evaluate(org, "MISSING_LOCK_DATE", now=NOW)
    assert lock.details["period_end"] == "2026-09-30"
    assert "the general ledger lock date is not set" in registry.get("MISSING_LOCK_DATE").explain(
        lock.details
    )
    (conversion,) = evaluate(org, "UNBALANCED_CONVERSION", now=NOW)
    assert conversion.details["problems"] == ["empty", "no_equity"]
    text = registry.get("UNBALANCED_CONVERSION").explain(conversion.details)
    assert "no opening balances were entered" in text


def test_fixes_clear_the_setup_findings() -> None:
    from numo9.conversion.services import set_line
    from numo9.ledger.models import Account, GifiCode
    from numo9.orgsettings.models import LockDate, TaxRegistration

    books = refined()
    org = books["org"]
    with org_context(org):
        code = GifiCode.objects.order_by("code").first()
        Account.objects.update(gifi=code)  # mapping itself is C-01's; any code will do here
        TaxRegistration(organisation=org, type="bn", number="123456782").save()
        LockDate(organisation=org, module="gl", level="everyone", date=dt.date(2026, 9, 30)).save()
        set_line(books["conversion"], books["accounts"]["1000"], debit="100.00")
        set_line(books["conversion"], books["accounts"]["3000"], credit="100.00")
    for code_ in ("UNMAPPED_GIFI", "MISSING_BN", "MISSING_LOCK_DATE", "UNBALANCED_CONVERSION"):
        assert evaluate(org, code_, now=NOW) == [], code_


def test_unbalanced_conversion_and_lock_date_too_early() -> None:
    from numo9.conversion.services import set_line
    from numo9.orgsettings.models import LockDate

    books = refined()
    org = books["org"]
    with org_context(org):
        set_line(books["conversion"], books["accounts"]["1000"], debit="100.00")
        set_line(books["conversion"], books["accounts"]["3000"], credit="90.00")
        LockDate(organisation=org, module="gl", level="everyone", date=dt.date(2026, 6, 30)).save()
    (conversion,) = evaluate(org, "UNBALANCED_CONVERSION", now=NOW)
    assert conversion.details["problems"] == ["unbalanced"]
    assert conversion.amount == Decimal("10.00")
    (lock,) = evaluate(org, "MISSING_LOCK_DATE", now=NOW)
    assert lock.details["lock"] == "2026-06-30"
    assert evaluate(org, "MISSING_LOCK_DATE", now=NOW, params={"days": 200}) == []


def test_no_registration_no_bn_finding_and_no_conversion_no_finding() -> None:
    books = refined(registration=False, conversion=False)
    assert evaluate(books["org"], "MISSING_BN", now=NOW) == []
    assert evaluate(books["org"], "UNBALANCED_CONVERSION", now=NOW) == []


def test_a_registered_conversion_probe_wins() -> None:
    books = refined()
    state = setup.ConversionState(
        "probe", dt.date(2025, 1, 1), 2, Decimal("5"), Decimal("5"), has_equity=True
    )
    setup.CONVERSION_PROBES.append(lambda org: state)
    try:
        assert evaluate(books["org"], "UNBALANCED_CONVERSION", now=NOW) == []
    finally:
        setup.CONVERSION_PROBES.clear()
