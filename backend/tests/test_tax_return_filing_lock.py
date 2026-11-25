"""G-03-T07 — on FILED: the Tax lock moves to the period's end (A-05) and the period is filed in
the filing-cycle engine. Acceptance: posting a GST document dated inside the period is refused
naming the lock."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.ledger.services import post_journal, reverse
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.tax import returns
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod, PeriodStatus
from numo9.tenancy.context import org_context
from tests.return_helpers import TODAY, account, post_sale, quarterly_books

pytestmark = pytest.mark.django_db
day = dt.date


def file(period: FilingPeriod, who: dict[str, object], number: str = "GH-1") -> object:
    draft = returns.prepare(period, who["owner"])
    return returns.file(returns.review(draft, who["adviser"]), who["owner"], confirmation_no=number)


def test_filing_locks_the_period_for_tax() -> None:
    reg, periods, who = quarterly_books()
    org = reg.organisation
    before = post_sale(org, day(2026, 3, 15), who["owner"])  # fine while the period is open
    file(periods[0], who)
    with org_context(org):
        q1 = FilingPeriod.objects.get(pk=periods[0].pk)
        assert (q1.status, q1.is_locked) == (PeriodStatus.FILED, True) and q1.filed_at is not None
        lock = LockDate.objects.get(module="tax", level="everyone")
        assert lock.date == day(2026, 3, 31) and "GH-1" in lock.reason
    for person in (who["owner"], who["adviser"]):  # everyone, advisers too
        with pytest.raises(LockedPeriod) as refused:
            post_sale(org, day(2026, 3, 20), person)
        assert refused.value.violation.as_dict() == {
            "module": "tax", "level": "everyone", "date": "2026-03-31",
        }  # fmt: skip
        assert "Sales tax lock date is 2026-03-31" in refused.value.violation.message()
    post_sale(org, day(2026, 4, 1), who["owner"])  # the next period is open
    with org_context(org):  # a journal without tax isn't stopped by the Tax lock
        plain = JournalSpec(
            date=day(2026, 3, 20),
            lines=[
                LineSpec(account(org, type="expense"), debit=Decimal("50.00")),
                LineSpec(account(org, type="liability"), credit=Decimal("50.00")),
            ],
        )
        post_journal(plain, organisation=org, user=who["owner"])
        with pytest.raises(LockedPeriod):  # nor can the filed sale be reversed inside the period
            reverse(before, user=who["owner"])
        reverse(before, date=day(2026, 4, 2), user=who["owner"])


def test_the_filed_period_never_changes_and_the_lock_never_moves_back() -> None:
    reg, periods, who = quarterly_books("Later Ltd.")
    org = reg.organisation
    file(periods[1], who, "GH-2")  # Q2 filed first: lock at 30 Jun
    file(periods[0], who, "GH-1")  # then Q1: the lock stays at 30 Jun
    with org_context(org):
        assert LockDate.objects.get(module="tax", level="everyone").date == day(2026, 6, 30)
    switch_frequency(reg, "monthly", day(2026, 7, 1), approval_ref="A-1", today=TODAY)
    with org_context(org):
        rows = list(FilingPeriod.objects.filter(registration=reg).order_by("start")[:3])
    assert [(p.start, p.end, p.status) for p in rows] == [
        (day(2026, 1, 1), day(2026, 3, 31), "filed"),
        (day(2026, 4, 1), day(2026, 6, 30), "filed"),
        (day(2026, 7, 1), day(2026, 7, 31), "open"),
    ]
