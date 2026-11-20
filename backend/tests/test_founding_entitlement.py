"""U-08-T05 — Entitlement: the founding slot grants all products (incl. ones that ship later).

Acceptance: a founding organisation on the smallest package resolves every key of every active
product; a product shipped after the allocation is entitled too; a planned product is not; the
flag follows the slot (released slot → package products only); the cached answer changes at once.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from numo9.catalogue.models import FeatureKey, Product, ProductStatus
from numo9.entitlements.cache import entitlements_for
from numo9.entitlements.engine import resolve_entitlements
from numo9.founding.models import FoundingSlot
from numo9.founding.services import allocate_founding_slot, sync_founding_flag
from numo9.tenancy.models import Organisation
from tests.entitlement_helpers import package, payroll_keys, subscribe

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    payroll_keys()
    organisation = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    subscribe(organisation, package("starter", ["accounting"]))
    return organisation


def _active_keys() -> set[str]:
    return set(
        FeatureKey.objects.filter(product__status=ProductStatus.ACTIVE).values_list(
            "key", flat=True
        )
    )


def test_founding_org_on_smallest_package_resolves_all_keys(org: Organisation) -> None:
    before = entitlements_for(org)
    assert not before.founding and "payroll" not in before.products
    assert allocate_founding_slot(org) is not None
    answer = entitlements_for(org)  # cache bumped by the allocation
    assert answer.founding
    assert _active_keys() <= answer.features
    assert "app.commerce" not in answer.products  # planned, not shipped


def test_product_shipped_later_is_entitled(org: Organisation) -> None:
    allocate_founding_slot(org)
    commerce = Product.objects.get(code="app.commerce")
    commerce.status = ProductStatus.ACTIVE
    commerce.save()
    assert "app.commerce" in resolve_entitlements(org).products


def test_flag_follows_the_slot(org: Organisation) -> None:
    slot = allocate_founding_slot(org)
    assert slot is not None
    FoundingSlot.objects.filter(pk=slot.pk).update(released_at=timezone.now())
    assert sync_founding_flag(org) is False
    answer = entitlements_for(org)
    assert not answer.founding and "payroll" not in answer.products
