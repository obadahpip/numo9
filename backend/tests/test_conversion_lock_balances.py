"""C-05-T06 — "lock balances" on finalise: the GL, AR and AP lock dates for everyone except
advisers move to the conversion date − 1, audited.

Acceptance: lock set and audited; a later lock already set stays; without the option no lock is
touched; afterwards a non-adviser can't post before the conversion date, an adviser can.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.conversion.finalise import finalise
from numo9.conversion.services import set_line
from numo9.orgsettings.locks import check_lock
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from tests.conversion_helpers import acct, conversion_books

pytestmark = pytest.mark.django_db
DAY_BEFORE = dt.date(2025, 12, 31)


@pytest.fixture
def books() -> dict[str, Any]:
    books = conversion_books()
    set_line(books["session"], acct(books, "1010"), debit="100.00")
    set_line(books["session"], acct(books, "3000"), credit="100.00")
    return books


def locks(books: dict[str, Any]) -> dict[tuple[str, str], dt.date | None]:
    with org_context(books["org"]):
        return {(r.module, r.level): r.date for r in LockDate.objects.all()}


def test_lock_set_and_audited(books: dict[str, Any]) -> None:
    session = finalise(books["session"], books["owner"], lock=True)
    assert session.lock_balances is True
    assert locks(books) == {
        ("gl", "advisers_only"): DAY_BEFORE,
        ("ar", "advisers_only"): DAY_BEFORE,
        ("ap", "advisers_only"): DAY_BEFORE,
    }
    with org_context(books["org"]):
        events = list(
            AuditEvent.objects.filter(action="orgsettings.lockdate.created").order_by("id")
        )
        assert len(events) == 3
        assert all(e.changes["date"] == [None, "2025-12-31"] for e in events)
        assert all("Conversion balances finalised" in e.changes["reason"][1] for e in events)
        assert {e.actor_user_id for e in events} == {books["owner"].pk}
        (done,) = AuditEvent.objects.filter(action="conversion.session.finalised")
        assert sorted(done.meta["locked"]) == ["ap", "ar", "gl"]
        org = books["org"]
        assert check_lock(org, "ar", DAY_BEFORE, books["owner"]) is not None
        assert check_lock(org, "ar", DAY_BEFORE, books["adviser"]) is None
        assert check_lock(org, "gl", dt.date(2026, 1, 1), books["owner"]) is None


def test_saved_choice_used_and_later_lock_kept(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        later = LockDate(organisation=books["org"], module="ap", level="advisers_only")
        later.set_lock(dt.date(2026, 1, 1) - dt.timedelta(days=0))
        later.save()
        session = books["session"]
        session.lock_balances = True
        session.save()
    finalise(books["session"], books["owner"])
    found = locks(books)
    assert found[("ap", "advisers_only")] == dt.date(2026, 1, 1)  # never moved back
    assert found[("gl", "advisers_only")] == DAY_BEFORE


def test_without_the_option_nothing_is_locked(books: dict[str, Any]) -> None:
    finalise(books["session"], books["owner"])
    assert locks(books) == {}
