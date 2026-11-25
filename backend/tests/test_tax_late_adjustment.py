"""G-03-T08 — late adjustments: a document flagged ``late_adjustment`` and dated in a filed
period posts; its tax is reported on the next open period's line 104 (more net tax) or 107 (less)
and is listed on that return. Acceptance: back-dated 113.00 of tax appears on the next return's
line 104."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.audit.models import AuditEvent
from numo9.orgsettings.locks import LockedPeriod
from numo9.tax import returns
from numo9.tax.models import FilingPeriod, LateAdjustment, TaxError
from numo9.tenancy.context import org_context
from tests.return_helpers import post_purchase, post_sale, quarterly_books

pytestmark = pytest.mark.django_db
day = dt.date


def file(period: FilingPeriod, who: dict[str, object], number: str = "GH-1") -> None:
    draft = returns.prepare(period, who["owner"])
    returns.file(returns.review(draft, who["adviser"]), who["owner"], confirmation_no=number)


def test_back_dated_tax_goes_to_the_next_returns_line_104() -> None:
    reg, periods, who = quarterly_books()
    org = reg.organisation
    q1, q2 = periods[0], periods[1]
    file(q1, who)
    with pytest.raises(LockedPeriod):  # without the flag: refused by the Tax lock
        post_sale(org, day(2026, 3, 20), who["owner"], tax="113.00")
    entry = post_sale(org, day(2026, 3, 20), who["owner"], tax="113.00", late_adjustment=True)
    assert entry.date == day(2026, 3, 20)  # posted on its own date
    with org_context(org):
        (row,) = LateAdjustment.objects.all()
        assert (row.journal, row.filed_period, row.target_period) == (entry, q1, q2)
        assert (row.line, str(row.amount), row.registration) == ("104", "113.00", reg)
        event = AuditEvent.objects.get(action="tax.return.late_adjustment")
        assert event.meta["reported_in"] == "2026-04-01 – 2026-06-30"
    draft = returns.prepare(q2, who["owner"])
    assert draft.lines["104"] == "113.00" and draft.lines["107"] == "0.00"
    listed = returns.late_adjustment_rows(q2)
    assert [(r["line"], r["amount"], r["document_date"], r["filed_period"]) for r in listed] == [
        ("104", "113.00", "2026-03-20", "2026-01-01 – 2026-03-31"),
    ]
    assert listed[0]["journal_number"] == entry.number
    # A late purchase lowers net tax: line 107, and the return in progress is updated at once.
    with returns.late_adjustments():
        post_purchase(org, day(2026, 2, 10), who["owner"], tax="26.00")
    with org_context(org):
        draft.refresh_from_db()
    assert (draft.lines["104"], draft.lines["107"]) == ("113.00", "26.00")
    assert returns.adjustment_lines(q1) == {"104": "0.00", "107": "0.00"}  # the filed one: none


def test_the_flag_only_matters_in_a_filed_period() -> None:
    reg, periods, who = quarterly_books("Open Ltd.")
    org = reg.organisation
    post_sale(org, day(2026, 3, 20), who["owner"], late_adjustment=True)  # Q1 open: normal
    with org_context(org):
        assert not LateAdjustment.objects.exists()
    file(periods[0], who)
    file(periods[1], who, "GH-2")
    post_sale(org, day(2026, 1, 5), who["owner"], tax="10.00", late_adjustment=True)
    with org_context(org):  # skips the filed Q2: the next period that isn't filed
        assert LateAdjustment.objects.get().target_period == periods[2]


def test_no_open_period_to_carry_it_is_refused() -> None:
    reg, periods, who = quarterly_books("Closed Ltd.")
    for index, period in enumerate(periods):
        file(period, who, f"GH-{index}")
    with pytest.raises(TaxError) as refused:
        post_sale(reg.organisation, day(2026, 12, 5), who["owner"], late_adjustment=True)
    assert refused.value.code == "tax.return.no_open_period"
    with org_context(reg.organisation):
        assert not LateAdjustment.objects.exists()
