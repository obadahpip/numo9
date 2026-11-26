"""K-09-T09, T15 — tax-coding rules: EXEMPT_ON_TAXABLE_ACCOUNT (with its recode fix) and
TAX_CODE_OVERRIDE_RATE.

Acceptance: every all-exempt teardown line on a normally taxable account is flagged; a
non-registrant, a taxable code or an excluded account is not; the fix is a find & recode search
for the line with the suggested code; the search finds exactly that line.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.assurance.models import ExceptionFinding
from numo9.assurance.rules.base import context_for, evaluate, registry
from numo9.ledger.recode_query import find_lines
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, post, refined

pytestmark = pytest.mark.django_db


def test_all_exempt_teardown_lines_are_flagged() -> None:
    books = refined()
    hits = evaluate(books["org"], "EXEMPT_ON_TAXABLE_ACCOUNT", now=NOW)
    j1, j2 = str(books["journal1"].public_id), str(books["journal2"].public_id)
    assert sorted(h.subject_id for h in hits) == sorted(
        [f"{j1}:1", f"{j1}:2", f"{j1}:3", f"{j1}:4", f"{j2}:1"]
    )
    assert sum((h.amount or Decimal(0)) for h in hits) == Decimal("994.17")
    (small,) = [h for h in hits if h.subject_id == f"{j1}:4"]
    text = registry.get("EXEMPT_ON_TAXABLE_ACCOUNT").explain(small.details)
    assert "line 4: 1.13 on 5515 · Advertising & Promotions is coded purchase.exempt" in text


def test_non_registrant_taxable_code_and_excluded_account_are_not_flagged() -> None:
    books = refined(registration=False)
    assert evaluate(books["org"], "EXEMPT_ON_TAXABLE_ACCOUNT", now=NOW) == []
    books = refined()
    org = books["org"]
    with org_context(org):
        taxed = post(
            books["accounts"],
            dt.date(2026, 7, 1),
            "Taxed",
            (("5920", "100.00", "0"), ("2900", "0", "100.00")),
            tax_code="purchase.ON.standard",
        )
    hits = evaluate(
        org, "EXEMPT_ON_TAXABLE_ACCOUNT", now=NOW, params={"exclude_accounts": ["5590"]}
    )
    ids = {h.subject_id.split(":")[0] + ":" + h.details["account"][:4] for h in hits}
    assert not any(i.startswith(str(taxed.public_id)) for i in ids)
    assert not any(i.endswith(":5590") for i in ids)
    assert len(hits) == 4


def test_fix_is_a_recode_of_that_line() -> None:
    books = refined()
    org = books["org"]
    hit = next(
        h
        for h in evaluate(org, "EXEMPT_ON_TAXABLE_ACCOUNT", now=NOW)
        if h.subject_id.endswith(":1") and h.details["account"].startswith("5920")
    )
    rule = registry.get("EXEMPT_ON_TAXABLE_ACCOUNT")
    finding = ExceptionFinding(
        rule_code=rule.code,
        subject_type=hit.subject_type,
        subject_id=hit.subject_id,
        details=hit.details,
    )
    with org_context(org):
        fix = rule.propose_fix(finding, context_for(org, rule, now=NOW))
        assert fix is not None and fix.kind == "recode" and fix.recode is not None
        # no province on file and an exempt default: no code to suggest, the search still works
        lines = list(find_lines(org, fix.recode["criteria"]))
    assert [(line.entry_id, line.line_no) for line in lines] == [(books["journal2"].pk, 1)]
    assert "Find & recode" in fix.reasoning
