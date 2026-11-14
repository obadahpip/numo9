"""Product model (U-01-T02): migration applies; code unique; retired product cannot be deleted."""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction

from numo9.catalogue.models import CatalogueError, Product, ProductKind, ProductStatus
from numo9.tenancy.checks import models_violating_org_ownership

pytestmark = pytest.mark.django_db


def make(code: str = "widgets", kind: str = ProductKind.MAIN, **fields: Any) -> Product:
    return Product.objects.create(code=code, kind=kind, **fields)


def test_product_is_created_with_defaults() -> None:
    product = make()
    product.refresh_from_db()
    assert product.status == ProductStatus.ACTIVE
    assert product.name_i18n_key == "catalogue.product.widgets"
    assert product.public_id is not None and product.created_at and product.updated_at
    assert str(product) == "widgets"


def test_code_is_unique_in_the_database() -> None:
    make()
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.bulk_create([Product(code="widgets", name_i18n_key="x", kind="main")])


@pytest.mark.parametrize("code", ["Widgets", "1widgets", "wid gets", "app.store", "", "a-b"])
def test_main_product_code_format(code: str) -> None:
    with pytest.raises(CatalogueError):
        make(code)


def test_companion_codes_are_app_dot_name() -> None:
    assert make("app.store", kind=ProductKind.COMPANION, status=ProductStatus.PLANNED).pk
    with pytest.raises(CatalogueError):
        make("store", kind=ProductKind.COMPANION)


def test_kind_and_status_are_constrained_in_the_database() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.bulk_create([Product(code="x1", name_i18n_key="x", kind="bundle")])
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.bulk_create(
            [Product(code="x2", name_i18n_key="x", kind="main", status="gone")]
        )


def test_code_never_changes_but_the_rest_may() -> None:
    product = make()
    product.sort = 5
    product.status = ProductStatus.RETIRED
    product.name_i18n_key = "catalogue.product.widgetsRenamed"
    product.save()
    product.code = "gadgets"
    with pytest.raises(CatalogueError) as error:
        product.save()
    assert error.value.error_dict["code"][0].code == "catalogue.code_immutable"
    assert Product.objects.get(pk=product.pk).code == "widgets"


def test_retired_product_cannot_be_deleted() -> None:
    product = make(status=ProductStatus.RETIRED)
    with pytest.raises(CatalogueError) as error:
        product.delete()
    assert error.value.code == "catalogue.product_retired"
    with pytest.raises(CatalogueError):
        Product.objects.filter(pk=product.pk).delete()
    assert Product.objects.filter(pk=product.pk).exists()


def test_active_product_without_keys_can_be_deleted() -> None:
    product = make()
    product.delete()
    assert not Product.objects.filter(code="widgets").exists()


def test_platform_model_allow_listed() -> None:
    config = apps.get_app_config("catalogue")
    assert models_violating_org_ownership([config], ("numo9.",)) == []
