"""U-03-T15 — gap-closure tests gap-06 / gap-14 / gap-41, backend half (the Playwright half:
frontend/e2e/gap-06-14-41.spec.ts, entitlements-gating.spec.ts).

- gap-06 — Xero paywalls invoice approval. Core accounting controls (approving invoices, bills,
  purchase orders, expense claims and journals, credit notes, reminders, bank accounts, lock
  dates, the audit log) are never gated inside the Accounting product: every Accounting approve
  key belongs to Accounting, and an organisation with Accounting — on the smallest package — gets
  every one of them. Lock dates, the audit log and approval limits are CORE (never gated at all);
- gap-14 — Xero's credit note silently redirects. A gated API call answers 402 in place: never a
  3xx, never another resource;
- gap-41 — generic upgrade banners. The 402 names the feature, the product and the packages that
  include it, and the bootstrap gives the screens the same names.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.catalogue.models import FeatureKey
from numo9.entitlements.engine import resolve_entitlements
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.entitlement_helpers import package, payroll_keys, subscribe

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.testapp.entitlement_urls")]

CORE_CONTROLS = (
    "credit_notes",
    "invoice_reminders",
    "banking",
    "sales_invoices",
    "bills",
    "journals",
    "period_close",
    "multi_currency",
)


@pytest.fixture
def org() -> Organisation:
    payroll_keys()
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def owner(org: Organisation) -> APIClient:
    user = User.objects.create_user(email="dana@maple.ca", password="x" * 12, name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role=OrganisationRole.OWNER)
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.gap("gap-06")
def test_approval_is_never_gated_within_accounting(org: Organisation) -> None:
    approve = FeatureKey.objects.filter(key__endswith=".approve", key__startswith="accounting.")
    assert approve.count() >= 5
    assert {k.product.code for k in approve} == {"accounting"}  # never a separate product
    subscribe(org, package("starter", ["accounting"]))  # the smallest package with Accounting
    answer = resolve_entitlements(org)
    accounting = set(
        FeatureKey.objects.filter(product__code="accounting").values_list("key", flat=True)
    )
    assert accounting <= answer.features  # every control, approval included
    for area in CORE_CONTROLS:
        assert any(k.startswith(f"accounting.{area}.") for k in answer.features), area


@pytest.mark.gap("gap-06")
def test_lock_dates_audit_and_approval_limits_are_core() -> None:
    from django.urls import get_resolver

    from numo9.catalogue.drf import CORE, declared_feature

    checked = 0
    for pattern in get_resolver("numo9.urls").url_patterns:
        for sub in getattr(pattern, "url_patterns", [pattern]):
            view = getattr(getattr(sub, "callback", None), "view_class", None)
            route = str(getattr(sub, "pattern", ""))
            in_org = route.startswith("o/<")  # organisation endpoints (platform ones aren't gated)
            if (
                view is None
                or not in_org
                or not any(p in route for p in ("audit", "limit", "lock"))
            ):
                continue
            for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                if hasattr(view, method.lower()):
                    assert declared_feature(view, method) == CORE, (route, method)
                    checked += 1
    assert checked > 0


@pytest.mark.gap("gap-14")
def test_gated_call_answers_402_in_place_never_a_redirect(
    org: Organisation, owner: APIClient
) -> None:
    subscribe(org, package("starter", ["accounting"]))
    for method in ("get", "post"):
        response = getattr(owner, method)(f"/api/v1/o/{org.public_id}/test/pay-runs")
        assert response.status_code == 402
        assert not response.has_header("Location")
        assert response.data["code"] == "entitlement.feature_not_in_package"


@pytest.mark.gap("gap-41")
def test_the_prompt_is_explicit(org: Organisation, owner: APIClient) -> None:
    package("complete", ["accounting", "payroll"], "Complete")
    subscribe(org, package("starter", ["accounting"], "Starter"))
    response = owner.post(f"/api/v1/o/{org.public_id}/test/pay-runs")
    assert response.data["product_name"] == "Payroll"
    assert response.data["packages"] == [{"code": "complete", "name": "Complete"}]
    assert "Payroll" in response.data["detail"]
    body = owner.get(f"/api/v1/o/{org.public_id}/entitlements").json()
    assert body["packages_by_product"]["payroll"] == [{"code": "complete", "name": "Complete"}]
    assert body["package_name"] == "Starter"
