"""FeatureKey model (U-01-T03): duplicate key rejected by the database unique index."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError

from numo9.catalogue.models import (
    CatalogueError,
    FeatureKey,
    Product,
    ProductKind,
    ProductStatus,
    split_key,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def widgets() -> Product:
    return Product.objects.create(code="widgets", kind=ProductKind.MAIN)


@pytest.fixture
def gadgets() -> Product:
    return Product.objects.create(code="gadgets", kind=ProductKind.MAIN)


def test_key_is_created_with_its_description_key(widgets: Product) -> None:
    feature = FeatureKey.objects.create(key="widgets.orders.write", product=widgets)
    feature.refresh_from_db()
    assert feature.description_i18n_key == "catalogue.feature.widgets.orders.write"
    assert feature.is_read_only is False
    assert (feature.area, feature.action) == ("orders", "write")
    assert list(widgets.feature_keys.all()) == [feature]


def test_duplicate_key_rejected_by_the_database_unique_index(
    widgets: Product, gadgets: Product
) -> None:
    FeatureKey.objects.create(key="widgets.orders.read", product=widgets)
    with pytest.raises(IntegrityError), transaction.atomic():
        # bulk_create skips save(): the database itself refuses the same key in another product.
        FeatureKey.objects.bulk_create(
            [FeatureKey(key="widgets.orders.read", product=gadgets, description_i18n_key="x")]
        )
    indexes = connection.introspection.get_constraints(connection.cursor(), "catalogue_featurekey")
    assert any(c["unique"] and c["columns"] == ["key"] for c in indexes.values())


@pytest.mark.parametrize(
    ("key", "read_only"),
    [
        ("widgets.orders.read", True),
        ("widgets.orders.write", False),
        ("widgets.orders.approve", False),
    ],
)
def test_read_only_follows_the_action(widgets: Product, key: str, read_only: bool) -> None:
    feature = FeatureKey.objects.create(key=key, product=widgets, is_read_only=not read_only)
    assert FeatureKey.objects.get(pk=feature.pk).is_read_only is read_only


@pytest.mark.parametrize(
    "key",
    [
        "widgets.orders",
        "widgets.orders.view",
        "widgets.Orders.read",
        "widgets.orders.list.read",
        "Widgets.orders.read",
        "widgets..read",
        "",
    ],
)
def test_malformed_keys_are_refused(widgets: Product, key: str) -> None:
    with pytest.raises(CatalogueError) as error:
        FeatureKey.objects.create(key=key, product=widgets)
    assert error.value.error_dict["key"][0].code == "catalogue.bad_feature_key"


def test_key_must_start_with_its_product_code(widgets: Product) -> None:
    with pytest.raises(CatalogueError) as error:
        FeatureKey.objects.create(key="gadgets.orders.read", product=widgets)
    assert error.value.error_dict["key"][0].code == "catalogue.key_product_mismatch"


def test_companion_keys_carry_the_app_prefix() -> None:
    store = Product.objects.create(
        code="app.store", kind=ProductKind.COMPANION, status=ProductStatus.PLANNED
    )
    feature = FeatureKey.objects.create(key="app.store.orders.write", product=store)
    assert split_key(feature.key) == ("app.store", "orders", "write")


def test_key_never_changes(widgets: Product) -> None:
    feature = FeatureKey.objects.create(key="widgets.orders.read", product=widgets)
    feature.sort = 3
    feature.save()
    feature.key = "widgets.sales.read"
    with pytest.raises(CatalogueError):
        feature.save()


def test_product_with_keys_cannot_be_deleted(widgets: Product) -> None:
    FeatureKey.objects.create(key="widgets.orders.read", product=widgets)
    with pytest.raises(ProtectedError):
        widgets.delete()
