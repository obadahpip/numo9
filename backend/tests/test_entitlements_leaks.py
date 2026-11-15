"""U-03-T13 — entitlement-leak suite: every feature key × every status, allowed or denied.

Acceptance: the matrix test is all green. The organisation is on a package with Accounting only
(plus the free sets, in every package) and once had Payroll (a downgrade: history). For each
subscription state and each feature key in the catalogue the expected answer is computed from the
rules alone — not from the engine — and checked twice: through the engine
(``Engine.allows``) and through the API's permission stack (``ReadOnlyGuard`` + ``RequiresFeature``
on a view declaring the key, GET and POST):

- full access (trialing, active, past_due within grace, demo): a key is allowed when its product
  is entitled (Accounting, Practice, Client portal), or when it is a read key of a product the
  organisation had (Payroll);
- read-only (past_due after grace, read_only, cancelled): read keys of those products only; every
  POST answers 402 ``entitlement.organisation_read_only``;
- never: a product not in the package and never had (Tax, Inventory, Finance), planned companion
  apps, any key outside an organisation.

A leak is a key allowed where the rules deny it (a lapsed organisation keeping paid features) or
denied where they allow it (a paying organisation losing them).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from numo9.accounts.models import User
from numo9.catalogue.models import FeatureKey
from numo9.entitlements.engine import Engine, resolve_entitlements
from numo9.entitlements.models import StatusReason, SubscriptionStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.entitlement_helpers import package, payroll_keys, subscribe
from tests.testapp.entitlement_api import Feature

pytestmark = pytest.mark.django_db

ENTITLED = frozenset({"accounting", "practice", "portal"})
HAD = frozenset({"payroll"})  # entitled before the downgrade

#: status, extra fields, read-only?
STATES: list[tuple[str, str, dict[str, Any], bool]] = [
    ("trialing", SubscriptionStatus.TRIALING, {}, False),
    ("active", SubscriptionStatus.ACTIVE, {}, False),
    ("past_due_in_grace", SubscriptionStatus.PAST_DUE, {"grace_until": timedelta(days=3)}, False),
    (
        "past_due_after_grace",
        SubscriptionStatus.PAST_DUE,
        {"grace_until": timedelta(days=-1)},
        True,
    ),
    (
        "read_only",
        SubscriptionStatus.READ_ONLY,
        {"status_reason": StatusReason.PAYMENT_FAILED},
        True,
    ),
    ("cancelled", SubscriptionStatus.CANCELLED, {"status_reason": StatusReason.CANCELLED}, True),
    ("demo", SubscriptionStatus.DEMO, {}, False),
]


def expected(key: FeatureKey, read_only: bool) -> bool:
    product = key.product.code
    if product in ENTITLED:
        return key.is_read_only or not read_only
    if product in HAD:
        return key.is_read_only
    return False


def downgraded_org(status: str, fields: dict[str, Any]) -> Organisation:
    """An organisation that had Accounting + Payroll, now on Accounting only, in ``status``."""
    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    complete = package("complete", ["accounting", "payroll"])
    starter = package("starter", ["accounting"])
    first = subscribe(org, complete)
    resolve_entitlements(org)  # Payroll was entitled: in the history now
    first.status = SubscriptionStatus.CANCELLED
    first.save()
    values = {k: timezone.now() + v if isinstance(v, timedelta) else v for k, v in fields.items()}
    subscribe(org, starter, status, **values)
    return org


@pytest.mark.parametrize(
    ("name", "status", "fields", "read_only"), STATES, ids=[s[0] for s in STATES]
)
def test_engine_matrix(name: str, status: str, fields: dict[str, Any], read_only: bool) -> None:
    payroll_keys()
    org = downgraded_org(status, fields)
    engine = Engine()
    keys = list(FeatureKey.objects.select_related("product"))
    assert len(keys) > 50  # every seeded key, plus the Payroll test keys
    leaks = [
        (key.key, expected(key, read_only))
        for key in keys
        if engine.allows(org, key.key) != expected(key, read_only)
    ]
    assert leaks == [], f"{name}: {leaks}"


@pytest.mark.parametrize(
    ("name", "status", "fields", "read_only"), STATES, ids=[s[0] for s in STATES]
)
def test_api_matrix(name: str, status: str, fields: dict[str, Any], read_only: bool) -> None:
    payroll_keys()
    org = downgraded_org(status, fields)
    owner = User.objects.create_user(email="dana@maple.ca", password="x" * 12, name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=owner, role=OrganisationRole.OWNER)
    factory = APIRequestFactory()
    leaks: list[tuple[str, str, int, int]] = []
    with org_context(org):
        for key in FeatureKey.objects.select_related("product"):
            view = Feature.for_key(key.key).as_view()
            allowed = expected(key, read_only)
            for method, ok in (("get", 200), ("post", 201)):
                request = getattr(factory, method)(f"/api/v1/o/{org.public_id}/test")
                force_authenticate(request, user=owner)
                response = view(request, org=str(org.public_id))
                if method == "post" and read_only:
                    want = 402  # organisation_read_only, whatever the key
                    code = response.data.get("code") if response.status_code == 402 else None
                    if code != "entitlement.organisation_read_only":
                        leaks.append((key.key, method, response.status_code, want))
                    continue
                want = ok if allowed else 402
                if response.status_code != want:
                    leaks.append((key.key, method, response.status_code, want))
    assert leaks == [], f"{name}: {leaks}"


def test_nothing_outside_an_organisation() -> None:
    payroll_keys()
    engine = Engine()
    assert not [
        k for k in FeatureKey.objects.values_list("key", flat=True) if engine.allows(None, k)
    ]
