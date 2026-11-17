"""C-02-T07 — Lock-date and period hook. Acceptance: a pre-lock date is refused naming the lock.

Also: the day after the lock passes; the module's own lock (AR) is named before the GL lock;
advisers pass an advisers-only lock; a system posting is stopped; no period check registered →
open (C-06 stub); a registered closed period is refused naming it (409 ``ledger.period.closed``),
and checked after the lock; French message.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from django.utils import translation

from numo9.accounts.models import User
from numo9.ledger.periods import (
    ClosedPeriod,
    PeriodClosed,
    assert_can_post,
    closed_period,
    register_period_check,
    unregister_period_check,
)
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, Practice, PracticeAssignment, PracticeMember

pytestmark = pytest.mark.django_db

LOCK = dt.date(2026, 3, 31)
FY2025 = ClosedPeriod(dt.date(2025, 1, 1), dt.date(2025, 12, 31), "Fiscal year 2025")


def _lock(org: Organisation, module: str, level: str, day: dt.date = LOCK) -> None:
    with org_context(org):
        LockDate(organisation=org, module=module, level=level, date=day).save()


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def fy2025_closed() -> Iterator[None]:
    def check(organisation: Organisation, date: dt.date) -> ClosedPeriod | None:
        return FY2025 if FY2025.start <= date <= FY2025.end else None

    register_period_check(check)
    yield
    unregister_period_check(check)


def test_pre_lock_date_is_refused_naming_the_lock(org: Organisation) -> None:
    _lock(org, "gl", "everyone")
    with pytest.raises(LockedPeriod) as refused:
        assert_can_post(org, LOCK)
    body: Any = refused.value.detail
    assert body["code"] == "lock.violation"
    assert body["lock"] == {"module": "gl", "level": "everyone", "date": "2026-03-31"}
    assert "General ledger lock date is 2026-03-31" in str(body["detail"])
    with pytest.raises(LockedPeriod):
        assert_can_post(org, dt.date(2026, 1, 15))
    assert_can_post(org, dt.date(2026, 4, 1))


def test_module_lock_is_named_before_the_gl_lock(org: Organisation) -> None:
    _lock(org, "gl", "everyone")
    _lock(org, "ar", "everyone")
    with pytest.raises(LockedPeriod) as refused:
        assert_can_post(org, dt.date(2026, 3, 1), module="ar")
    assert refused.value.violation.module == "ar"
    _lock(org, "ap", "everyone", dt.date(2026, 6, 30))
    with pytest.raises(LockedPeriod) as ap:
        assert_can_post(org, dt.date(2026, 5, 1), module="ap")
    assert ap.value.violation.module == "ap"
    assert_can_post(org, dt.date(2026, 5, 1), module="ar")


def test_advisers_pass_an_advisers_only_lock(org: Organisation) -> None:
    _lock(org, "gl", "advisers_only")
    practice = Practice.objects.create(name="Tremblay CPA")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    adviser = User.objects.create_user(email="cpa@tremblay.ca", password="x" * 12)
    assignment.assigned_staff.add(
        PracticeMember.objects.create(practice=practice, user=adviser, role="accountant")
    )
    assert_can_post(org, LOCK, adviser)
    with pytest.raises(LockedPeriod):
        assert_can_post(org, LOCK, None)  # a system job is stopped like everyone


def test_no_period_check_means_open(org: Organisation) -> None:
    assert closed_period(org, dt.date(2020, 1, 1)) is None
    assert_can_post(org, dt.date(2020, 1, 1))


def test_closed_period_is_refused_naming_it(org: Organisation, fy2025_closed: None) -> None:
    with pytest.raises(PeriodClosed) as refused:
        assert_can_post(org, dt.date(2025, 12, 31))
    body: Any = refused.value.detail
    assert refused.value.status_code == 409 and body["code"] == "ledger.period.closed"
    assert body["period"]["label"] == "Fiscal year 2025"
    assert "Fiscal year 2025 (2025-01-01 to 2025-12-31) is closed" in str(body["detail"])
    assert_can_post(org, dt.date(2026, 1, 1))


def test_lock_is_checked_before_the_period(org: Organisation, fy2025_closed: None) -> None:
    _lock(org, "gl", "everyone", dt.date(2025, 12, 31))
    with pytest.raises(LockedPeriod):
        assert_can_post(org, dt.date(2025, 6, 30))


def test_french_period_message(org: Organisation, fy2025_closed: None) -> None:
    with translation.override("fr-ca"), pytest.raises(PeriodClosed) as refused:
        assert_can_post(org, dt.date(2025, 6, 30))
    detail: Any = refused.value.detail
    assert "est fermée" in str(detail["detail"])
