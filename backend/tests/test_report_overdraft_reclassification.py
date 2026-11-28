"""K-02-T04 — overdraft reclassification: an overdrawn asset bank or cash account is shown in
current liabilities with a note.

Acceptance: Petty Cash −994.17 (teardown: 417.22 on 3 Jun and 576.95 on 15 Jun from an empty
float) shows as the liability "Bank overdraft — Petty Cash" 994.17 with the note "Overdrawn bank
and cash accounts are presented as current liabilities (ASPE 1510)." — and the balance sheet
still balances. Also: with comparatives, only the columns where it is overdrawn move (the other
column keeps it in current assets); a funded account never moves; no note without an overdraft.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import post_journal
from numo9.reports.engine import registry
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db
D = Decimal
NOTE = "Overdrawn bank and cash accounts are presented as current liabilities (ASPE 1510)."


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(organisation):
        accounts = chart(organisation)
        post_journal(pay(accounts["chequing"], accounts["sales"], "5000.00", dt.date(2026, 5, 1)))
        post_journal(pay(accounts["petty"], accounts["sales"], "100.00", dt.date(2026, 5, 2)))
        post_journal(pay(accounts["office"], accounts["petty"], "517.22", dt.date(2026, 6, 3)))
        post_journal(pay(accounts["office"], accounts["petty"], "576.95", dt.date(2026, 6, 15)))
    return organisation


def _run(org: Organisation, **params: Any) -> Any:
    return registry.get("balance_sheet").run(org, params)


def _rows(result: Any) -> dict[str, Any]:
    return {row.key: row for row in [*result.rows, *result.totals]}


def _keys_between(result: Any, start: str, end: str) -> list[str]:
    keys = [row.key for row in result.rows]
    return keys[keys.index(start) + 1 : keys.index(end)]


def test_petty_cash_minus_994_17_is_a_liability_with_the_note(org: Organisation) -> None:
    result = _run(org, as_of="2026-06-30")
    rows = _rows(result)
    assert "account:1010" not in _keys_between(
        result, "group:current_assets", "total:current_assets"
    )
    overdraft = rows["overdraft:1010"]
    assert (overdraft.label, overdraft.values) == ("Bank overdraft — Petty Cash", [D("994.17")])
    assert "overdraft:1010" in _keys_between(
        result, "group:current_liabilities", "total:current_liabilities"
    )
    assert rows["total:current_liabilities"].values == [D("994.17")]
    note = rows["note:overdraft"]
    assert (note.kind, note.label) == ("text", NOTE)
    assert rows["total:assets"].values == [D("5000.00")]
    assert rows["total:liabilities_and_equity"].values == rows["total:assets"].values
    assert result.alerts == []  # balanced: no integrity banner


def test_comparatives_move_only_the_overdrawn_column(org: Organisation) -> None:
    result = _run(org, as_of="2026-06-30", compare="previous", periods=1)
    rows = _rows(result)
    dates = [c.label for c in result.columns]
    assert len(dates) == 2
    assert rows["account:1010"].values == [D("0.00"), D("100.00")]  # 31 May: still funded
    assert rows["overdraft:1010"].values == [D("994.17"), D("0.00")]
    for key in ("total:assets", "total:liabilities_and_equity"):
        assert rows[key].values == [D("5000.00"), D("5100.00")]


def test_no_overdraft_no_note() -> None:
    org = Organisation.objects.create(name="Funded Ltd.")
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["petty"], accounts["sales"], "100.00", dt.date(2026, 5, 2)))
    rows = _rows(_run(org, as_of="2026-06-30"))
    assert rows["account:1010"].values == [D("100.00")]
    assert not any(key.startswith(("overdraft:", "note:")) for key in rows)
