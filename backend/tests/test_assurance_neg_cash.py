"""K-09-T06 — NEG_CASH: a bank or cash account whose running balance went below zero, with a
fix proposal (transfer from a funded bank, or a Shareholder Loan credit).

Acceptance (teardown fixture): finding −994.17 on Petty Cash with the draft Dr 1000 994.17 /
Cr 2900 994.17 dated 3 Jun 2026. Also: a funded account is not flagged; a balance that dipped
in the past and recovered is still flagged at its lowest point; with a funded bank the fix is a
transfer (the loan is the alternative); ``fix_source`` forces the loan; incremental runs check
the scope's accounts only.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.assurance.models import ExceptionFinding
from numo9.assurance.rules.base import Scope, context_for, evaluate, registry
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, post, refined
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def _fix(books: dict[str, Any], hit_subject: str, **params: object) -> dict[str, Any]:
    rule = registry.get("NEG_CASH")
    org = books["org"]
    ctx = context_for(org, rule, now=NOW, params=params or None)
    finding = ExceptionFinding(rule_code="NEG_CASH", subject_type="ledger.Account")
    finding.subject_id = hit_subject
    with org_context(org):
        fix = rule.propose_fix(finding, ctx)
    assert fix is not None
    return fix.as_dict()


def test_teardown_petty_cash_minus_994_17_with_shareholder_loan_fix() -> None:
    books = refined()
    org = books["org"]
    (hit,) = evaluate(org, "NEG_CASH", now=NOW)
    petty = books["accounts"]["1000"]
    assert (hit.subject_type, hit.subject_id) == ("ledger.Account", str(petty.public_id))
    assert hit.amount == Decimal("-994.17")
    assert hit.details["lowest_on"] == "2026-06-15"
    assert hit.details["first_negative_on"] == "2026-06-03"
    assert hit.details["today_balance"] == "-994.17"
    text = registry.get("NEG_CASH").explain(hit.details)
    assert text.startswith("Petty Cash went below zero: −994.17 on 15 Jun 2026 (today −994.17).")
    fix = _fix(books, hit.subject_id)
    assert fix["kind"] == "journal" and fix["date"] == "2026-06-03"
    assert [(x["code"], x["debit"], x["credit"]) for x in fix["lines"]] == [
        ("1000", "994.17", "0.00"),
        ("2900", "0.00", "994.17"),
    ]
    assert "Shareholder Loan" in fix["reasoning"]
    assert fix["alternatives"] == []


def test_funded_account_is_not_flagged() -> None:
    books = refined()
    org = books["org"]
    with org_context(org):
        post(
            books["accounts"],
            dt.date(2026, 6, 1),
            "Float",
            (("1000", "1000.00", "0"), ("4000", "0", "1000.00")),
        )
    assert evaluate(org, "NEG_CASH", now=NOW) == []


def test_a_past_dip_that_recovered_is_flagged_at_its_lowest() -> None:
    books = refined()
    org = books["org"]
    with org_context(org):
        post(
            books["accounts"],
            dt.date(2026, 7, 1),
            "Late float",
            (("1000", "2000.00", "0"), ("4000", "0", "2000.00")),
        )
    (hit,) = evaluate(org, "NEG_CASH", now=NOW)
    assert hit.amount == Decimal("-994.17")
    assert hit.details["today_balance"] == "1005.83"


def test_funded_bank_gives_a_transfer_with_the_loan_as_alternative() -> None:
    books = refined()
    org = books["org"]
    with org_context(org):
        books["accounts"]["1010"] = account(org, "1010", "Chequing", subtype="bank")
        post(
            books["accounts"],
            dt.date(2026, 5, 1),
            "Deposit",
            (("1010", "5000.00", "0"), ("4000", "0", "5000.00")),
        )
    (hit,) = evaluate(org, "NEG_CASH", now=NOW)
    fix = _fix(books, hit.subject_id)
    assert [(x["code"], x["debit"], x["credit"]) for x in fix["lines"]] == [
        ("1000", "994.17", "0.00"),
        ("1010", "0.00", "994.17"),
    ]
    assert "Chequing has 5,000.00 today" in fix["reasoning"]
    (alternative,) = fix["alternatives"]
    assert alternative["lines"][1]["code"] == "2900"
    forced = _fix(books, hit.subject_id, fix_source="shareholder_loan")
    assert forced["lines"][1]["code"] == "2900"


def test_incremental_scope_checks_its_accounts_only() -> None:
    books = refined()
    org = books["org"]
    petty, travel = books["accounts"]["1000"], books["accounts"]["5920"]
    scoped = evaluate(org, "NEG_CASH", Scope(accounts=frozenset({str(travel.public_id)})), now=NOW)
    assert scoped == []
    scoped = evaluate(org, "NEG_CASH", Scope(accounts=frozenset({str(petty.public_id)})), now=NOW)
    assert len(scoped) == 1
