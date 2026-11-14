"""Catalogue seed (U-01-T04): 7 products (+ planned companion apps) and the Phase 0–1 keys;
idempotent — running the seed twice leaves the same rows."""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from django.apps import apps

from numo9.catalogue.models import FeatureKey, Product, split_key

pytestmark = pytest.mark.django_db

seed_migration = importlib.import_module("numo9.catalogue.migrations.0003_seed_catalogue")

PRODUCTS = ["accounting", "tax", "payroll", "inventory", "finance", "practice", "portal"]
COMPANIONS = ["app.commerce", "app.bank", "app.receipts"]


def snapshot() -> tuple[list[Any], list[Any]]:
    products = list(
        Product.objects.order_by("code").values_list(
            "id", "public_id", "code", "name_i18n_key", "kind", "status", "sort"
        )
    )
    keys = list(
        FeatureKey.objects.order_by("key").values_list(
            "id",
            "public_id",
            "key",
            "product__code",
            "description_i18n_key",
            "is_read_only",
            "sort",
        )
    )
    return products, keys


def test_seven_products_and_planned_companion_apps() -> None:
    main_and_free = Product.objects.exclude(kind="companion")
    assert list(main_and_free.values_list("code", flat=True)) == PRODUCTS
    assert dict(main_and_free.values_list("code", "kind")) == {
        **dict.fromkeys(PRODUCTS[:5], "main"),
        "practice": "free_set",
        "portal": "free_set",
    }
    assert set(main_and_free.values_list("status", flat=True)) == {"active"}
    companions = Product.objects.filter(kind="companion")
    assert list(companions.values_list("code", flat=True)) == COMPANIONS
    assert set(companions.values_list("status", flat=True)) == {"planned"}


def test_phase_0_1_keys_are_seeded_and_well_formed() -> None:
    keys = list(FeatureKey.objects.select_related("product"))
    prefixes = {k.product.code for k in keys}
    assert prefixes == {"accounting", "tax", "practice", "portal"}
    for feature in keys:
        product, _area, action = split_key(feature.key)
        assert product == feature.product.code
        assert feature.is_read_only is (action == "read")
        assert feature.description_i18n_key == f"catalogue.feature.{feature.key}"
    seeded = {k.key for k in keys}
    # gap 51: projects, expense claims and document capture are in Accounting, not add-ons.
    assert {
        "accounting.projects.write",
        "accounting.expense_claims.write",
        "accounting.documents.write",
        "accounting.invoice_reminders.write",
        "accounting.journals.approve",
        "tax.returns.approve",
    } <= seeded
    assert len(seeded) == len(keys) == 59


def test_seed_is_idempotent() -> None:
    before = snapshot()
    seed_migration.seed(apps)
    seed_migration.seed(apps)
    assert snapshot() == before


def test_seed_restores_changed_rows_without_duplicates() -> None:
    Product.objects.filter(code="tax").update(sort=999)
    FeatureKey.objects.filter(key="tax.codes.read").delete()
    seed_migration.seed(apps)
    assert Product.objects.get(code="tax").sort == 20
    assert FeatureKey.objects.filter(key="tax.codes.read").count() == 1
    assert Product.objects.count() == 10


def test_after_migrate_missing_rows_come_back_and_changes_stay() -> None:
    from numo9.catalogue.apps import _seed_after_migrate

    Product.objects.filter(code="finance").update(status="retired")
    FeatureKey.objects.filter(key="portal.requests.write").delete()
    _seed_after_migrate(apps.get_app_config("catalogue"))
    assert Product.objects.get(code="finance").status == "retired"  # the owner's change stays
    assert FeatureKey.objects.filter(key="portal.requests.write").exists()
