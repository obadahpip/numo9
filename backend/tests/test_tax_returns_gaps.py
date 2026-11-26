"""G-03-T15 — gap-54: the GST/HST return is on every package with Tax — each active package that
includes the Tax product resolves ``tax.returns.read`` / ``.write`` / ``.approve`` and its
people prepare a return; a package without Tax gets the explicit 402 gate naming the product
(the web app shows the locked panel in place: frontend/e2e/tax-returns.spec.ts)."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.catalogue.models import Product
from numo9.entitlements.engine import resolve_entitlements
from numo9.entitlements.models import Package, PackageStatus
from tests.entitlement_helpers import package, subscribe
from tests.tax_report_helpers import june_books

pytestmark = pytest.mark.django_db
KEYS = ("tax.returns.read", "tax.returns.write", "tax.returns.approve")


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = june_books()
    client = Client()
    client.force_login(books["owner"])
    base = f"/api/v1/o/{books['org'].public_id}/tax/returns"
    return {**books, "client": client, "base": base}


@pytest.mark.gap("gap-54")
def test_every_package_with_tax_has_the_return(ctx: dict[str, Any]) -> None:
    tax = Product.objects.get(code="tax")
    with_tax = [
        p
        for p in Package.objects.filter(status=PackageStatus.ACTIVE)
        if p.products.filter(pk=tax.pk).exists()
    ] or [package("books_tax", ["accounting", "tax"])]
    for plan in with_tax:
        subscribe(ctx["org"], plan)
        features = resolve_entitlements(ctx["org"]).features
        assert set(KEYS) <= set(features), plan.code
        made = ctx["client"].post(
            ctx["base"], {"period": str(ctx["period"].public_id)}, content_type="application/json"
        )
        assert made.status_code == 201, (plan.code, made.content)


@pytest.mark.gap("gap-54")
def test_a_package_without_tax_is_gated(ctx: dict[str, Any]) -> None:
    subscribe(ctx["org"], package("books_only", ["accounting"]))
    assert "tax.returns.read" not in resolve_entitlements(ctx["org"]).features
    refused = ctx["client"].get(ctx["base"])
    assert refused.status_code == 402
    body = refused.json()
    assert (body["code"], body["feature"], body["product"]) == (
        "entitlement.feature_not_in_package",
        "tax.returns.read",
        "tax",
    )
