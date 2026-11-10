"""Invitation service (A-02-T09): create, send, resend, revoke and accept for the four flows.

- ``practice_staff`` — sent by a practice admin; accepting creates a ``PracticeMember`` with
  the role.
- ``organisation_owner`` — sent by a practice member who reaches the organisation through its
  practice assignment, while the organisation has no owner; accepting makes the invitee the
  owner (``OrganisationMember``); the practice stays assigned.
- ``organisation_user`` — sent by the organisation's owner or an admin; accepting creates an
  ``OrganisationMember`` with the role.
- ``organisation_accountant`` — sent by the organisation's owner or an admin; accepting assigns
  the accountant's practice (``PracticeAssignment``, role = what the practice does) with the
  accountant as assigned staff. An accountant without a practice gets a **pending practice**
  (``setup_pending``) they finish in practice onboarding.

Rules: links are single use and expire after 7 days; accepting is **bound to the invited email**
(signed in as another account → ``invitation.wrong_account``); an invitee who already has an
account is attached, never duplicated; one pending invitation per email and target — sending
again while one is waiting is refused (resend it instead); an expired one is replaced. The link
token exists only in the email: the database holds its SHA-256, and resending issues a new one.

Permission checks here are the Phase 0 baseline; A-03 replaces them with the permission catalogue
(``users.invite`` etc.) without changing this API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _

from numo9.accounts.models import User, normalise_email
from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError, api_error

from .access import PRACTICE_WIDE_ROLES
from .models import (
    INVITATION_TTL,
    Invitation,
    InvitationKind,
    InvitationStatus,
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
    hash_token,
    new_token,
)

RESEND_COOLDOWN = timedelta(seconds=60)
ORG_MANAGER_ROLES = frozenset({OrganisationRole.OWNER, OrganisationRole.ADMIN})
ORG_KINDS = frozenset(
    {
        InvitationKind.ORGANISATION_OWNER,
        InvitationKind.ORGANISATION_USER,
        InvitationKind.ORGANISATION_ACCOUNTANT,
    }
)


@dataclass(frozen=True)
class Issued:
    """A sent invitation and its link token (the token is not stored anywhere else)."""

    invitation: Invitation
    token: str

    @property
    def link(self) -> str:
        return invitation_link(self.token)


def invitation_link(token: str) -> str:
    return f"{settings.FRONTEND_URL}/invite/{token}"


# ---- who may send ---------------------------------------------------------------------------


def _is_practice_admin(user: User, practice: Practice) -> bool:
    return PracticeMember.objects.filter(
        practice=practice, user=user, role=PracticeRole.PRACTICE_ADMIN
    ).exists()


def _manages_organisation(user: User, organisation: Organisation) -> bool:
    return OrganisationMember.objects.filter(
        organisation=organisation, user=user, role__in=ORG_MANAGER_ROLES
    ).exists()


def _serves_organisation(user: User, organisation: Organisation) -> bool:
    """The user reaches the organisation through an active assignment of their practice."""
    for assignment in PracticeAssignment.objects.filter(organisation=organisation, active=True):
        member = PracticeMember.objects.filter(practice=assignment.practice, user=user).first()
        if member is None:
            continue
        if (
            member.role in PRACTICE_WIDE_ROLES
            or assignment.assigned_staff.filter(pk=member.pk).exists()
        ):
            return True
    return False


def can_invite(user: User, kind: str, target: Practice | Organisation) -> bool:
    if not user.is_active:
        return False
    if kind == InvitationKind.PRACTICE_STAFF:
        return isinstance(target, Practice) and _is_practice_admin(user, target)
    if not isinstance(target, Organisation):
        return False
    if kind == InvitationKind.ORGANISATION_OWNER:
        return _serves_organisation(user, target)
    return _manages_organisation(user, target)


def can_manage(user: User, invitation: Invitation) -> bool:
    """Resend/revoke: the sender, or anyone who may send that kind to that target."""
    return invitation.inviter_id == user.pk or can_invite(user, invitation.kind, invitation.target)


# ---- create / send / resend / revoke ----------------------------------------------------------


def _already_member(kind: str, target: Practice | Organisation, email: str) -> bool:
    if kind == InvitationKind.PRACTICE_STAFF:
        return PracticeMember.objects.filter(practice_id=target.pk, user__email=email).exists()
    if kind == InvitationKind.ORGANISATION_ACCOUNTANT:
        return PracticeAssignment.objects.filter(
            organisation_id=target.pk, active=True, assigned_staff__user__email=email
        ).exists()
    return OrganisationMember.objects.filter(organisation_id=target.pk, user__email=email).exists()


def _target_kwargs(kind: str, target: Practice | Organisation) -> dict[str, Any]:
    return (
        {"practice": target} if kind == InvitationKind.PRACTICE_STAFF else {"organisation": target}
    )


def create(
    *,
    inviter: User,
    kind: str,
    email: str,
    role: str,
    target: Practice | Organisation,
    send: bool = True,
) -> Issued:
    """Create (and by default email) an invitation. Raises ``CatalogueError`` on a refused one."""
    email = normalise_email(email)
    if not can_invite(inviter, kind, target):
        raise api_error(errors.INVITATION_NOT_ALLOWED)
    if kind == InvitationKind.ORGANISATION_OWNER:
        role = OrganisationRole.OWNER
        if OrganisationMember.objects.filter(
            organisation_id=target.pk, role=OrganisationRole.OWNER
        ).exists():
            raise api_error(errors.INVITATION_HAS_OWNER)
    if _already_member(kind, target, email):
        raise api_error(errors.INVITATION_ALREADY_MEMBER, email=email)

    target_kwargs = _target_kwargs(kind, target)
    with transaction.atomic():
        waiting = (
            Invitation.objects.select_for_update()
            .filter(email=email, accepted_at__isnull=True, revoked_at__isnull=True, **target_kwargs)
            .first()
        )
        if waiting is not None:
            if waiting.status == InvitationStatus.PENDING:
                raise api_error(errors.INVITATION_ALREADY_PENDING, email=email)
            waiting.revoked_at = timezone.now()  # expired: replaced by the new one
            waiting.save(update_fields=["revoked_at", "updated_at"])
        token, token_hash = new_token()
        try:
            with transaction.atomic():
                invitation = Invitation.objects.create(
                    kind=kind,
                    inviter=inviter,
                    role=role,
                    email=email,
                    token_hash=token_hash,
                    expires_at=timezone.now() + INVITATION_TTL,
                    **target_kwargs,
                )
        except IntegrityError as error:  # a concurrent request created the same one
            raise api_error(errors.INVITATION_ALREADY_PENDING, email=email) from error
    issued = Issued(invitation, token)
    if send:
        deliver(issued)
    return issued


def deliver(issued: Issued) -> None:
    """Email the link and record the send."""
    invitation = issued.invitation
    target = invitation.target
    locale = getattr(target, "locale", None) or invitation.inviter.locale
    with translation.override(locale):
        subject = _("%(inviter)s invited you to %(target)s on Numo9") % {
            "inviter": invitation.inviter.name or invitation.inviter.email,
            "target": target.name,
        }
        body = _(
            "%(inviter)s invited you to join %(target)s on Numo9.\n\n"
            "Accept the invitation:\n%(link)s\n\n"
            "The link works once and expires on %(date)s. If you weren't expecting this "
            "invitation, you can ignore this email."
        ) % {
            "inviter": invitation.inviter.name or invitation.inviter.email,
            "target": target.name,
            "link": issued.link,
            "date": formats.date_format(timezone.localtime(invitation.expires_at), "DATE_FORMAT"),
        }
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [invitation.email])
    invitation.send_count += 1
    invitation.last_sent_at = timezone.now()
    invitation.save(update_fields=["send_count", "last_sent_at", "updated_at"])


def resend(invitation: Invitation, *, by: User) -> Issued:
    """Send a pending invitation again with a new link (the old link stops working) and a
    fresh 7-day expiry; an expired invitation can be resent too."""
    if not can_manage(by, invitation):
        raise api_error(errors.INVITATION_NOT_ALLOWED)
    with transaction.atomic():
        invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
        if invitation.accepted_at is not None or invitation.revoked_at is not None:
            raise api_error(errors.INVITATION_NOT_PENDING)
        if invitation.last_sent_at and timezone.now() - invitation.last_sent_at < RESEND_COOLDOWN:
            raise api_error(errors.INVITATION_RESEND_TOO_SOON)
        token, invitation.token_hash = new_token()
        invitation.expires_at = timezone.now() + INVITATION_TTL
        invitation.save(update_fields=["token_hash", "expires_at", "updated_at"])
    issued = Issued(invitation, token)
    deliver(issued)
    return issued


def revoke(invitation: Invitation, *, by: User) -> Invitation:
    if not can_manage(by, invitation):
        raise api_error(errors.INVITATION_NOT_ALLOWED)
    with transaction.atomic():
        invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
        if invitation.accepted_at is not None or invitation.revoked_at is not None:
            raise api_error(errors.INVITATION_NOT_PENDING)
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at", "updated_at"])
    return invitation


# ---- accept ---------------------------------------------------------------------------------


def _usable(invitation: Invitation | None) -> Invitation:
    if invitation is None:
        raise api_error(errors.INVITATION_INVALID)
    status = invitation.status
    if status == InvitationStatus.ACCEPTED:
        raise api_error(errors.INVITATION_USED)
    if status == InvitationStatus.REVOKED:
        raise api_error(errors.INVITATION_REVOKED)
    if status == InvitationStatus.EXPIRED:
        date = formats.date_format(timezone.localtime(invitation.expires_at), "DATE_FORMAT")
        raise api_error(errors.INVITATION_EXPIRED, date=date)
    return invitation


def lookup(token: str) -> Invitation:
    """The usable invitation for a link token, or a ``CatalogueError`` naming why not."""
    return _usable(Invitation.find_by_token(token))


def _accountant_practice(user: User, practice: Practice | None) -> tuple[Practice, PracticeMember]:
    memberships = list(PracticeMember.objects.filter(user=user).select_related("practice"))
    if practice is not None:
        member = next((m for m in memberships if m.practice_id == practice.pk), None)
        if member is None:
            raise api_error(errors.UNKNOWN_PRACTICE)
        return member.practice, member
    if len(memberships) == 1:
        return memberships[0].practice, memberships[0]
    if memberships:
        raise api_error(errors.INVITATION_CHOOSE_PRACTICE)
    # No practice yet: a pending one, finished in practice onboarding (name, Province).
    pending = Practice.objects.create(name=user.name or user.email, setup_pending=True)
    member = PracticeMember.objects.create(
        practice=pending, user=user, role=PracticeRole.PRACTICE_ADMIN
    )
    return pending, member


def accept(token: str, user: User, *, practice: Practice | None = None) -> Invitation:
    """Accept for the signed-in ``user``; ``practice`` picks which of the accountant's practices
    serves the organisation when they belong to several (``organisation_accountant`` only)."""
    with transaction.atomic():
        found = Invitation.objects.select_for_update().filter(token_hash=hash_token(token))
        invitation = _usable(found.first())
        if normalise_email(user.email) != invitation.email:
            raise api_error(errors.INVITATION_WRONG_ACCOUNT, email=invitation.email)

        kind = invitation.kind
        if kind == InvitationKind.PRACTICE_STAFF:
            PracticeMember.objects.get_or_create(
                practice=invitation.practice, user=user, defaults={"role": invitation.role}
            )
        elif kind in (InvitationKind.ORGANISATION_OWNER, InvitationKind.ORGANISATION_USER):
            org_member, created = OrganisationMember.objects.get_or_create(
                organisation=invitation.organisation, user=user, defaults={"role": invitation.role}
            )
            if not created and kind == InvitationKind.ORGANISATION_OWNER:
                org_member.role = OrganisationRole.OWNER
                org_member.save(update_fields=["role"])
        else:  # organisation_accountant
            own_practice, member = _accountant_practice(user, practice)
            assignment, created = PracticeAssignment.objects.get_or_create(
                practice=own_practice,
                organisation=invitation.organisation,
                defaults={"role": invitation.role, "active": True},
            )
            if not created and (not assignment.active or assignment.role != invitation.role):
                assignment.active = True
                assignment.role = invitation.role
                assignment.save(update_fields=["active", "role", "updated_at"])
            assignment.assigned_staff.add(member)

        invitation.accepted_at = timezone.now()
        invitation.accepted_by = user
        invitation.save(update_fields=["accepted_at", "accepted_by", "updated_at"])
    return invitation


__all__ = [
    "CatalogueError",
    "Issued",
    "accept",
    "can_invite",
    "can_manage",
    "create",
    "deliver",
    "invitation_link",
    "lookup",
    "resend",
    "revoke",
]
