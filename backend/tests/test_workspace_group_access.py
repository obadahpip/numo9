"""V-02-T05 — Effective access: direct ∪ group ∪ ancestor groups, cached per user.

Property (Hypothesis): over random practice trees (depth ≤ 5), random filing of organisations,
random staff assignments to groups, random direct assignments, practice admins and switched-off
practice assignments, ``accessible_organisations`` and ``can_access`` equal a brute-force model of
the rule: a user reaches an organisation when they're a member, a practice admin of a practice
actively serving it, its assigned staff, or assigned to a group that holds it — the group or any
of its descendants — of a practice actively serving it. Also, with examples: an organisation added
later to a group is reachable at once; the cache answers repeated checks without a query; another
practice's groups never grant anything.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.accounts.models import User
from numo9.tenancy.access import accessible_organisations, can_access
from numo9.tenancy.models import Organisation, Practice, PracticeAssignment, PracticeMember
from numo9.workspace.access import group_organisation_ids
from numo9.workspace.groups import add_organisation, assign_staff, create_group
from numo9.workspace.models import OrgGroup

pytestmark = pytest.mark.django_db
_n = itertools.count(1)

#: A random world: per practice a tree (parent index per group, -1 = top), filings, staff.
world = st.fixed_dictionaries(
    {
        "trees": st.lists(
            st.lists(st.integers(min_value=-1, max_value=6), min_size=1, max_size=7),
            min_size=1,
            max_size=2,
        ),
        "orgs": st.integers(min_value=1, max_value=5),
        "served": st.lists(st.booleans(), min_size=10, max_size=10),
        "active": st.lists(st.booleans(), min_size=10, max_size=10),
        "filings": st.lists(st.tuples(st.integers(0, 6), st.integers(0, 4)), max_size=12),
        "staff": st.lists(st.tuples(st.integers(0, 6), st.integers(0, 2)), max_size=6),
        "direct": st.lists(st.tuples(st.integers(0, 4), st.integers(0, 2)), max_size=4),
        "admins": st.lists(st.integers(0, 2), max_size=2),
    }
)


def build(spec: dict[str, Any]) -> tuple[list[User], list[Organisation], dict[int, set[int]]]:
    """Create the world and return users, organisations and the expected access per user."""
    run = next(_n)
    orgs = [Organisation.objects.create(name=f"Org {run}-{i}") for i in range(spec["orgs"])]
    users = [User.objects.create_user(f"u{run}-{i}@cpa.ca", password="x" * 12) for i in range(3)]
    expected: dict[int, set[int]] = {u.pk: set() for u in users}
    for p_index, parents in enumerate(spec["trees"]):
        practice = Practice.objects.create(name=f"Practice {run}-{p_index}")
        members = [
            PracticeMember.objects.create(
                practice=practice,
                user=u,
                role="practice_admin" if i in spec["admins"] and p_index == 0 else "accountant",
            )
            for i, u in enumerate(users)
        ]
        assignments: dict[int, PracticeAssignment] = {}
        for o_index, org in enumerate(orgs):
            k = p_index * 5 + o_index
            if spec["served"][k]:
                assignments[o_index] = PracticeAssignment.objects.create(
                    practice=practice, organisation=org
                )
                assignments[o_index].keep = spec["active"][k]  # type: ignore[attr-defined]
        groups: list[OrgGroup] = []
        parent_of: dict[int, int] = {}
        for g_index, parent in enumerate(parents):
            target = groups[parent] if 0 <= parent < len(groups) else None
            if target is not None and target.depth >= 5:
                target = None
            group = create_group(practice, f"G{g_index}", target)
            groups.append(group)
            parent_of[g_index] = groups.index(target) if target is not None else -1
        holds: dict[int, set[int]] = {g: set() for g in range(len(groups))}
        for g_index, o_index in spec["filings"]:
            if g_index < len(groups) and o_index < len(orgs) and o_index in assignments:
                add_organisation(groups[g_index], orgs[o_index])
                holds[g_index].add(o_index)

        def subtree(g: int, parent_of: dict[int, int] = parent_of) -> set[int]:
            out = {g}
            for child, parent in parent_of.items():
                if parent == g:
                    out |= subtree(child, parent_of)
            return out

        # Switch some assignments off after filing: their memberships go (V-02-T02).
        for assignment in assignments.values():
            if not assignment.keep:  # type: ignore[attr-defined]
                assignment.active = False
                assignment.save()
        for g_index, u_index in spec["staff"]:
            if g_index < len(groups):
                assign_staff(groups[g_index], members[u_index])
                for g in subtree(g_index):
                    for o in holds[g]:
                        if assignments[o].active:
                            expected[users[u_index].pk].add(orgs[o].pk)
        for o_index, u_index in spec["direct"]:
            if o_index < len(orgs) and o_index in assignments and p_index == 0:
                assignments[o_index].assigned_staff.add(members[u_index])
                if assignments[o_index].active:
                    expected[users[u_index].pk].add(orgs[o_index].pk)
        for u_index in spec["admins"]:
            if p_index == 0:
                for o, assignment in assignments.items():
                    if assignment.active:
                        expected[users[u_index].pk].add(orgs[o].pk)
    return users, orgs, expected


@settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(spec=world)
def test_access_equals_the_rule(spec: dict[str, Any]) -> None:
    users, orgs, expected = build(spec)
    for user in users:
        got = set(
            accessible_organisations(user)
            .filter(pk__in=[o.pk for o in orgs])
            .values_list("pk", flat=True)
        )
        assert got == expected[user.pk]
        for org in orgs:
            assert can_access(user, org) == (org.pk in expected[user.pk])


def test_added_later_and_cached() -> None:
    practice = Practice.objects.create(name="Abuodeh CPA")
    user = User.objects.create_user("priya@cpa.ca", password="x" * 12)
    member = PracticeMember.objects.create(practice=practice, user=user, role="accountant")
    toronto = create_group(practice, "Toronto office")
    retail = create_group(practice, "Retail clients", toronto)
    assign_staff(toronto, member)
    later = Organisation.objects.create(name="Joined Later Inc.")
    PracticeAssignment.objects.create(practice=practice, organisation=later)
    assert not can_access(user, later)
    add_organisation(retail, later)
    assert can_access(user, later)  # the sub-group's new organisation, at once
    group_organisation_ids(user)
    with CaptureQueriesContext(connection) as queries:
        assert later.pk in group_organisation_ids(user)
    assert len(queries) == 0  # answered from the per-user cache


def test_other_practices_groups_grant_nothing() -> None:
    mine, theirs = Practice.objects.create(name="Mine"), Practice.objects.create(name="Theirs")
    user = User.objects.create_user("sam@cpa.ca", password="x" * 12)
    member = PracticeMember.objects.create(practice=mine, user=user, role="accountant")
    org = Organisation.objects.create(name="Their client")
    PracticeAssignment.objects.create(practice=theirs, organisation=org)
    their_group = create_group(theirs, "Theirs")
    add_organisation(their_group, org)
    assign_staff(create_group(mine, "Mine"), member)
    assert not can_access(user, org)
