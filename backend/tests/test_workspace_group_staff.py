"""V-02-T04 — ``GroupStaffAssignment`` (group, practice member, role).

Acceptance: unique per group + member — assigning again changes the role instead of adding a row,
and the database refuses a second row. Also: only members of the group's practice; roles from the
group role list (no practice admin: admins see every client already); a member can be in several
groups; deleting the group removes its staff rows; a member with group assignments can't be
deleted (practice records are never cascade-deleted).
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.accounts.models import User
from numo9.tenancy.models import Practice, PracticeMember
from numo9.workspace.groups import GroupError, assign_staff, create_group, unassign_staff
from numo9.workspace.models import GroupStaffAssignment, GroupStaffRole

pytestmark = pytest.mark.django_db


def member(practice: Practice, email: str, role: str = "accountant") -> PracticeMember:
    user = User.objects.create_user(email, password="x" * 12, name=email.split("@")[0])
    return PracticeMember.objects.create(practice=practice, user=user, role=role)


@pytest.fixture
def practice() -> Practice:
    return Practice.objects.create(name="Abuodeh CPA")


def test_unique_per_group_and_member(practice: Practice) -> None:
    retail = create_group(practice, "Retail clients")
    priya = member(practice, "priya@cpa.ca")
    first = assign_staff(retail, priya, "accountant")
    again = assign_staff(retail, priya, "reviewer")
    assert again.pk == first.pk and again.role == "reviewer"
    assert GroupStaffAssignment.objects.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        GroupStaffAssignment.objects.create(group=retail, practice_member=priya)
    payroll = create_group(practice, "Payroll clients")
    assign_staff(payroll, priya, "payroll_specialist")
    assert GroupStaffAssignment.objects.filter(practice_member=priya).count() == 2
    assert unassign_staff(payroll, priya) == 1


def test_practice_and_role_rules(practice: Practice) -> None:
    retail = create_group(practice, "Retail clients")
    outsider = member(Practice.objects.create(name="Other CPA"), "sam@other.ca")
    with pytest.raises(GroupError) as other:
        assign_staff(retail, outsider)
    assert other.value.code == "workspace.group.staff_other_practice"
    with pytest.raises(GroupError) as role:
        assign_staff(retail, member(practice, "dana@cpa.ca"), "practice_admin")
    assert role.value.code == "workspace.group.staff_role"
    assert "practice_admin" not in GroupStaffRole.values
    with pytest.raises(IntegrityError), transaction.atomic():
        GroupStaffAssignment.objects.create(
            group=retail, practice_member=member(practice, "x@cpa.ca"), role="owner"
        )


def test_group_deletion_and_member_protection(practice: Practice) -> None:
    retail = create_group(practice, "Retail clients")
    priya = member(practice, "priya@cpa.ca")
    assign_staff(retail, priya)
    with pytest.raises(IntegrityError), transaction.atomic():
        priya.delete()
    retail.delete()
    assert not GroupStaffAssignment.objects.exists()
