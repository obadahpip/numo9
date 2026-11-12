"""Audit hooks for sign-in, 2FA changes and invitations (A-02-T14).

Acceptance: the events are visible in the audit log — sign-in success and failure, 2FA changes
(platform events about the person) and every invitation step (in the organisation's or the
practice's log), each with the actor, the record and where it came from.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from django.test import Client, override_settings

from numo9.accounts.models import User
from numo9.audit.models import ActorKind, AuditEvent
from numo9.tenancy import invitations as service
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    InvitationKind,
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeMember,
    PracticeRole,
)
from tests.auth_helpers import API, PASSWORD, login, make_user, post
from tests.test_auth_totp import enrol, reauthenticate, totp

pytestmark = pytest.mark.django_db

UA = "Mozilla/5.0 (Numo9 test)"
WRONG = "not the password 1"  # noqa: S105 — test credential


def platform(action: str) -> list[AuditEvent]:
    return list(AuditEvent.platform_events.filter(action=action).order_by("id"))


def client() -> Client:
    return Client(HTTP_USER_AGENT=UA, REMOTE_ADDR="198.51.100.20")


# ---- sign-in -----------------------------------------------------------------------------------


def test_successful_sign_in_is_recorded_for_the_person() -> None:
    user = make_user()
    assert login(client()).status_code == 200
    (event,) = platform("auth.login.succeeded")
    assert event.organisation is None
    assert event.actor_kind == ActorKind.USER and event.actor_user == user
    assert event.object_type == "accounts.User" and event.object_id == str(user.public_id)
    assert event.object_label == "dana@maple.ca"
    assert event.ip == "198.51.100.20" and event.user_agent == UA


def test_wrong_password_is_recorded_without_the_password() -> None:
    user = make_user()
    assert login(client(), password=WRONG).status_code == 401
    (event,) = platform("auth.login.failed")
    assert event.actor_user == user and event.object_id == str(user.public_id)
    assert event.meta == {"email": "dana@maple.ca", "reason": "invalid_credentials"}
    assert WRONG not in str(event.meta) + str(event.changes)


def test_failed_sign_in_for_an_unknown_address_is_recorded_too() -> None:
    assert login(client(), email="Nobody@Example.com").status_code == 401
    (event,) = platform("auth.login.failed")
    assert event.actor_user is None and event.object_id == ""
    assert event.object_label == "nobody@example.com" and event.actor_label == "nobody@example.com"


@override_settings(NUMO9_LOGIN_LOCKOUT_THRESHOLD=2)
def test_locked_address_attempt_is_recorded() -> None:
    make_user()
    browser = client()
    for _ in range(2):
        login(browser, password=WRONG)
    assert login(browser).status_code in (400, 429)
    (event,) = platform("auth.login.locked")
    assert event.meta["reason"] == "locked"


def test_sign_out_is_recorded() -> None:
    make_user()
    browser = client()
    login(browser)
    assert browser.delete(f"{API}/auth/session").status_code == 401
    assert len(platform("auth.logout")) == 1


# ---- two-step verification ---------------------------------------------------------------------


# allauth's change notification emails need the request, gone once the test client returns.
@override_settings(ACCOUNT_EMAIL_NOTIFICATIONS=False)
def test_2fa_enrolment_regeneration_and_removal_are_recorded(
    django_capture_on_commit_callbacks: Any,
) -> None:
    # allauth sends its 2FA signals once the change has committed.
    user = make_user()
    browser = client()
    login(browser)
    with django_capture_on_commit_callbacks(execute=True):
        enrol(browser)
    assert [e.meta for e in platform("auth.2fa.enabled")] == [{"type": "totp"}]
    assert len(platform("auth.recovery_codes.created")) == 1
    reauthenticate(browser)
    with django_capture_on_commit_callbacks(execute=True):
        regenerated = post(browser, "/account/authenticators/recovery-codes", {})
    assert regenerated.status_code == 200
    assert len(platform("auth.recovery_codes.regenerated")) == 1
    reauthenticate(browser)
    with django_capture_on_commit_callbacks(execute=True):
        removed = browser.delete(
            f"{API}/account/authenticators/totp", content_type="application/json"
        )
    assert removed.status_code == 200, removed.json()
    (disabled,) = platform("auth.2fa.disabled")
    assert disabled.actor_user == user and disabled.object_id == str(user.public_id)


def test_wrong_2fa_code_at_sign_in_is_recorded() -> None:
    make_user()
    first = client()
    login(first)
    secret, _ = enrol(first)
    second = client()
    login(second)
    assert (
        post(second, "/auth/2fa/authenticate", {"code": totp(secret, steps=4)}).status_code == 400
    )
    assert len(platform("auth.2fa.failed")) == 1


# ---- invitations -------------------------------------------------------------------------------


@pytest.fixture
def owner() -> User:
    return make_user(email="sam@refined.ca", name="Sam Roy")


@pytest.fixture
def organisation(owner: User) -> Organisation:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    OrganisationMember.objects.create(organisation=org, user=owner, role=OrganisationRole.OWNER)
    return org


def org_events(org: Organisation, prefix: str = "tenancy.invitation.") -> list[AuditEvent]:
    with org_context(org):
        return list(AuditEvent.objects.filter(action__startswith=prefix).order_by("id"))


def test_invitation_steps_are_in_the_organisation_log(
    owner: User, organisation: Organisation
) -> None:
    issued = service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_USER,
        email="Lee@Refined.ca",
        role=OrganisationRole.SALES,
        target=organisation,
    )
    service.resend(_aged(issued.invitation), by=owner)
    invitee = make_user(email="lee@refined.ca", name="Lee Chan")
    token = _link_token(str(mail.outbox[-1].body))
    service.accept(token, invitee)

    created, resent, accepted = org_events(organisation)
    assert created.action == "tenancy.invitation.created" and created.actor_user == owner
    assert created.object_type == "tenancy.Invitation"
    assert created.object_id == str(issued.invitation.public_id)
    assert created.object_label == "lee@refined.ca — Refined Interiors Inc."
    assert created.changes["email"] == [None, "lee@refined.ca"]
    assert created.changes["role"] == [None, "sales"]
    assert created.meta["kind"] == InvitationKind.ORGANISATION_USER
    assert resent.action == "tenancy.invitation.resent" and "expires_at" in resent.changes
    assert accepted.action == "tenancy.invitation.accepted" and accepted.actor_user == invitee
    assert accepted.changes == {"status": ["pending", "accepted"]}
    assert "token" not in str(created.changes) + str(created.meta)


def test_revoked_invitation_is_recorded(owner: User, organisation: Organisation) -> None:
    issued = service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_USER,
        email="lee@refined.ca",
        role=OrganisationRole.SALES,
        target=organisation,
        send=False,
    )
    service.revoke(issued.invitation, by=owner)
    revoked = org_events(organisation)[-1]
    assert revoked.action == "tenancy.invitation.revoked"
    assert revoked.changes == {"status": ["pending", "revoked"]}


def test_practice_staff_invitation_is_a_practice_event() -> None:
    admin = make_user(email="dana@maple.ca", name="Dana Lee")
    practice = Practice.objects.create(name="Maple Leaf Accounting")
    PracticeMember.objects.create(practice=practice, user=admin, role=PracticeRole.PRACTICE_ADMIN)
    service.create(
        inviter=admin,
        kind=InvitationKind.PRACTICE_STAFF,
        email="kim@maple.ca",
        role=PracticeRole.ACCOUNTANT,
        target=practice,
        send=False,
    )
    (event,) = platform("tenancy.invitation.created")
    assert event.organisation is None and event.practice == practice


def test_failed_invitation_leaves_no_event(owner: User, organisation: Organisation) -> None:
    stranger = make_user(email="x@example.com", name="X")
    with pytest.raises(service.CatalogueError):
        service.create(
            inviter=stranger,
            kind=InvitationKind.ORGANISATION_USER,
            email="lee@refined.ca",
            role=OrganisationRole.SALES,
            target=organisation,
        )
    assert org_events(organisation) == []


# ---- helpers -----------------------------------------------------------------------------------


def _aged(invitation: Any) -> Any:
    """Past the resend cool-down (the invitation was just sent)."""
    from datetime import timedelta

    from django.utils import timezone

    from numo9.tenancy.models import Invitation

    Invitation.objects.filter(pk=invitation.pk).update(
        last_sent_at=timezone.now() - timedelta(hours=1)
    )
    invitation.refresh_from_db()
    return invitation


def _link_token(body: str) -> str:
    link = next(line for line in body.splitlines() if "/invite/" in line)
    return link.rsplit("/invite/", 1)[1].strip()


assert PASSWORD  # shared credential used by the helpers
