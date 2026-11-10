"""A-02-T08 — Invitation model: type, inviter, target practice/organisation, role, email, token
hash, expiry, accepted_at; at most one pending invitation per email address and target."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.accounts.models import User
from numo9.tenancy.models import (
    INVITATION_TTL,
    AssignmentRole,
    Invitation,
    InvitationKind,
    InvitationStatus,
    Organisation,
    OrganisationRole,
    Practice,
    PracticeRole,
    hash_token,
    new_token,
)


@pytest.fixture
def inviter(db: Any) -> User:
    return User.objects.create_user(email="dana@maple.ca", password=None, name="Dana Lee")


@pytest.fixture
def practice(db: Any) -> Practice:
    return Practice.objects.create(name="Maple Leaf Accounting")


@pytest.fixture
def organisation(db: Any) -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def invite(inviter: User, **fields: Any) -> Invitation:
    token, token_hash = new_token()
    fields.setdefault("email", "sam@refined.ca")
    fields.setdefault("expires_at", timezone.now() + INVITATION_TTL)
    return Invitation.objects.create(inviter=inviter, token_hash=token_hash, **fields)


def refused(**kwargs: Any) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        invite(**kwargs)


# ---- acceptance: unique pending per email + target ------------------------------------------


def test_one_pending_invitation_per_email_and_organisation(
    inviter: User, organisation: Organisation
) -> None:
    first = invite(
        inviter,
        kind=InvitationKind.ORGANISATION_USER,
        organisation=organisation,
        role=OrganisationRole.SALES,
    )
    # Same address (any casing), same organisation — even as a different type or role.
    refused(
        inviter=inviter,
        kind=InvitationKind.ORGANISATION_OWNER,
        organisation=organisation,
        role=OrganisationRole.OWNER,
        email="SAM@Refined.ca",
    )
    assert Invitation.objects.count() == 1
    assert first.status == InvitationStatus.PENDING


def test_one_pending_invitation_per_email_and_practice(inviter: User, practice: Practice) -> None:
    invite(
        inviter, kind=InvitationKind.PRACTICE_STAFF, practice=practice, role=PracticeRole.ACCOUNTANT
    )
    refused(
        inviter=inviter,
        kind=InvitationKind.PRACTICE_STAFF,
        practice=practice,
        role=PracticeRole.REVIEWER,
    )


def test_accepted_or_revoked_frees_the_slot(inviter: User, organisation: Organisation) -> None:
    kwargs = {
        "kind": InvitationKind.ORGANISATION_USER,
        "organisation": organisation,
        "role": OrganisationRole.SALES,
    }
    accepted = invite(inviter, **kwargs)
    accepted.accepted_at = timezone.now()
    accepted.save()
    revoked = invite(inviter, **kwargs)
    revoked.revoked_at = timezone.now()
    revoked.save()
    pending = invite(inviter, **kwargs)
    assert [accepted.status, revoked.status, pending.status] == ["accepted", "revoked", "pending"]


def test_same_email_for_other_targets_is_fine(
    inviter: User, practice: Practice, organisation: Organisation
) -> None:
    other = Organisation.objects.create(name="Other Ltd.")
    for target in (organisation, other):
        invite(
            inviter,
            kind=InvitationKind.ORGANISATION_USER,
            organisation=target,
            role=OrganisationRole.SALES,
        )
    invite(
        inviter, kind=InvitationKind.PRACTICE_STAFF, practice=practice, role=PracticeRole.ACCOUNTANT
    )
    assert Invitation.objects.filter(email="sam@refined.ca").count() == 3


# ---- type, target and role rules ------------------------------------------------------------


def test_each_flow_with_its_target_and_role(
    inviter: User, practice: Practice, organisation: Organisation
) -> None:
    flows: list[tuple[str, dict[str, Any], str]] = [
        (InvitationKind.PRACTICE_STAFF, {"practice": practice}, PracticeRole.PRACTICE_ADMIN),
        (InvitationKind.ORGANISATION_OWNER, {"organisation": organisation}, OrganisationRole.OWNER),
        (
            InvitationKind.ORGANISATION_USER,
            {"organisation": organisation},
            OrganisationRole.PAYROLL,
        ),
        (
            InvitationKind.ORGANISATION_ACCOUNTANT,
            {"organisation": organisation},
            AssignmentRole.TAX,
        ),
    ]
    for number, (kind, target, role) in enumerate(flows):
        made = invite(inviter, kind=kind, role=role, email=f"person{number}@x.ca", **target)
        assert made.target == next(iter(target.values()))


@pytest.mark.parametrize(
    ("kind", "target", "role"),
    [
        (InvitationKind.PRACTICE_STAFF, "organisation", PracticeRole.ACCOUNTANT),  # wrong target
        (InvitationKind.ORGANISATION_USER, "practice", OrganisationRole.SALES),
        (InvitationKind.ORGANISATION_USER, "both", OrganisationRole.SALES),
        (InvitationKind.ORGANISATION_USER, "none", OrganisationRole.SALES),
        (InvitationKind.PRACTICE_STAFF, "practice", OrganisationRole.OWNER),  # wrong role set
        (InvitationKind.ORGANISATION_OWNER, "organisation", OrganisationRole.ADMIN),
        (InvitationKind.ORGANISATION_USER, "organisation", PracticeRole.PRACTICE_ADMIN),
        (InvitationKind.ORGANISATION_ACCOUNTANT, "organisation", OrganisationRole.OWNER),
        ("superuser", "organisation", OrganisationRole.OWNER),  # unknown type
    ],
)
def test_wrong_target_or_role_is_refused(
    inviter: User,
    practice: Practice,
    organisation: Organisation,
    kind: str,
    target: str,
    role: str,
) -> None:
    options: dict[str, dict[str, Any]] = {
        "practice": {"practice": practice},
        "organisation": {"organisation": organisation},
        "both": {"practice": practice, "organisation": organisation},
        "none": {},
    }
    refused(inviter=inviter, kind=kind, role=role, **options[target])


def test_cannot_be_both_accepted_and_revoked(inviter: User, organisation: Organisation) -> None:
    invitation = invite(
        inviter,
        kind=InvitationKind.ORGANISATION_USER,
        organisation=organisation,
        role=OrganisationRole.SALES,
    )
    invitation.accepted_at = invitation.revoked_at = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        invitation.save()


# ---- token, email, expiry -------------------------------------------------------------------


def test_only_the_token_hash_is_stored(inviter: User, organisation: Organisation) -> None:
    token, token_hash = new_token()
    assert len(token) >= 43  # 256 bits, URL-safe
    assert token_hash == hash_token(token) and len(token_hash) == 64
    invitation = Invitation.objects.create(
        inviter=inviter,
        kind=InvitationKind.ORGANISATION_USER,
        organisation=organisation,
        role=OrganisationRole.SALES,
        email="sam@refined.ca",
        token_hash=token_hash,
        expires_at=timezone.now() + INVITATION_TTL,
    )
    assert token not in str(Invitation.objects.filter(pk=invitation.pk).values().get())
    assert Invitation.find_by_token(token) == invitation
    assert Invitation.find_by_token(token + "x") is None


def test_email_is_normalised(inviter: User, organisation: Organisation) -> None:
    invitation = invite(
        inviter,
        kind=InvitationKind.ORGANISATION_USER,
        organisation=organisation,
        role=OrganisationRole.SALES,
        email="  Sam@Refined.CA ",
    )
    assert invitation.email == "sam@refined.ca"


def test_expired_invitation_reports_expired(inviter: User, organisation: Organisation) -> None:
    assert timedelta(days=7) == INVITATION_TTL
    invitation = invite(
        inviter,
        kind=InvitationKind.ORGANISATION_USER,
        organisation=organisation,
        role=OrganisationRole.SALES,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert invitation.status == InvitationStatus.EXPIRED
    assert invitation.is_pending is False
