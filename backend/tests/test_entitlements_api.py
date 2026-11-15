"""U-03-T07, T08, T09 — the engine behind the API.

T07 acceptance: a gated endpoint returns 402 with the product. The body names the feature, the
product (code and name) and the packages offered that include it; CORE is never gated; a foreign
organisation answers 404 before any 402; practice users get the organisation's answer.
T08 acceptance: POST in read_only refused; export allowed. Also: reason and since in the body;
reads stay open; billing (every method) allowed; an outsider never learns the state (404).
T09 acceptance: GET /api/v1/o/<org>/entitlements answers < 20 ms p95 cached. Also: the body, the
names in the request's language, a change seen at once, 404 for outsiders, open while read-only.
"""

from __future__ import annotations

import statistics
import time
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.entitlements.models import StatusReason, SubscriptionStatus
from numo9.tenancy.models import (
    AssignmentRole,
    Organisation,
    OrganisationMember,
    OrganisationRole,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)
from tests.entitlement_helpers import package, payroll_keys, subscribe

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.testapp.entitlement_urls")]


@pytest.fixture
def org() -> Organisation:
    payroll_keys()
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


def member(org: Organisation, email: str, role: str = OrganisationRole.OWNER) -> User:
    user = User.objects.create_user(email=email, password="x" * 12, name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def owner(org: Organisation) -> APIClient:
    return client_for(member(org, "dana@maple.ca"))


def url(org: Organisation, path: str) -> str:
    return f"/api/v1/o/{org.public_id}/{path}"


# ---- T07: RequiresFeature on the engine ---------------------------------------------------------


def test_gated_endpoint_answers_402_naming_product_and_packages(
    org: Organisation, owner: APIClient
) -> None:
    package("starter", ["accounting"], "Starter")
    package("complete", ["accounting", "payroll"], "Complete")
    package("payroll_plus", ["payroll"], "Payroll Plus")
    subscribe(org, package("growth", ["accounting", "tax"], "Growth"))
    response = owner.post(url(org, "test/pay-runs"))
    assert response.status_code == 402
    assert response.data["code"] == "entitlement.feature_not_in_package"
    assert response.data["feature"] == "payroll.pay_runs.write"
    assert (response.data["product"], response.data["product_name"]) == ("payroll", "Payroll")
    assert response.data["packages"] == [
        {"code": "complete", "name": "Complete"},
        {"code": "payroll_plus", "name": "Payroll Plus"},
    ]
    assert "part of Payroll" in response.data["detail"]
    assert owner.get(url(org, "test/pay-runs")).status_code == 402  # read too: never entitled


def test_entitled_endpoint_answers(org: Organisation, owner: APIClient) -> None:
    subscribe(org, package("complete", ["accounting", "payroll"]))
    assert owner.get(url(org, "test/pay-runs")).status_code == 200
    assert owner.post(url(org, "test/pay-runs")).status_code == 201


def test_core_is_never_gated(org: Organisation, owner: APIClient) -> None:
    subscribe(org, package("starter", ["accounting"]))
    assert owner.get(url(org, "test/core")).status_code == 200
    assert owner.post(url(org, "test/core")).status_code == 201


def test_foreign_organisation_is_404_before_402(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]))
    stranger = client_for(member(Organisation.objects.create(name="Other"), "x@other.ca"))
    assert stranger.post(url(org, "test/pay-runs")).status_code == 404


def test_practice_user_gets_the_organisations_answer(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]))
    practice = Practice.objects.create(name="Profitex CPA")
    accountant = User.objects.create_user(email="cpa@profitex.ca", password="x" * 12, name="Ana")
    PracticeMember.objects.create(
        practice=practice, user=accountant, role=PracticeRole.PRACTICE_ADMIN
    )
    PracticeAssignment.objects.create(
        practice=practice, organisation=org, role=AssignmentRole.BOOKKEEPING
    )
    client = client_for(accountant)
    assert client.get(url(org, "test/pay-runs")).status_code == 402  # the org has no Payroll
    body = client.get(url(org, "entitlements")).json()
    assert "payroll" not in body["products"] and body["package"] == "starter"
    assert body["viewer"] == {"can_change_package": False}  # accountants never buy


# ---- T08: read-only mode ------------------------------------------------------------------------


@pytest.fixture
def read_only_org(org: Organisation) -> Organisation:
    grace = timezone.now() - timedelta(days=1)
    subscribe(
        org,
        package("complete", ["accounting", "payroll"]),
        SubscriptionStatus.READ_ONLY,
        status_reason=StatusReason.PAYMENT_FAILED,
        grace_until=grace,
    )
    return org


def test_post_in_read_only_is_refused(read_only_org: Organisation, owner: APIClient) -> None:
    response = owner.post(url(read_only_org, "test/core"))
    assert response.status_code == 402
    assert response.data["code"] == "entitlement.organisation_read_only"
    assert response.data["reason"] == "payment_failed"
    assert response.data["since"] is not None
    for method in ("put", "patch", "delete"):
        assert getattr(owner, method)(url(read_only_org, "test/core")).status_code in (402, 405)
    assert owner.post(url(read_only_org, "test/pay-runs")).data["code"] == (
        "entitlement.organisation_read_only"
    )


def test_reads_stay_open_in_read_only(read_only_org: Organisation, owner: APIClient) -> None:
    assert owner.get(url(read_only_org, "test/core")).status_code == 200
    assert owner.get(url(read_only_org, "test/pay-runs")).status_code == 200


def test_export_and_billing_are_allowed_in_read_only(
    read_only_org: Organisation, owner: APIClient
) -> None:
    assert owner.post(url(read_only_org, "test/export")).status_code == 202
    assert owner.post(url(read_only_org, "test/billing")).status_code == 201
    assert owner.delete(url(read_only_org, "test/billing")).status_code == 204


def test_cancelled_is_read_and_export_only(org: Organisation, owner: APIClient) -> None:
    subscribe(org, package("starter", ["accounting"]), SubscriptionStatus.CANCELLED)
    response = owner.post(url(org, "test/core"))
    assert (response.status_code, response.data["reason"]) == (402, "cancelled")
    assert owner.post(url(org, "test/export")).status_code == 202


def test_outsider_never_learns_the_read_only_state(read_only_org: Organisation) -> None:
    stranger = client_for(member(Organisation.objects.create(name="Other"), "x@other.ca"))
    assert stranger.post(url(read_only_org, "test/core")).status_code == 404
    assert APIClient().post(url(read_only_org, "test/core")).status_code in (401, 403)


def test_past_due_keeps_writing_during_grace(org: Organisation, owner: APIClient) -> None:
    subscribe(org, package("starter", ["accounting"]), SubscriptionStatus.PAST_DUE)
    assert owner.post(url(org, "test/core")).status_code == 201


# ---- T09: bootstrap API -------------------------------------------------------------------------


def test_bootstrap_body(org: Organisation, owner: APIClient) -> None:
    package("complete", ["accounting", "payroll"], "Complete")
    subscribe(org, package("starter", ["accounting"], "Starter"))
    response = owner.get(url(org, "entitlements"))
    assert response.status_code == 200
    body = response.json()
    assert body["organisation"] == str(org.public_id)
    assert (body["mode"], body["reason"], body["since"]) == ("full", "active", None)
    assert (body["package"], body["package_name"], body["status"]) == (
        "starter",
        "Starter",
        "active",
    )
    assert body["products"] == ["accounting", "portal", "practice"]
    assert "accounting.sales_invoices.approve" in body["features"]
    assert "payroll.pay_runs.read" not in body["features"]
    assert body["product_names"]["payroll"] == "Payroll"
    assert body["packages_by_product"]["payroll"] == [{"code": "complete", "name": "Complete"}]
    assert body["founding"] is False and body["read_products"] == []
    assert body["version"]
    assert body["viewer"] == {"can_change_package": True}  # the owner
    assert body["time_zone"] == "America/Toronto"


def test_bootstrap_sees_a_change_at_once(org: Organisation, owner: APIClient) -> None:
    item = subscribe(org, package("starter", ["accounting"]))
    first = owner.get(url(org, "entitlements")).json()
    item.status = SubscriptionStatus.CANCELLED
    item.save()
    second = owner.get(url(org, "entitlements")).json()
    assert (second["mode"], second["reason"]) == ("read_only", "cancelled")
    assert second["version"] != first["version"]
    assert second["since"] is not None


def test_bootstrap_names_in_the_request_language(org: Organisation, owner: APIClient) -> None:
    package("complete", ["accounting", "payroll"], "Complete")
    body = owner.get(url(org, "entitlements"), HTTP_ACCEPT_LANGUAGE="fr-CA").json()
    assert body["product_names"]["portal"] in ("Portail client", "Client portal")
    english = owner.get(url(org, "entitlements"), HTTP_ACCEPT_LANGUAGE="en-CA").json()
    assert english["product_names"]["portal"] == "Client portal"


def test_bootstrap_is_404_for_outsiders(org: Organisation) -> None:
    stranger = client_for(member(Organisation.objects.create(name="Other"), "x@other.ca"))
    assert stranger.get(url(org, "entitlements")).status_code == 404


def test_bootstrap_open_while_read_only(read_only_org: Organisation, owner: APIClient) -> None:
    body = owner.get(url(read_only_org, "entitlements")).json()
    assert (body["mode"], body["reason"]) == ("read_only", "payment_failed")


def test_bootstrap_answers_under_20_ms_p95_cached(org: Organisation, owner: APIClient) -> None:
    subscribe(org, package("starter", ["accounting"]))
    target = url(org, "entitlements")
    for _ in range(5):  # warm: cache filled, permission sets, URL resolver
        assert owner.get(target).status_code == 200
    durations: list[float] = []
    for _ in range(100):
        start = time.perf_counter()
        response = owner.get(target)
        durations.append((time.perf_counter() - start) * 1000)
        assert response.status_code == 200
    p95 = statistics.quantiles(durations, n=20)[-1]
    assert p95 < 20, f"p95 {p95:.1f} ms"


def body_of(response: Any) -> dict[str, Any]:
    data: dict[str, Any] = response.json()
    return data
