"""V-04-T03 — Phase 0 providers: trials expiring ≤ 7 days, organisations missing a BN, missing a
lock date, read-only organisations, dormant staff.

Acceptance: counts = the fixture (tests/dashboard_helpers.py), for the whole practice and for
"my organisations"; archived organisations never counted; dormant staff only for those who
manage staff; zero is 0, not empty.
"""

from __future__ import annotations

import pytest

from numo9.tenancy.models import PracticeMember
from numo9.workspace.dashboard import ALL, MINE, DashboardContext, answer_all
from tests.dashboard_helpers import Firm, build_firm

pytestmark = pytest.mark.django_db


@pytest.fixture
def firm() -> Firm:
    return build_firm()


def counts(firm: Firm, person: PracticeMember, scope: str) -> dict[str, int | None]:
    ctx = DashboardContext(user=person.user, practice=firm.practice, member=person, scope=scope)
    return {w["key"]: w["count"] for w in answer_all(ctx) if w["kind"] == "count"}


def admin(firm: Firm) -> PracticeMember:
    return PracticeMember.objects.get(practice=firm.practice, user=firm.admin)


def test_practice_wide_counts_equal_the_fixture(firm: Firm) -> None:
    assert counts(firm, admin(firm), ALL) == {
        "trials_ending": 1,  # Maple (Birch ends in 10 days)
        "missing_bn": 2,  # Maple, Cedar (Fir is archived)
        "missing_lock_date": 2,  # Maple, Pine
        "read_only": 2,  # Cedar, Spruce
        "dormant_staff": 1,  # Lina, 61 days
    }


def test_my_organisations(firm: Firm) -> None:
    sam = counts(firm, firm.sam, MINE)
    assert sam == {"trials_ending": 1, "missing_bn": 2, "missing_lock_date": 1, "read_only": 1}
    assert "dormant_staff" not in sam  # staff management only
    assert counts(firm, admin(firm), MINE) == {
        "trials_ending": 0,  # the admin isn't assigned to any client: 0, not empty
        "missing_bn": 0,
        "missing_lock_date": 0,
        "read_only": 0,
        "dormant_staff": 1,
    }


def test_each_count_carries_its_drill_filters(firm: Firm) -> None:
    ctx = DashboardContext(user=firm.sam.user, practice=firm.practice, member=firm.sam, scope=MINE)
    filters = {w["key"]: w["filters"] for w in answer_all(ctx) if w["kind"] == "count"}
    assert filters["trials_ending"] == {
        "status": ["trial"],
        "trial_ending": ["yes"],
        "mine": ["yes"],
    }
    assert filters["missing_bn"] == {"bn_missing": ["yes"], "mine": ["yes"]}
    assert filters["missing_lock_date"] == {"lock_missing": ["yes"], "mine": ["yes"]}
    assert filters["read_only"] == {"status": ["read_only"], "mine": ["yes"]}


@pytest.mark.django_db(transaction=True)
def test_a_new_lock_date_reaches_the_directory_row() -> None:
    import datetime as dt

    from numo9.orgsettings.models import LockDate
    from numo9.tenancy.context import org_context
    from numo9.workspace.models import OrgDirectorySummary
    from tests.workspace_helpers import client_org, practice

    org = client_org(practice("Abuodeh CPA"), "Maple")
    from numo9.workspace.summary import rebuild_all

    rebuild_all()
    assert OrgDirectorySummary.objects.get(organisation=org).lock_date is None
    with org_context(org):
        LockDate(organisation=org, module="ap", level="everyone", date=dt.date(2026, 3, 31)).save()
    assert OrgDirectorySummary.objects.get(organisation=org).lock_date == dt.date(2026, 3, 31)
