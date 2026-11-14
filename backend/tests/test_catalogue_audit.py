"""Audit hooks on the catalogue (U-01-T14): changing a product's status writes an audit row with
the diff — in the platform log, never the active organisation's."""

from __future__ import annotations

import pytest

from numo9.audit.models import AuditEvent
from numo9.catalogue.models import FeatureKey, Product, ProductKind, ProductStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def events(action: str) -> list[AuditEvent]:
    return list(AuditEvent.platform_events.filter(action=action).order_by("id"))


def test_changing_product_status_writes_an_audit_row_with_the_diff() -> None:
    product = Product.objects.get(code="finance")
    product.status = ProductStatus.RETIRED
    product.save()
    [event] = events("catalogue.product.updated")
    assert event.organisation is None
    assert event.object_type == "catalogue.Product"
    assert event.object_id == str(product.public_id)
    assert event.object_label == "finance"
    assert event.changes == {"status": ["active", "retired"]}


def test_no_change_no_event() -> None:
    product = Product.objects.get(code="tax")
    product.save()
    assert events("catalogue.product.updated") == []


def test_new_product_and_new_key_are_recorded() -> None:
    product = Product.objects.create(code="widgets", kind=ProductKind.MAIN, sort=90)
    FeatureKey.objects.create(key="widgets.orders.write", product=product)
    [created] = events("catalogue.product.created")
    assert created.changes["code"] == [None, "widgets"]
    assert created.changes["status"] == [None, "active"]
    [key] = events("catalogue.featurekey.created")
    assert key.changes["key"] == [None, "widgets.orders.write"]
    assert key.changes["product"][1]["label"] == "widgets"


def test_key_changes_and_deletes_are_recorded() -> None:
    feature = FeatureKey.objects.get(key="portal.requests.write")
    feature.sort = 9999
    feature.save()
    [updated] = events("catalogue.featurekey.updated")
    assert list(updated.changes) == ["sort"]
    feature.delete()
    [deleted] = events("catalogue.featurekey.deleted")
    assert deleted.changes["key"] == ["portal.requests.write", None]


def test_changes_in_an_organisation_request_stay_in_the_platform_log() -> None:
    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    with org_context(org):
        product = Product.objects.get(code="inventory")
        product.sort = 41
        product.save()
    [event] = events("catalogue.product.updated")
    assert event.organisation is None
    assert not AuditEvent.platform_events.filter(organisation=org).exists()


def test_seeding_is_not_an_audited_change() -> None:
    assert not AuditEvent.platform_events.filter(action__startswith="catalogue.").exists()
