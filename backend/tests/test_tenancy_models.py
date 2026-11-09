"""A-01-T01 — tenancy models: Practice, PracticeMember, Organisation, OrganisationMember,
PracticeAssignment (constraints, defaults, enums, assigned-staff rule, no cascades)."""

from __future__ import annotations

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from numo9.accounts.models import User
from numo9.tenancy.models import (
    DEFAULT_TIME_ZONE,
    AssignmentRole,
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)

pytestmark = pytest.mark.django_db


def make_user(email: str) -> User:
    return User.objects.create_user(email, name=email.split("@")[0])


@pytest.fixture
def practice() -> Practice:
    return Practice.objects.create(name="Profitex")


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery")


def test_organisation_defaults(org: Organisation) -> None:
    assert org.status == OrganisationStatus.TRIAL
    assert org.time_zone == DEFAULT_TIME_ZONE == "America/Toronto"
    assert isinstance(org.public_id, uuid.UUID)
    other = Organisation.objects.create(name="Other")
    assert other.public_id != org.public_id


def test_practice_has_public_id(practice: Practice) -> None:
    assert isinstance(practice.public_id, uuid.UUID)
    assert str(practice) == "Profitex"


def test_organisation_statuses_are_the_six_life_cycle_states() -> None:
    assert OrganisationStatus.values == [
        "demo",
        "trial",
        "active",
        "grace",
        "read_only",
        "cancelled",
    ]
    for status in OrganisationStatus.values:
        organisation = Organisation(name=f"Org {status}", status=status)
        organisation.full_clean()
        organisation.save()


def test_invalid_status_rejected_by_validation_and_database(org: Organisation) -> None:
    org.status = "suspended"
    with pytest.raises(ValidationError) as exc:
        org.full_clean()
    assert "status" in exc.value.message_dict
    with pytest.raises(IntegrityError), transaction.atomic():
        Organisation.objects.filter(pk=org.pk).update(status="suspended")


@pytest.mark.parametrize("tz", ["America/Vancouver", "America/Halifax", "America/St_Johns"])
def test_valid_time_zones_accepted(org: Organisation, tz: str) -> None:
    org.time_zone = tz
    org.full_clean()


@pytest.mark.parametrize("tz", ["Mars/Olympus", "EST5", "", "america/toronto "])
def test_invalid_time_zone_rejected(org: Organisation, tz: str) -> None:
    org.time_zone = tz
    with pytest.raises(ValidationError) as exc:
        org.full_clean()
    assert "time_zone" in exc.value.message_dict


def test_practice_assignment_unique_per_practice_and_organisation(
    practice: Practice, org: Organisation
) -> None:
    PracticeAssignment.objects.create(practice=practice, organisation=org)
    with pytest.raises(IntegrityError), transaction.atomic():
        PracticeAssignment.objects.create(
            practice=practice, organisation=org, role=AssignmentRole.TAX
        )


def test_organisation_can_have_zero_one_or_several_practices(org: Organisation) -> None:
    assert org.practice_assignments.count() == 0
    bookkeeper = Practice.objects.create(name="Bookkeeper Co")
    tax = Practice.objects.create(name="Tax Co")
    PracticeAssignment.objects.create(
        practice=bookkeeper, organisation=org, role=AssignmentRole.BOOKKEEPING
    )
    PracticeAssignment.objects.create(practice=tax, organisation=org, role=AssignmentRole.TAX)
    assert org.practice_assignments.count() == 2


def test_practice_can_serve_many_organisations(practice: Practice) -> None:
    for i in range(3):
        PracticeAssignment.objects.create(
            practice=practice, organisation=Organisation.objects.create(name=f"Org {i}")
        )
    assert practice.assignments.count() == 3


def test_assignment_defaults(practice: Practice, org: Organisation) -> None:
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    assert assignment.active is True
    assert assignment.role == AssignmentRole.FULL_SERVICE
    assert assignment.assigned_staff.count() == 0


def test_practice_member_unique_per_practice(practice: Practice) -> None:
    user = make_user("acc@example.com")
    PracticeMember.objects.create(practice=practice, user=user, role=PracticeRole.ACCOUNTANT)
    with pytest.raises(IntegrityError), transaction.atomic():
        PracticeMember.objects.create(practice=practice, user=user, role=PracticeRole.REVIEWER)


def test_organisation_member_unique_per_organisation(org: Organisation) -> None:
    user = make_user("owner@example.com")
    OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.OWNER)
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.SALES)


def test_user_can_be_practice_member_and_organisation_owner(
    practice: Practice, org: Organisation
) -> None:
    user = make_user("both@example.com")
    PracticeMember.objects.create(practice=practice, user=user, role=PracticeRole.PRACTICE_ADMIN)
    OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.OWNER)
    assert user.practice_memberships.count() == 1
    assert user.organisation_memberships.count() == 1


def test_practice_member_role_outside_catalogue_rejected(practice: Practice) -> None:
    member = PracticeMember.objects.create(
        practice=practice, user=make_user("r@example.com"), role=PracticeRole.ACCOUNTANT
    )
    member.role = OrganisationRole.OWNER  # an organisation role is not a practice role
    with pytest.raises(ValidationError):
        member.full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        PracticeMember.objects.filter(pk=member.pk).update(role="owner")


def test_organisation_member_role_outside_catalogue_rejected(org: Organisation) -> None:
    member = OrganisationMember.objects.create(
        organisation=org, user=make_user("r@example.com"), role=OrganisationRole.SALES
    )
    member.role = PracticeRole.PRACTICE_ADMIN  # a practice role is not an organisation role
    with pytest.raises(ValidationError):
        member.full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganisationMember.objects.filter(pk=member.pk).update(role="practice_admin")


def test_assignment_role_outside_catalogue_rejected(practice: Practice, org: Organisation) -> None:
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    with pytest.raises(IntegrityError), transaction.atomic():
        PracticeAssignment.objects.filter(pk=assignment.pk).update(role="audit")


def test_member_role_is_required(practice: Practice) -> None:
    member = PracticeMember(practice=practice, user=make_user("n@example.com"))
    with pytest.raises(ValidationError) as exc:
        member.full_clean()
    assert "role" in exc.value.message_dict


def test_assigned_staff_from_the_same_practice(practice: Practice, org: Organisation) -> None:
    member = PracticeMember.objects.create(
        practice=practice, user=make_user("s@example.com"), role=PracticeRole.ACCOUNTANT
    )
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    assignment.assigned_staff.add(member)
    assert list(assignment.assigned_staff.all()) == [member]
    assert list(member.assignments.all()) == [assignment]


def test_staff_of_another_practice_cannot_be_assigned(
    practice: Practice, org: Organisation
) -> None:
    outsider = PracticeMember.objects.create(
        practice=Practice.objects.create(name="Other firm"),
        user=make_user("out@example.com"),
        role=PracticeRole.ACCOUNTANT,
    )
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    with pytest.raises(ValidationError), transaction.atomic():
        assignment.assigned_staff.add(outsider)
    with pytest.raises(ValidationError), transaction.atomic():
        assignment.assigned_staff.set([outsider])
    with pytest.raises(ValidationError), transaction.atomic():
        outsider.assignments.add(assignment)  # reverse side
    assert assignment.assigned_staff.count() == 0


def test_deactivating_assignment_keeps_its_history(practice: Practice, org: Organisation) -> None:
    member = PracticeMember.objects.create(
        practice=practice, user=make_user("h@example.com"), role=PracticeRole.ACCOUNTANT
    )
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    assignment.assigned_staff.add(member)
    assignment.active = False
    assignment.save()
    assignment.refresh_from_db()
    assert assignment.active is False
    assert assignment.assigned_staff.count() == 1


def test_no_cascade_deletes(practice: Practice, org: Organisation) -> None:
    user = make_user("keep@example.com")
    OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.OWNER)
    PracticeMember.objects.create(practice=practice, user=user, role=PracticeRole.ACCOUNTANT)
    PracticeAssignment.objects.create(practice=practice, organisation=org)
    for obj in (org, practice, user):
        with pytest.raises(ProtectedError):
            obj.delete()
