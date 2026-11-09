"""A-01-T05 — access resolver: can_access(user, org) = org member OR member of an actively
assigned practice with a practice-wide role or named in the assigned staff.

The truth table enumerates every valid combination of the inputs (random membership graphs are
A-01-T11)."""

from __future__ import annotations

import itertools
from typing import NamedTuple

import pytest

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

pytestmark = pytest.mark.django_db


class Case(NamedTuple):
    user_active: bool
    org_member: bool
    practice_member: bool
    wide_role: bool
    assigned: bool
    assignment_active: bool
    assigned_staff: bool

    @property
    def expected(self) -> bool:
        via_practice = (
            self.practice_member
            and self.assigned
            and self.assignment_active
            and (self.wide_role or self.assigned_staff)
        )
        return self.user_active and (self.org_member or via_practice)

    @property
    def valid(self) -> bool:
        # Only combinations that can exist: a role needs a membership, an assignment state
        # needs an assignment, and assigned staff must be a member of the assigned practice.
        if self.wide_role and not self.practice_member:
            return False
        if not self.assigned and self.assignment_active:
            return False
        return not (self.assigned_staff and not (self.practice_member and self.assigned))


CASES = [c for c in itertools.starmap(Case, itertools.product([False, True], repeat=7)) if c.valid]


def build(case: Case) -> tuple[User, Organisation]:
    user = User.objects.create_user("u@example.com", name="U", is_active=case.user_active)
    org = Organisation.objects.create(name="Maple Bakery")
    practice = Practice.objects.create(name="Profitex")
    if case.org_member:
        OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.SALES)
    member = None
    if case.practice_member:
        role = PracticeRole.PRACTICE_ADMIN if case.wide_role else PracticeRole.ACCOUNTANT
        member = PracticeMember.objects.create(practice=practice, user=user, role=role)
    if case.assigned:
        assignment = PracticeAssignment.objects.create(
            practice=practice, organisation=org, active=case.assignment_active
        )
        if case.assigned_staff:
            assert member is not None
            assignment.assigned_staff.add(member)
    return user, org


def test_truth_table_covers_every_valid_combination() -> None:
    assert len(CASES) == 52  # 2 (active) x 2 (org member) x 13 practice states
    assert {c.expected for c in CASES} == {True, False}


@pytest.mark.parametrize("case", CASES, ids=lambda c: "-".join(str(int(v)) for v in c))
def test_truth_table(case: Case) -> None:
    user, org = build(case)
    assert can_access(user, org) is case.expected
    assert list(accessible_organisations(user)) == ([org] if case.expected else [])


def test_practice_wide_roles() -> None:
    assert frozenset({"practice_admin"}) == PRACTICE_WIDE_ROLES


@pytest.mark.parametrize("role", [r for r in PracticeRole.values if r not in PRACTICE_WIDE_ROLES])
def test_other_practice_roles_need_a_staff_assignment(role: str) -> None:
    user = User.objects.create_user("s@example.com", name="S")
    org = Organisation.objects.create(name="Org")
    practice = Practice.objects.create(name="Firm")
    member = PracticeMember.objects.create(practice=practice, user=user, role=role)
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    assert not can_access(user, org)
    assignment.assigned_staff.add(member)
    assert can_access(user, org)


def test_anonymous_user_has_no_access() -> None:
    from django.contrib.auth.models import AnonymousUser

    org = Organisation.objects.create(name="Org")
    assert not can_access(AnonymousUser(), org)
    assert not accessible_organisations(None).exists()


def test_superuser_without_membership_has_no_access() -> None:
    admin = User.objects.create_superuser("root@example.com", "pw-not-used-here", name="Root")
    assert not can_access(admin, Organisation.objects.create(name="Org"))


def test_practice_access_is_limited_to_its_own_assignments() -> None:
    user = User.objects.create_user("admin@example.com", name="Admin")
    practice = Practice.objects.create(name="Firm")
    PracticeMember.objects.create(practice=practice, user=user, role=PracticeRole.PRACTICE_ADMIN)
    served, other = (Organisation.objects.create(name=n) for n in ("Served", "Other"))
    PracticeAssignment.objects.create(practice=practice, organisation=served)
    PracticeAssignment.objects.create(
        practice=Practice.objects.create(name="Another firm"), organisation=other
    )
    assert can_access(user, served)
    assert not can_access(user, other)


def test_staff_assignment_counts_only_for_that_organisation() -> None:
    user = User.objects.create_user("acc@example.com", name="Acc")
    practice = Practice.objects.create(name="Firm")
    member = PracticeMember.objects.create(
        practice=practice, user=user, role=PracticeRole.ACCOUNTANT
    )
    org_a, org_b = (Organisation.objects.create(name=n) for n in ("A", "B"))
    PracticeAssignment.objects.create(practice=practice, organisation=org_a).assigned_staff.add(
        member
    )
    PracticeAssignment.objects.create(practice=practice, organisation=org_b)
    assert can_access(user, org_a)
    assert not can_access(user, org_b)


def test_accessible_organisations_lists_each_once_across_all_paths() -> None:
    user = User.objects.create_user("all@example.com", name="All")
    practice = Practice.objects.create(name="Firm")
    member = PracticeMember.objects.create(
        practice=practice, user=user, role=PracticeRole.PRACTICE_ADMIN
    )
    own, served, both = (Organisation.objects.create(name=n) for n in ("Own", "Served", "Both"))
    Organisation.objects.create(name="Unrelated")
    OrganisationMember.objects.create(organisation=own, user=user, role=OrganisationRole.OWNER)
    PracticeAssignment.objects.create(practice=practice, organisation=served)
    OrganisationMember.objects.create(organisation=both, user=user, role=OrganisationRole.ADMIN)
    PracticeAssignment.objects.create(practice=practice, organisation=both).assigned_staff.add(
        member
    )
    result = list(accessible_organisations(user).order_by("name"))
    assert result == [both, own, served]


def test_access_is_not_cached() -> None:
    user = User.objects.create_user("gone@example.com", name="Gone")
    org = Organisation.objects.create(name="Org")
    practice = Practice.objects.create(name="Firm")
    member = PracticeMember.objects.create(
        practice=practice, user=user, role=PracticeRole.ACCOUNTANT
    )
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    assignment.assigned_staff.add(member)
    assert can_access(user, org)
    assignment.assigned_staff.remove(member)
    assert not can_access(user, org)
    assignment.assigned_staff.add(member)
    assignment.active = False
    assignment.save()
    assert not can_access(user, org)
