"""A-05-T05 — Lock service ``assert_not_locked(org, module, date, user)`` returning
``LockViolation(module, level, date)``.

Acceptance: the message names the lock (module, date, level). Also: on-or-before refused, after
allowed; advisers pass the advisers-only level but not the everyone level; read-only practice
staff, organisation users and system changes are stopped by both; the GL lock applies to every
module and the module's own lock is named first; organisation-local dates (a date-time late on
31 March UTC is 31 March in Toronto); no lock / removed lock / deleted lock = allowed; property:
for any lock date and change date, refused ⇔ change date ≤ lock date.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from numo9.accounts.models import User
from numo9.orgsettings.locks import LockedPeriod, assert_not_locked, check_lock, is_adviser
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)

pytestmark = pytest.mark.django_db

MARCH_31 = dt.date(2026, 3, 31)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")


def lock(org: Organisation, module: str, level: str, date: dt.date | None) -> LockDate:
    with org_context(org):
        row = LockDate(organisation=org, module=module, level=level, date=date)
        row.save()
        return row


def _user(email: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=email)


@pytest.fixture
def people(org: Organisation) -> dict[str, User]:
    practice = Practice.objects.create(name="North Star CPA")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    found: dict[str, User] = {}
    for role in ("accountant", "read_only"):
        user = _user(f"{role}@northstar.ca")
        member = PracticeMember.objects.create(practice=practice, user=user, role=role)
        assignment.assigned_staff.add(member)
        found[role] = user
    owner = _user("dana@refined.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    found["owner"] = owner
    return found


def test_violation_names_the_lock(org: Organisation, people: dict[str, User]) -> None:
    lock(org, "ar", "everyone", MARCH_31)
    with pytest.raises(LockedPeriod) as raised:
        assert_not_locked(org, "ar", MARCH_31, people["owner"])
    violation = raised.value.violation
    assert (violation.module, violation.level, violation.date) == ("ar", "everyone", MARCH_31)
    assert raised.value.status_code == 409
    detail: Any = raised.value.detail
    assert detail["code"] == "lock.violation"
    assert detail["lock"] == {"module": "ar", "level": "everyone", "date": "2026-03-31"}
    assert str(detail["detail"]) == (
        "The Sales and accounts receivable lock date is 2026-03-31 (everyone): changes dated on "
        "or before it are refused. Date it after 2026-03-31, or ask someone who manages lock dates."
    )
    assert_not_locked(org, "ar", dt.date(2026, 4, 1), people["owner"])  # after: allowed
    assert check_lock(org, "ap", MARCH_31, people["owner"]) is None  # another module


def test_advisers_only_level(org: Organisation, people: dict[str, User]) -> None:
    lock(org, "gl", "advisers_only", MARCH_31)
    assert is_adviser(people["accountant"], org) and not is_adviser(people["read_only"], org)
    assert check_lock(org, "gl", MARCH_31, people["accountant"]) is None
    for who in (people["read_only"], people["owner"], None):
        violation = check_lock(org, "gl", MARCH_31, who)
        assert violation is not None and violation.level == "advisers_only"
    lock(org, "gl", "everyone", dt.date(2026, 2, 28))
    stopped = check_lock(org, "gl", dt.date(2026, 2, 15), people["accountant"])
    assert stopped is not None and stopped.level == "everyone"


def test_inactive_assignment_is_no_adviser(org: Organisation, people: dict[str, User]) -> None:
    PracticeAssignment.objects.update(active=False)
    assert not is_adviser(people["accountant"], org)


def test_gl_lock_applies_to_every_module_and_own_lock_named_first(org: Organisation) -> None:
    lock(org, "gl", "everyone", MARCH_31)
    for module in ("ar", "ap", "bank", "payroll", "tax"):
        violation = check_lock(org, module, dt.date(2026, 3, 1))
        assert violation is not None and violation.module == "gl"
    lock(org, "ar", "everyone", dt.date(2026, 6, 30))
    violation = check_lock(org, "ar", dt.date(2026, 3, 1))
    assert violation is not None and violation.module == "ar"


def test_organisation_local_date(org: Organisation) -> None:
    lock(org, "gl", "everyone", MARCH_31)
    # 2026-04-01 02:30 UTC = 2026-03-31 22:30 in Toronto: still the 31st → locked.
    late_evening = dt.datetime(2026, 4, 1, 2, 30, tzinfo=dt.UTC)
    assert check_lock(org, "gl", late_evening) is not None
    next_morning = dt.datetime(2026, 4, 1, 12, 0, tzinfo=dt.UTC)
    assert check_lock(org, "gl", next_morning) is None


def test_no_lock_removed_or_deleted(org: Organisation) -> None:
    row = lock(org, "gl", "everyone", None)
    assert check_lock(org, "gl", MARCH_31) is None
    with org_context(org):
        row.set_lock(MARCH_31)
        row.save()
    assert check_lock(org, "gl", MARCH_31) is not None
    with org_context(org):
        row.soft_delete()
    assert check_lock(org, "gl", MARCH_31) is None
    with pytest.raises(ValueError):
        check_lock(org, "nope", MARCH_31)


@settings(max_examples=60, deadline=None)
@given(
    lock_day=st.dates(dt.date(2024, 1, 1), dt.date(2027, 12, 31)),
    change_day=st.dates(dt.date(2024, 1, 1), dt.date(2027, 12, 31)),
)
def test_property_refused_iff_on_or_before(lock_day: dt.date, change_day: dt.date) -> None:
    org = Organisation.objects.create(name="Property Co.")
    lock(org, "gl", "everyone", lock_day)
    assert (check_lock(org, "gl", change_day) is not None) == (change_day <= lock_day)
