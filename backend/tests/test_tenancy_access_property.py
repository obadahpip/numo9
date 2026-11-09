"""A-01-T11 — property test: on random membership graphs, the access resolver agrees with an
independent reference model of the rule for every (user, organisation) pair.

Hypothesis draws users (active or not), organisations, practices, organisation memberships,
practice memberships with any practice role, practice assignments (active or not) and assigned
staff drawn from the assigned practice's members. Each example is built in a savepoint and rolled
back. 1,000 examples (acceptance criterion)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from django.db import transaction
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.accounts.models import User
from numo9.tenancy.access import PRACTICE_WIDE_ROLES, accessible_organisations, can_access
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)

pytestmark = [pytest.mark.django_db, pytest.mark.tenant_isolation]


@dataclass(frozen=True)
class Graph:
    users_active: tuple[bool, ...]
    n_orgs: int
    n_practices: int
    org_members: frozenset[tuple[int, int]]  # (user, org)
    practice_members: dict[tuple[int, int], str]  # (user, practice) -> practice role
    assignments: dict[tuple[int, int], bool]  # (practice, org) -> active
    staff: frozenset[tuple[int, int, int]]  # (practice, org, user)


@st.composite
def graphs(draw: st.DrawFn) -> Graph:
    users_active = tuple(draw(st.lists(st.booleans(), min_size=1, max_size=4)))
    n_users = len(users_active)
    n_orgs = draw(st.integers(1, 3))
    n_practices = draw(st.integers(0, 3))
    pairs = st.tuples(st.integers(0, n_users - 1), st.integers(0, n_orgs - 1))
    org_members = frozenset(draw(st.sets(pairs, max_size=n_users * n_orgs)))
    practice_members: dict[tuple[int, int], str] = {}
    assignments: dict[tuple[int, int], bool] = {}
    if n_practices:
        practice_members = draw(
            st.dictionaries(
                st.tuples(st.integers(0, n_users - 1), st.integers(0, n_practices - 1)),
                st.sampled_from(PracticeRole.values),
            )
        )
        assignments = draw(
            st.dictionaries(
                st.tuples(st.integers(0, n_practices - 1), st.integers(0, n_orgs - 1)),
                st.booleans(),
            )
        )
    # Staff of an assignment are members of the assigned practice (enforced by the model).
    candidates = sorted(
        (p, o, u) for (p, o) in assignments for (u, mp) in practice_members if mp == p
    )
    staff = frozenset(draw(st.sets(st.sampled_from(candidates)))) if candidates else frozenset()
    return Graph(
        users_active, n_orgs, n_practices, org_members, practice_members, assignments, staff
    )


def expected_access(g: Graph, user: int, org: int) -> bool:
    """Reference model of A-01-T05, written independently of the resolver."""
    if not g.users_active[user]:
        return False
    if (user, org) in g.org_members:
        return True
    for (practice, assigned_org), active in g.assignments.items():
        if assigned_org != org or not active:
            continue
        role = g.practice_members.get((user, practice))
        if role is None:
            continue
        if role in PRACTICE_WIDE_ROLES or (practice, org, user) in g.staff:
            return True
    return False


def build(g: Graph) -> tuple[list[User], list[Organisation]]:
    users = [
        User.objects.create_user(f"u{i}@example.com", name=f"U{i}", is_active=active)
        for i, active in enumerate(g.users_active)
    ]
    orgs = [Organisation.objects.create(name=f"Org {i}") for i in range(g.n_orgs)]
    practices = [Practice.objects.create(name=f"Practice {i}") for i in range(g.n_practices)]
    for u, o in g.org_members:
        OrganisationMember.objects.create(
            organisation=orgs[o], user=users[u], role=OrganisationRole.SALES
        )
    members = {
        (u, p): PracticeMember.objects.create(practice=practices[p], user=users[u], role=role)
        for (u, p), role in g.practice_members.items()
    }
    for (p, o), active in g.assignments.items():
        assignment = PracticeAssignment.objects.create(
            practice=practices[p], organisation=orgs[o], active=active
        )
        staff = [members[(u, p)] for (sp, so, u) in g.staff if (sp, so) == (p, o)]
        if staff:
            assignment.assigned_staff.add(*staff)
    return users, orgs


class _Rollback(Exception):
    pass


@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(graph=graphs())
def test_resolver_matches_reference_model_on_random_graphs(graph: Graph) -> None:
    try:
        with transaction.atomic():
            users, orgs = build(graph)
            for u, user in enumerate(users):
                expected_orgs = {
                    orgs[o].pk for o in range(graph.n_orgs) if expected_access(graph, u, o)
                }
                assert set(accessible_organisations(user).values_list("pk", flat=True)) == (
                    expected_orgs
                )
                for o, org in enumerate(orgs):
                    assert can_access(user, org) is expected_access(graph, u, o), (u, o)
            raise _Rollback
    except _Rollback:
        pass


def test_reference_model_sanity() -> None:
    g = Graph(
        users_active=(True, True, False),
        n_orgs=2,
        n_practices=1,
        org_members=frozenset({(2, 0)}),
        practice_members={(0, 0): PracticeRole.PRACTICE_ADMIN, (1, 0): PracticeRole.ACCOUNTANT},
        assignments={(0, 0): True, (0, 1): False},
        staff=frozenset({(0, 1, 1)}),
    )
    assert expected_access(g, 0, 0) is True  # practice admin, active assignment
    assert expected_access(g, 0, 1) is False  # assignment inactive
    assert expected_access(g, 1, 0) is False  # accountant not in staff
    assert expected_access(g, 1, 1) is False  # in staff but assignment inactive
    assert expected_access(g, 2, 0) is False  # inactive user, even as org member
