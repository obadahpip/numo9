"""V-04-T04 — workload provider: organisations per staff member, open tasks placeholder.

Acceptance: matches the assignments — direct and through groups (V-02), within the dashboard's
scope (an organisation the viewer can't see isn't counted; archived ones neither); suspended
members left out; open tasks 0 until tasks exist; busiest first.
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.tenancy.models import PracticeMember
from numo9.workspace.dashboard import ALL, MINE, DashboardContext, answer_all
from numo9.workspace.models import GroupStaffAssignment, OrgGroup, OrgGroupMembership
from tests.dashboard_helpers import Firm, build_firm

pytestmark = pytest.mark.django_db


def workload(firm: Firm, person: PracticeMember, scope: str = ALL) -> list[dict[str, Any]]:
    ctx = DashboardContext(user=person.user, practice=firm.practice, member=person, scope=scope)
    (widget,) = [w for w in answer_all(ctx) if w["key"] == "workload"]
    assert widget["status"] == "ok"
    items: list[dict[str, Any]] = widget["items"]
    return items


def admin(firm: Firm) -> PracticeMember:
    return PracticeMember.objects.get(practice=firm.practice, user=firm.admin)


def test_matches_the_assignments() -> None:
    firm = build_firm()
    rows = workload(firm, admin(firm))
    assert [(r["name"], r["organisations"], r["open_tasks"]) for r in rows] == [
        ("Sam Patel", 3, 0),  # Maple, Birch, Cedar
        ("Ada Admin", 0, 0),
        ("Lina Roy", 0, 0),
    ]


def test_group_assignments_count_and_archived_do_not() -> None:
    firm = build_firm()
    group = OrgGroup.add_root(practice=firm.practice, name="Year-end")
    for name in ("Pine", "Spruce", "Fir"):  # Fir is archived
        OrgGroupMembership.objects.create(group=group, organisation=firm.orgs[name])
    GroupStaffAssignment.objects.create(group=group, practice_member=firm.lina, role="reviewer")
    by_name = {r["name"]: r["organisations"] for r in workload(firm, admin(firm))}
    assert by_name["Lina Roy"] == 2


def test_scope_limits_the_counts_and_suspended_are_left_out() -> None:
    firm = build_firm()
    from django.utils import timezone

    PracticeMember.objects.filter(pk=firm.lina.pk).update(suspended_at=timezone.now())
    rows = workload(firm, admin(firm), MINE)  # the admin's own organisations: none
    assert {r["name"] for r in rows} == {"Ada Admin", "Sam Patel"}
    assert all(r["organisations"] == 0 for r in rows)
