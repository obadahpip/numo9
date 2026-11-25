"""C-07-T04 — recode preview: before/after per line, totals unchanged, tax impact recalculated
(unit + Hypothesis over random recodes of the fixture)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.ledger.recode_preview import preview
from numo9.tenancy.context import org_context
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db
EVERYTHING = {"conditions": [{"field": "date", "op": "after", "value": "2025-12-31"}]}


@pytest.fixture
def books() -> dict[str, Any]:
    return recode_books()


def pid(books: dict[str, Any], key: str) -> str:
    return str(books[key].public_id)


def run(books: dict[str, Any], criteria: Any, changes: Any) -> Any:
    with org_context(books["org"]):
        return preview(books["org"], criteria, changes, books["adviser"])


def test_account_recode_before_after(books: dict[str, Any]) -> None:
    criteria = {"conditions": [{"field": "account", "op": "is", "value": pid(books, "expense")}]}
    result = run(
        books, criteria, {"account": pid(books, "expense2"), "tracking": {"region": "north"}}
    )
    rows = [r.as_dict() for r in result.lines]
    assert [(r["number"], r["line_no"], r["debit"]) for r in rows] == [
        (books["entries"][1].number, 1, "200.00"),
        (books["entries"][3].number, 1, "75.00"),
    ]
    assert rows[0]["before"] == {
        "account": pid(books, "expense"),
        "tax_code": "purchase.ON.standard",
        "tracking": {"region": "east"},
        "contact": pid(books, "bolt"),
    }
    assert rows[0]["after"] == {
        **rows[0]["before"],
        "account": pid(books, "expense2"),
        "tracking": {"region": "north"},
    }
    assert rows[0]["changed"] == ["account", "tracking"]
    assert result.totals_unchanged and result.totals_before == result.totals_after
    assert result.totals_before["accounting"] == {
        "debit": Decimal("200.00"),
        "credit": Decimal("0.00"),
    }
    assert result.totals_before["tax"] == {"debit": Decimal("275.00"), "credit": Decimal("0.00")}
    moves = result.accounts
    assert moves[pid(books, "expense")] == {"before": Decimal("275.00"), "after": Decimal("0.00")}
    assert moves[pid(books, "expense2")] == {"before": Decimal("0.00"), "after": Decimal("275.00")}
    assert result.tax_impact == [] and not result.needs_confirmation
    assert result.summary()["lines"] == 2
    assert result.summary()["entries"] == 2


def test_tax_recode_recalculates_the_split(books: dict[str, Any]) -> None:
    criteria = {"conditions": [{"field": "tax_code", "op": "is", "value": "sales.ON.standard"}]}
    result = run(books, criteria, {"tax_code": "sales.zero_rated"})
    (impact,) = result.tax_impact
    assert (impact["base"], impact["from"], impact["to"]) == (
        "1000.00",
        "sales.ON.standard",
        "sales.zero_rated",
    )
    assert sum(Decimal(v) for v in impact["before"].values()) == Decimal("130.00")
    assert sum(Decimal(v) for v in impact["after"].values()) == Decimal("0.00")
    assert impact["delta"] == "-130.00" and result.tax_delta == Decimal("-130.00")
    assert result.needs_confirmation and result.totals_unchanged


def test_unchanged_and_excluded_counted(books: dict[str, Any]) -> None:
    import datetime as dt

    from numo9.orgsettings.models import LockDate

    with org_context(books["org"]):
        LockDate(
            organisation=books["org"],
            module="gl",
            level="everyone",
            date=dt.date(2026, 1, 31),
            reason="Closing January",
        ).save()
    result = run(books, EVERYTHING, {"account": pid(books, "bank")})
    assert result.unchanged == 3  # the bank lines of Feb–Apr already are
    assert len(result.excluded) == 2 and {x.reason.code for x in result.excluded} == {"locked"}
    assert len(result.lines) == 3


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"amount": "1"},
        {"account": "nope"},
        {"tracking": "east"},
        {"tax_code": 13},
        {"contact": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_changes_refused(books: dict[str, Any], changes: Any) -> None:
    with pytest.raises(ValidationError) as caught:
        run(books, EVERYTHING, changes)
    assert "ledger.recode.changes_invalid" in str(caught.value.error_dict["changes"][0].code)


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(data=st.data())
def test_property_preview_totals_equal_original_totals(books: dict[str, Any], data: Any) -> None:
    accounts = [pid(books, k) for k in ("bank", "revenue", "expense", "expense2")]
    fields = data.draw(
        st.sets(st.sampled_from(["account", "tax_code", "tracking", "contact"]), min_size=1)
    )
    changes: dict[str, Any] = {}
    if "account" in fields:
        changes["account"] = data.draw(st.sampled_from(accounts))
    if "tax_code" in fields:
        changes["tax_code"] = data.draw(
            st.sampled_from(["", "sales.ON.standard", "sales.zero_rated", "purchase.ON.standard"])
        )
    if "tracking" in fields:
        changes["tracking"] = {"region": data.draw(st.sampled_from(["east", "west", None]))}
    if "contact" in fields:
        changes["contact"] = data.draw(
            st.sampled_from([None, pid(books, "acme"), pid(books, "bolt")])
        )
    picked = data.draw(st.sets(st.sampled_from(accounts), min_size=1))
    criteria = {"conditions": [{"field": "account", "op": "in", "value": sorted(picked)}]}
    result = run(books, criteria, changes)
    assert result.totals_unchanged
    for book in ("accounting", "tax"):
        found = [r.line for r in result.lines if r.line.book in (book, "both")]
        assert result.totals_after[book]["debit"] == sum((x.debit for x in found), Decimal("0"))
        assert result.totals_after[book]["credit"] == sum((x.credit for x in found), Decimal("0"))
    before = sum((v["before"] for v in result.accounts.values()), Decimal("0"))
    after = sum((v["after"] for v in result.accounts.values()), Decimal("0"))
    assert before == after
    for row in result.lines:
        assert row.changed and all(
            row.after[k] == row.before[k]
            for k in ("account", "tax_code", "tracking", "contact")
            if k not in row.changed
        )
