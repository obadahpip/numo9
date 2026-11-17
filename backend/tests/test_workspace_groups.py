"""V-02-T02 — ``OrgGroup`` tree (materialised path) + ``OrgGroupMembership``.

Acceptance: depth > 5 is rejected — creating a sixth level, moving a subtree so its deepest group
would be sixth, and writing depth 6 straight to the database are all refused. Also: trees per
practice; siblings unique by name (case and accents ignored), the same name allowed under another
parent; moves with the subtree (paths follow), refused into itself or a descendant or another
practice's group; organisations filed in several groups, only clients of the practice, once per
group; the practice's assignment switched off or deleted removes its memberships (other
practices' groups untouched).
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.tenancy.models import Organisation, Practice, PracticeAssignment
from numo9.workspace.groups import (
    GroupError,
    add_organisation,
    create_group,
    groups_of,
    move_group,
    remove_organisation,
    rename_group,
)
from numo9.workspace.models import OrgGroup, OrgGroupMembership

pytestmark = pytest.mark.django_db


@pytest.fixture
def practice() -> Practice:
    return Practice.objects.create(name="Abuodeh CPA")


def chain(practice: Practice, depth: int) -> list[OrgGroup]:
    groups: list[OrgGroup] = []
    parent = None
    for level in range(1, depth + 1):
        parent = create_group(practice, f"Level {level}", parent)
        groups.append(parent)
    return groups


def code(error: pytest.ExceptionInfo[GroupError]) -> str:
    return str(error.value.code)


def test_depth_over_five_is_rejected(practice: Practice) -> None:
    levels = chain(practice, 5)
    assert [g.depth for g in levels] == [1, 2, 3, 4, 5]
    with pytest.raises(GroupError) as too_deep:
        create_group(practice, "Level 6", levels[-1])
    assert code(too_deep) == "workspace.group.too_deep"
    branch = create_group(practice, "Branch")
    create_group(practice, "Leaf", create_group(practice, "Mid", branch))  # height 3
    with pytest.raises(GroupError) as moved:
        move_group(branch, levels[2])  # depth 3 + height 3 = 6
    assert code(moved) == "workspace.group.too_deep"
    move_group(branch, levels[1])  # 2 + 3 = 5: fine
    with pytest.raises(IntegrityError), transaction.atomic():
        OrgGroup.objects.filter(pk=levels[-1].pk).update(depth=6)


def test_names_unique_among_siblings(practice: Practice) -> None:
    toronto = create_group(practice, "Toronto office")
    with pytest.raises(GroupError) as taken:
        create_group(practice, "  toronto   OFFICE ")
    assert code(taken) == "workspace.group.name_taken"
    retail = create_group(practice, "Retail clients", toronto)
    montreal = create_group(practice, "Montréal office")
    create_group(practice, "Retail clients", montreal)  # another parent: fine
    with pytest.raises(GroupError):
        create_group(practice, "MONTREAL office")  # accents ignored
    with pytest.raises(GroupError):
        rename_group(retail, " ")
    assert rename_group(retail, "Retail").name == "Retail"
    other = Practice.objects.create(name="Other CPA")
    create_group(other, "Toronto office")  # another practice: fine


def test_moves_carry_the_subtree(practice: Practice) -> None:
    toronto = create_group(practice, "Toronto office")
    retail = create_group(practice, "Retail clients", toronto)
    grocery = create_group(practice, "Grocery", retail)
    montreal = create_group(practice, "Montréal office")
    move_group(retail, montreal)
    grocery.refresh_from_db()
    retail.refresh_from_db()
    assert OrgGroup.objects.get_parent(retail) == montreal
    assert OrgGroup.objects.get_parent(grocery) == retail
    assert grocery.depth == 3 and grocery.path.startswith(montreal.path)
    for target in (retail, grocery):
        with pytest.raises(GroupError) as loop:
            move_group(retail, target)
        assert code(loop) == "workspace.group.into_itself"
    other_root = create_group(Practice.objects.create(name="Other CPA"), "Theirs")
    with pytest.raises(GroupError) as foreign:
        move_group(retail, other_root)
    assert code(foreign) == "workspace.group.other_practice"
    move_group(retail, None)
    retail.refresh_from_db()
    assert retail.is_root() and [g.name for g in groups_of(practice)][:1]


def test_memberships(practice: Practice) -> None:
    maple = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    stranger = Organisation.objects.create(name="Not a client Inc.")
    PracticeAssignment.objects.create(practice=practice, organisation=maple)
    retail = create_group(practice, "Retail clients")
    payroll = create_group(practice, "Payroll clients")
    add_organisation(retail, maple)
    add_organisation(retail, maple)  # once per group
    add_organisation(payroll, maple)  # several groups
    assert OrgGroupMembership.objects.filter(organisation=maple).count() == 2
    with pytest.raises(GroupError) as outsider:
        add_organisation(retail, stranger)
    assert code(outsider) == "workspace.group.not_served"
    assert remove_organisation(payroll, maple) == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        OrgGroupMembership.objects.create(group=retail, organisation=maple)


def test_stopping_service_removes_memberships(practice: Practice) -> None:
    maple = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=maple)
    other = Practice.objects.create(name="Other CPA")
    PracticeAssignment.objects.create(practice=other, organisation=maple)
    mine, theirs = create_group(practice, "Mine"), create_group(other, "Theirs")
    add_organisation(mine, maple)
    add_organisation(theirs, maple)
    assignment.active = False
    assignment.save()
    assert list(OrgGroupMembership.objects.values_list("group__name", flat=True)) == ["Theirs"]
