"""Segregation-of-duties helper assert_not_creator (A-03-T08). Acceptance: self-approval refused."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import translation
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.i18n.exceptions import exception_handler
from numo9.rbac.approvals import ApprovalLimitExceeded, assert_can_approve
from numo9.rbac.duties import SelfApprovalRefused, assert_not_creator, creators, is_creator
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.testapp.models import Widget

pytestmark = pytest.mark.django_db


def make_user(email: str, name: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=name)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def record(org: Organisation, created_by: User | None) -> Widget:
    with org_context(org):
        widget: Widget = Widget.objects.create(label="PO-0001", created_by=created_by)
    return widget


def test_self_approval_is_refused(org: Organisation) -> None:
    sam = make_user("sam@refined.ca", "Sam Patel")
    po = record(org, sam)
    with pytest.raises(SelfApprovalRefused) as refused:
        assert_not_creator(sam, po)
    assert refused.value.status_code == 403
    assert refused.value.get_codes() == "approval.self_approval"
    assert (
        str(refused.value.detail) == "You created this widget, so someone else has to approve it."
    )
    assert refused.value.field == "created_by"


def test_someone_else_may_approve(org: Organisation) -> None:
    sam = make_user("sam@refined.ca", "Sam Patel")
    dana = make_user("dana@refined.ca", "Dana Lee")
    po = record(org, sam)
    assert_not_creator(dana, po)  # no exception
    assert is_creator(sam, po) and not is_creator(dana, po)


def test_system_created_record_has_no_creator(org: Organisation) -> None:
    po = record(org, None)
    assert creators(po) == []
    assert_not_creator(make_user("dana@refined.ca", "Dana Lee"), po)


def test_record_name_and_several_fields(org: Organisation) -> None:
    sam = make_user("sam@refined.ca", "Sam Patel")
    po = record(org, None)
    setattr(po, "submitted_by_id", sam.pk)  # noqa: B010 — a module record's "submitted by"
    with pytest.raises(SelfApprovalRefused) as refused:
        assert_not_creator(sam, po, fields=("created_by", "submitted_by"), record="bill")
    assert "You created this bill" in str(refused.value.detail)
    assert refused.value.extra == {"field": "submitted_by"}
    assert_not_creator(sam, po, fields="created_by")  # a single field as a string


def test_unknown_field_is_a_programming_error(org: Organisation) -> None:
    po = record(org, None)
    with pytest.raises(TypeError, match="approved_by"):
        assert_not_creator(make_user("a@refined.ca", "A"), po, fields=("approved_by",))
    with pytest.raises(TypeError):
        assert_not_creator(None, po, fields=("approved_by",))


def test_anonymous_or_unsaved_user_is_never_the_creator(org: Organisation) -> None:
    po = record(org, make_user("sam@refined.ca", "Sam Patel"))
    assert_not_creator(None, po)
    assert not is_creator(User(email="new@refined.ca"), po)


def test_api_error_body_and_french(org: Organisation) -> None:
    sam = make_user("sam@refined.ca", "Sam Patel")
    po = record(org, sam)
    with translation.override("fr-ca"), pytest.raises(SelfApprovalRefused) as refused:
        assert_not_creator(sam, po, record="facture fournisseur")
    response = exception_handler(refused.value, {"view": APIView()})
    assert response is not None and response.status_code == 403
    assert response.data["code"] == "approval.self_approval"
    assert response.data["detail"].startswith("Vous avez créé ce document (facture fournisseur)")


def test_with_approval_limits_the_creator_is_not_suggested(org: Organisation) -> None:
    sam = make_user("sam@refined.ca", "Sam Patel")
    creator = make_user("casey@refined.ca", "Casey Creator")
    owner = make_user("avery@refined.ca", "Avery Owner")
    for person, role in ((sam, "purchasing"), (creator, "admin"), (owner, "owner")):
        OrganisationMember.objects.create(organisation=org, user=person, role=role)
    po = record(org, creator)
    with org_context(org):
        for person in (sam, creator, owner):
            ApprovalLimit.objects.create(user=person, doc_type="bill", max_amount=Decimal(9000))
        ApprovalLimit.objects.filter(user=sam).update(max_amount=Decimal(100))
        with pytest.raises(ApprovalLimitExceeded) as refused:
            assert_can_approve(sam, "bill", Decimal(500), exclude=creators(po))
    assert [a.name for a in refused.value.next_approvers] == ["Avery Owner"]
    with pytest.raises(SelfApprovalRefused):
        assert_not_creator(creator, po)  # within the limit, but the creator
