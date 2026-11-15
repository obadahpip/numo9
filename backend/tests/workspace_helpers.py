"""Shared helpers for the accountant workspace tests (V-01): a practice, its staff and clients."""

from __future__ import annotations

from typing import Any

from numo9.accounts.models import User
from numo9.orgsettings.models import OrganisationSettings, RegistrationType, TaxRegistration
from numo9.orgsettings.validators import luhn_valid
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)

_counter = {"n": 0}


def user(email: str, name: str = "", **fields: Any) -> User:
    return User.objects.create_user(email=email, password=None, name=name or email, **fields)


def practice(name: str = "Abuodeh CPA", admin: User | None = None) -> Practice:
    created = Practice.objects.create(name=name)
    if admin is not None:
        PracticeMember.objects.create(
            practice=created, user=admin, role=PracticeRole.PRACTICE_ADMIN
        )
    return created


def member(practice: Practice, person: User, role: str = PracticeRole.ACCOUNTANT) -> PracticeMember:
    return PracticeMember.objects.create(practice=practice, user=person, role=role)


def client_org(
    practice: Practice | None,
    name: str,
    *,
    staff: list[PracticeMember] | None = None,
    status: str = OrganisationStatus.ACTIVE,
    active: bool = True,
    settings: dict[str, Any] | None = None,
    bn: str = "",
    owner: User | None = None,
) -> Organisation:
    """An organisation, assigned to ``practice`` (with ``staff``), with optional settings, a BN
    registration and an owner."""
    organisation = Organisation.objects.create(name=name, status=status)
    if settings is not None:
        with org_context(organisation):
            OrganisationSettings(organisation=organisation, display_name=name, **settings).save()
    if bn:
        with org_context(organisation):
            TaxRegistration(organisation=organisation, type=RegistrationType.BN, number=bn).save()
    if owner is not None:
        OrganisationMember.objects.create(
            organisation=organisation, user=owner, role=OrganisationRole.OWNER
        )
    if practice is not None:
        assignment = PracticeAssignment.objects.create(
            practice=practice, organisation=organisation, active=active
        )
        for item in staff or []:
            assignment.assigned_staff.add(item)
    return organisation


def valid_bn(seed: int) -> str:
    """The Business Number made of ``seed`` (8 digits) and its Luhn check digit."""
    body = f"{seed:08d}"
    return next(body + d for d in "0123456789" if luhn_valid(body + d))
