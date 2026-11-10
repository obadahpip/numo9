"""A-02-T09 — invitation service and API: create/send/resend/revoke/accept for the four flows;
accept binds the invited email; owner → accountant creates a PracticeAssignment (or a pending
practice when the accountant has none)."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.i18n.errors import CatalogueError
from numo9.tenancy import invitations as service
from numo9.tenancy.access import can_access
from numo9.tenancy.models import (
    AssignmentRole,
    Invitation,
    InvitationKind,
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)
from tests.auth_helpers import login, make_user

pytestmark = pytest.mark.django_db


def code_of(excinfo: pytest.ExceptionInfo[CatalogueError]) -> str:
    return str(excinfo.value.get_codes())


@pytest.fixture
def owner() -> User:
    return make_user(email="sam@refined.ca", name="Sam Roy")


@pytest.fixture
def organisation(owner: User) -> Organisation:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    OrganisationMember.objects.create(organisation=org, user=owner, role=OrganisationRole.OWNER)
    return org


@pytest.fixture
def practice_admin() -> User:
    return make_user(email="dana@maple.ca", name="Dana Lee")


@pytest.fixture
def practice(practice_admin: User) -> Practice:
    p = Practice.objects.create(name="Maple Leaf Accounting")
    PracticeMember.objects.create(practice=p, user=practice_admin, role=PracticeRole.PRACTICE_ADMIN)
    return p


def link_token(message: Any) -> str:
    match = re.search(r"/invite/(\S+)", str(message.body))
    assert match, message.body
    return match.group(1)


# ---- acceptance: owner invites accountant → assigned ----------------------------------------


def test_owner_invites_accountant_who_becomes_assigned(
    owner: User, organisation: Organisation, practice: Practice, practice_admin: User
) -> None:
    issued = service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_ACCOUNTANT,
        email="DANA@maple.ca",
        role=AssignmentRole.BOOKKEEPING,
        target=organisation,
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["dana@maple.ca"]
    token = link_token(mail.outbox[0])
    assert token == issued.token
    assert not can_access(practice_admin, organisation)

    invitation = service.accept(token, practice_admin)

    assignment = PracticeAssignment.objects.get(practice=practice, organisation=organisation)
    assert assignment.active is True
    assert assignment.role == AssignmentRole.BOOKKEEPING
    member = PracticeMember.objects.get(practice=practice, user=practice_admin)
    assert list(assignment.assigned_staff.all()) == [member]
    assert can_access(practice_admin, organisation)
    assert invitation.accepted_by == practice_admin
    assert invitation.status == "accepted"


def test_accountant_without_a_practice_gets_a_pending_one(
    owner: User, organisation: Organisation
) -> None:
    accountant = make_user(email="lee@solo.ca", name="Lee Chen")
    issued = service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_ACCOUNTANT,
        email="lee@solo.ca",
        role=AssignmentRole.TAX,
        target=organisation,
    )
    service.accept(issued.token, accountant)
    member = PracticeMember.objects.get(user=accountant)
    assert member.role == PracticeRole.PRACTICE_ADMIN
    assert member.practice.setup_pending is True
    assert member.practice.name == "Lee Chen"
    assert PracticeAssignment.objects.get(practice=member.practice).organisation == organisation
    assert can_access(accountant, organisation)


def test_accountant_in_several_practices_chooses_one(
    owner: User, organisation: Organisation, practice: Practice, practice_admin: User
) -> None:
    second = Practice.objects.create(name="Second Practice")
    PracticeMember.objects.create(
        practice=second, user=practice_admin, role=PracticeRole.ACCOUNTANT
    )
    issued = service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_ACCOUNTANT,
        email="dana@maple.ca",
        role=AssignmentRole.FULL_SERVICE,
        target=organisation,
    )
    with pytest.raises(CatalogueError) as excinfo:
        service.accept(issued.token, practice_admin)
    assert code_of(excinfo) == "invitation.choose_practice"
    service.accept(issued.token, practice_admin, practice=second)
    assert PracticeAssignment.objects.get(organisation=organisation).practice == second


def test_reactivates_a_previous_assignment(
    owner: User, organisation: Organisation, practice: Practice, practice_admin: User
) -> None:
    old = PracticeAssignment.objects.create(
        practice=practice, organisation=organisation, role=AssignmentRole.TAX, active=False
    )
    issued = service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_ACCOUNTANT,
        email="dana@maple.ca",
        role=AssignmentRole.PAYROLL,
        target=organisation,
    )
    service.accept(issued.token, practice_admin)
    old.refresh_from_db()
    assert (old.active, old.role) == (True, AssignmentRole.PAYROLL)
    assert PracticeAssignment.objects.count() == 1


# ---- the other three flows ------------------------------------------------------------------


def test_practice_invites_staff(practice: Practice, practice_admin: User) -> None:
    issued = service.create(
        inviter=practice_admin,
        kind=InvitationKind.PRACTICE_STAFF,
        email="kim@maple.ca",
        role=PracticeRole.REVIEWER,
        target=practice,
    )
    kim = make_user(email="kim@maple.ca", name="Kim Park")
    service.accept(issued.token, kim)
    assert PracticeMember.objects.get(user=kim).role == PracticeRole.REVIEWER


def test_practice_invites_the_owner_of_a_client_it_created(
    practice: Practice, practice_admin: User
) -> None:
    client_org = Organisation.objects.create(name="Client Co.")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=client_org)
    assignment.assigned_staff.add(PracticeMember.objects.get(user=practice_admin))
    issued = service.create(
        inviter=practice_admin,
        kind=InvitationKind.ORGANISATION_OWNER,
        email="boss@client.ca",
        role=OrganisationRole.OWNER,
        target=client_org,
    )
    boss = make_user(email="boss@client.ca", name="Pat Boss")
    service.accept(issued.token, boss)
    assert OrganisationMember.objects.get(user=boss).role == OrganisationRole.OWNER
    assert can_access(practice_admin, client_org)  # the accountant stays assigned


def test_organisation_invites_a_user(owner: User, organisation: Organisation) -> None:
    issued = service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_USER,
        email="ali@refined.ca",
        role=OrganisationRole.SALES,
        target=organisation,
    )
    ali = make_user(email="ali@refined.ca", name="Ali Haddad")
    service.accept(issued.token, ali)
    assert OrganisationMember.objects.get(user=ali).role == OrganisationRole.SALES


# ---- accept rules ---------------------------------------------------------------------------


@pytest.fixture
def user_invite(owner: User, organisation: Organisation) -> service.Issued:
    return service.create(
        inviter=owner,
        kind=InvitationKind.ORGANISATION_USER,
        email="ali@refined.ca",
        role=OrganisationRole.SALES,
        target=organisation,
    )


def test_accept_is_bound_to_the_invited_email(user_invite: service.Issued) -> None:
    stranger = make_user(email="eve@evil.ca", name="Eve")
    with pytest.raises(CatalogueError) as excinfo:
        service.accept(user_invite.token, stranger)
    assert code_of(excinfo) == "invitation.wrong_account"
    assert excinfo.value.status_code == 403
    assert not OrganisationMember.objects.filter(user=stranger).exists()
    assert Invitation.objects.get().status == "pending"  # the right person can still accept


def test_link_is_single_use(user_invite: service.Issued) -> None:
    ali = make_user(email="ali@refined.ca", name="Ali")
    service.accept(user_invite.token, ali)
    with pytest.raises(CatalogueError) as excinfo:
        service.accept(user_invite.token, ali)
    assert code_of(excinfo) == "invitation.used"
    assert excinfo.value.status_code == 410


def test_expired_link_is_refused(user_invite: service.Issued) -> None:
    Invitation.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    with pytest.raises(CatalogueError) as excinfo:
        service.accept(user_invite.token, make_user(email="ali@refined.ca"))
    assert code_of(excinfo) == "invitation.expired"


def test_unknown_link_is_refused() -> None:
    with pytest.raises(CatalogueError) as excinfo:
        service.lookup("not-a-real-token")
    assert code_of(excinfo) == "invitation.invalid"
    assert excinfo.value.status_code == 404


def test_existing_member_is_attached_not_duplicated(
    owner: User, organisation: Organisation
) -> None:
    ali = make_user(email="ali@refined.ca", name="Ali")
    OrganisationMember.objects.create(
        organisation=organisation, user=ali, role=OrganisationRole.EMPLOYEE
    )
    with pytest.raises(CatalogueError) as excinfo:
        service.create(
            inviter=owner,
            kind=InvitationKind.ORGANISATION_USER,
            email="ali@refined.ca",
            role=OrganisationRole.SALES,
            target=organisation,
        )
    assert code_of(excinfo) == "invitation.already_member"


# ---- create rules ---------------------------------------------------------------------------


def test_only_admins_may_invite(
    owner: User, organisation: Organisation, practice: Practice
) -> None:
    sales = make_user(email="ali@refined.ca")
    OrganisationMember.objects.create(organisation=organisation, user=sales, role="sales")
    staff = make_user(email="kim@maple.ca")
    PracticeMember.objects.create(practice=practice, user=staff, role=PracticeRole.ACCOUNTANT)
    outsider = make_user(email="eve@evil.ca")
    refused: list[tuple[User, str, Practice | Organisation, str]] = [
        (sales, InvitationKind.ORGANISATION_USER, organisation, OrganisationRole.ADMIN),
        (sales, InvitationKind.ORGANISATION_ACCOUNTANT, organisation, AssignmentRole.TAX),
        (staff, InvitationKind.PRACTICE_STAFF, practice, PracticeRole.PRACTICE_ADMIN),
        (outsider, InvitationKind.ORGANISATION_USER, organisation, OrganisationRole.OWNER),
        (outsider, InvitationKind.ORGANISATION_OWNER, organisation, OrganisationRole.OWNER),
        (owner, InvitationKind.PRACTICE_STAFF, practice, PracticeRole.ACCOUNTANT),
    ]
    for inviter, kind, target, role in refused:
        with pytest.raises(CatalogueError) as excinfo:
            service.create(inviter=inviter, kind=kind, email="new@x.ca", role=role, target=target)
        assert code_of(excinfo) == "invitation.not_allowed", (inviter, kind)
    assert not Invitation.objects.exists()


def test_owner_invitation_refused_when_an_owner_exists(
    organisation: Organisation, practice: Practice, practice_admin: User
) -> None:
    PracticeAssignment.objects.create(practice=practice, organisation=organisation)
    with pytest.raises(CatalogueError) as excinfo:
        service.create(
            inviter=practice_admin,
            kind=InvitationKind.ORGANISATION_OWNER,
            email="boss@x.ca",
            role=OrganisationRole.OWNER,
            target=organisation,
        )
    assert code_of(excinfo) == "invitation.has_owner"


def test_second_pending_invitation_is_refused_but_expired_one_is_replaced(
    owner: User, organisation: Organisation, user_invite: service.Issued
) -> None:
    kwargs: dict[str, Any] = {
        "inviter": owner,
        "kind": InvitationKind.ORGANISATION_USER,
        "email": "ali@refined.ca",
        "role": OrganisationRole.SALES,
        "target": organisation,
    }
    with pytest.raises(CatalogueError) as excinfo:
        service.create(**kwargs)
    assert code_of(excinfo) == "invitation.already_pending"

    Invitation.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
    fresh = service.create(**kwargs)
    old = Invitation.objects.exclude(pk=fresh.invitation.pk).get()
    assert old.status == "revoked"
    assert fresh.invitation.status == "pending"


# ---- resend / revoke ------------------------------------------------------------------------


def test_resend_issues_a_new_link_and_kills_the_old_one(
    owner: User, user_invite: service.Issued
) -> None:
    Invitation.objects.update(
        last_sent_at=timezone.now() - timedelta(minutes=2),
        expires_at=timezone.now() + timedelta(days=1),
    )
    again = service.resend(user_invite.invitation, by=owner)
    assert again.token != user_invite.token
    assert again.invitation.send_count == 2
    assert again.invitation.expires_at > timezone.now() + timedelta(days=6)
    assert link_token(mail.outbox[-1]) == again.token
    with pytest.raises(CatalogueError):
        service.lookup(user_invite.token)
    assert service.lookup(again.token) == again.invitation


def test_resend_has_a_cooldown(owner: User, user_invite: service.Issued) -> None:
    with pytest.raises(CatalogueError) as excinfo:
        service.resend(user_invite.invitation, by=owner)
    assert code_of(excinfo) == "invitation.resend_too_soon"


def test_revoke_stops_the_link(owner: User, user_invite: service.Issued) -> None:
    service.revoke(user_invite.invitation, by=owner)
    with pytest.raises(CatalogueError) as excinfo:
        service.accept(user_invite.token, make_user(email="ali@refined.ca"))
    assert code_of(excinfo) == "invitation.revoked"
    with pytest.raises(CatalogueError) as again:
        service.revoke(user_invite.invitation, by=owner)
    assert code_of(again) == "invitation.not_pending"


def test_strangers_cannot_resend_or_revoke(user_invite: service.Issued) -> None:
    eve = make_user(email="eve@evil.ca")
    for action in (service.resend, service.revoke):
        with pytest.raises(CatalogueError) as excinfo:
            action(user_invite.invitation, by=eve)
        assert code_of(excinfo) == "invitation.not_allowed"


def test_email_names_the_inviter_target_and_expiry(user_invite: service.Issued) -> None:
    message = mail.outbox[-1]
    assert "Sam Roy" in message.subject and "Refined Interiors Inc." in message.subject
    assert "http://localhost:3000/invite/" in message.body
    assert "expires" in message.body
    assert Invitation.objects.get().token_hash not in message.body


# ---- API ------------------------------------------------------------------------------------


def api(client: Client, path: str, body: dict[str, Any] | None = None) -> Any:
    return client.post(f"/api/v1/invitations{path}", body or {}, content_type="application/json")


def test_api_full_flow_owner_invites_accountant(
    owner: User, organisation: Organisation, practice: Practice, practice_admin: User
) -> None:
    sam = Client()
    login(sam, "sam@refined.ca")
    created = api(
        sam,
        "",
        {
            "kind": "organisation_accountant",
            "email": "dana@maple.ca",
            "role": "bookkeeping",
            "organisation": str(organisation.public_id),
        },
    )
    assert created.status_code == 201, created.json()
    assert created.json()["status"] == "pending"
    token = link_token(mail.outbox[-1])

    preview = api(Client(), "/preview", {"token": token})  # no sign-in needed to preview
    assert preview.status_code == 200
    assert preview.json()["target_name"] == "Refined Interiors Inc."
    assert preview.json()["inviter_name"] == "Sam Roy"

    dana = Client()
    login(dana, "dana@maple.ca")
    accepted = api(dana, "/accept", {"token": token})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    orgs = dana.get("/api/v1/me/organisations").json()
    assert [o["name"] for o in orgs] == ["Refined Interiors Inc."]

    again = api(dana, "/accept", {"token": token})
    assert again.status_code == 410
    assert again.json()["code"] == "invitation.used"


def test_api_wrong_account_and_anonymous(user_invite: service.Issued) -> None:
    make_user(email="eve@evil.ca")
    eve = Client()
    login(eve, "eve@evil.ca")
    wrong = api(eve, "/accept", {"token": user_invite.token})
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "invitation.wrong_account"
    assert "ali@refined.ca" in wrong.json()["detail"]
    assert api(Client(), "/accept", {"token": user_invite.token}).status_code == 403


def test_api_hides_foreign_invitations_and_targets(
    user_invite: service.Issued, organisation: Organisation
) -> None:
    make_user(email="eve@evil.ca")
    eve = Client()
    login(eve, "eve@evil.ca")
    invitation_id = user_invite.invitation.public_id
    for action in ("resend", "revoke"):
        response = api(eve, f"/{invitation_id}/{action}")
        assert response.status_code == 404
    unknown = api(
        eve,
        "",
        {"kind": "organisation_user", "email": "x@y.ca", "organisation": str(Practice().public_id)},
    )
    foreign = api(
        eve,
        "",
        {
            "kind": "organisation_user",
            "email": "x@y.ca",
            "organisation": str(organisation.public_id),
        },
    )
    assert unknown.status_code == foreign.status_code == 403
    assert unknown.json() == foreign.json()


def test_api_owner_revokes_and_role_is_checked(
    owner: User, organisation: Organisation, user_invite: service.Issued
) -> None:
    sam = Client()
    login(sam, "sam@refined.ca")
    revoked = api(sam, f"/{user_invite.invitation.public_id}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    bad_role = api(
        sam,
        "",
        {
            "kind": "organisation_user",
            "email": "x@y.ca",
            "role": "practice_admin",
            "organisation": str(organisation.public_id),
        },
    )
    assert bad_role.status_code == 400
    assert "doesn't fit the invitation" in bad_role.json()["role"][0]
