"""G-03-T14 — compliance fixtures for the GST/HST return (GST34): the regular method, the quick
method, a nil return, a refund, a stub period, the cash basis and a revision across periods (a
late adjustment of a filed period, then an amendment). Each fixture states the lines it expects
in ``tests/fixtures/gst_return/<name>.json``; the return the workflow prepares must equal them.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from numo9.tax import returns
from numo9.tax.cash_basis import register_payment_source, unregister_payment_source
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod
from numo9.tax.settings import tax_settings
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration
from tests.journal_helpers import people
from tests.return_helpers import account, quarterly_books
from tests.tax_report_helpers import june_books

pytestmark = pytest.mark.django_db
FIXTURES = Path(__file__).parent / "fixtures" / "gst_return"
D = Decimal
day = dt.date


def expected(name: str) -> dict[str, str]:
    data: dict[str, str] = json.loads((FIXTURES / f"{name}.json").read_text())["lines"]
    return data


def check(lines: dict[str, Any], name: str) -> None:
    import os

    if os.environ.get("NUMO9_WRITE_FIXTURES"):
        FIXTURES.mkdir(parents=True, exist_ok=True)
        keep = {k: v for k, v in lines.items() if k != "entries"}
        (FIXTURES / f"{name}.json").write_text(json.dumps({"lines": keep}, indent=2) + "\n")
    want = expected(name)
    got = {line: lines[line] for line in want}
    assert got == want, name
    # GST34 arithmetic: 105 = 103 + 104, 108 = 106 + 107, 109 = 105 − 108, 112 = 110 + 111,
    # 113A = 109 − 112, 113C = 113A + 113B, and 114 / 115 the refund / payment of 113C.
    v = {k: D(x) for k, x in lines.items() if k != "entries"}
    assert v["105"] == v["103"] + v["104"]
    assert v["108"] == v["106"] + v["107"]
    assert v["109"] == v["105"] - v["108"]
    assert v["112"] == v["110"] + v["111"]
    assert v["113A"] == v["109"] - v["112"]
    assert v["113C"] == v["113A"] + v["113B"]
    assert (v["114"], v["115"]) == ((-v["113C"], D("0")) if v["113C"] < 0 else (D("0"), v["113C"]))


def post_sale(org: Any, date: dt.date, user: Any, tax: str = "13.00", **spec: Any) -> Any:
    """A manual journal of a 100.00 Ontario sale plus ``tax`` of HST, carrying its tax part
    (what a sales document posts)."""
    from numo9.ledger.services import post_journal
    from numo9.ledger.validation import JournalSpec, LineSpec, TaxPart

    amount = D(tax)
    part = TaxPart(
        component="hst_on",
        kind="hst",
        side="sales",
        basis=D("100.00"),
        tax=amount,
        rate=D("13"),
        code="sales.ON.standard",
    )
    lines = [
        LineSpec(account(org, type="liability"), debit=D("100.00") + amount),
        LineSpec(account(org, type="revenue"), credit=D("100.00"), tax_parts=(part,)),
        LineSpec(account(org, "gst_hst_payable"), credit=amount),
    ]
    with org_context(org):
        return post_journal(
            JournalSpec(date=date, lines=lines, **spec), organisation=org, user=user
        )


def prepare(period: FilingPeriod, who: Any, **kw: Any) -> dict[str, Any]:
    lines: dict[str, Any] = returns.prepare(period, who, **kw).lines
    return lines


def test_regular() -> None:
    books = june_books()
    check(prepare(books["period"], books["owner"]), "regular")


def test_quick() -> None:
    books = june_books()
    org = books["org"]
    with org_context(org):
        settings = tax_settings(org)
        settings.quick_method = True
        settings.quick_method_from = day(2026, 1, 1)
        settings.quick_method_kind = "services"
        settings.save()
    check(prepare(books["period"], books["owner"], method="quick"), "quick")


def test_nil() -> None:
    _reg, periods, who = quarterly_books("Nil Ltd.")
    check(prepare(periods[0], who["owner"]), "nil")


def test_refund() -> None:
    books = june_books(with_inv_0001=False)
    check(prepare(books["period"], books["owner"]), "refund")


def test_stub_period() -> None:
    """Registered from 15 Feb: the first quarter is a stub, 15 Feb – 31 Mar; a sale on 20 Feb
    is on it."""
    from numo9.ledger.template import load_template

    reg = registration("Stub Ltd.", start=day(2026, 2, 15), stop=day(2026, 12, 31))
    load_template(reg.organisation, "ON")
    periods, _warnings = switch_frequency(reg, "quarterly", day(2026, 2, 15), today=day(2026, 6, 1))
    first = periods[0]
    assert (first.kind, first.start, first.end) == ("stub", day(2026, 2, 15), day(2026, 3, 31))
    who = people(reg.organisation)
    post_sale(reg.organisation, day(2026, 2, 20), who["owner"], tax="13.00")
    lines = prepare(first, who["owner"])
    assert lines["103"] == "13.00"
    check(lines, "stub")


class HalfPaid:
    """Every document half paid inside the period."""

    source_types = ("sales.invoice", "purchases.bill")

    def __init__(self, totals: dict[str, Decimal]) -> None:
        self.totals = totals

    def payments(
        self, organisation: Any, refs: list[str], start: dt.date, end: dt.date
    ) -> dict[str, tuple[Decimal, Decimal]]:
        return {r: (self.totals[r] / 2, self.totals[r]) for r in refs if r in self.totals}


@pytest.fixture
def half_paid() -> Iterator[dict[str, Any]]:
    books = june_books()
    source = HalfPaid({str(d.public_id): d.total for d in (*books["invoices"], *books["bills"])})
    register_payment_source(source)
    yield books
    unregister_payment_source(source)


def test_cash_basis(half_paid: dict[str, Any]) -> None:
    org = half_paid["org"]
    with org_context(org):
        settings = tax_settings(org)
        settings.basis = "cash"
        settings.save()
    check(prepare(half_paid["period"], half_paid["owner"]), "cash_basis")


def test_revision_across_periods() -> None:
    """Q1 is filed; a sale dated in Q1 posted later (flagged late) is reported on Q2's line 104;
    Q1 is then amended: version 2 leaves the late sale out (it is on Q2 already), so the 26.00
    is reported once; the filed version stays."""
    reg, periods, who = quarterly_books("Revision Ltd.")
    org = reg.organisation
    q1, q2 = periods[0], periods[1]
    post_sale(org, day(2026, 2, 10), who["owner"], tax="13.00")
    filed = returns.prepare(q1, who["owner"])
    filed = returns.file(returns.review(filed, who["adviser"]), who["owner"], confirmation_no="G1")
    post_sale(org, day(2026, 3, 20), who["owner"], tax="26.00", late_adjustment=True)
    post_sale(org, day(2026, 5, 5), who["owner"], tax="13.00")
    check(prepare(q2, who["owner"]), "revision_q2")
    amendment = returns.amend(filed, who["adviser"], "Late sale of 20 March")
    with org_context(org):
        amendment = returns.recalculate(amendment, who["adviser"])
    assert amendment.version == 2 and filed.lines["103"] == "13.00"
    check(amendment.lines, "revision_q1_amended")
