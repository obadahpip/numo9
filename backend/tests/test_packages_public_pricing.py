"""Public pricing API (U-02-T08): GET /api/v1/public/pricing — active packages, current prices,
founding badge data; consumed later by the website (Q-01). Acceptance: the response is cached
60 s; draft and retired packages are excluded."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from numo9.catalogue.models import Product
from numo9.packages import public
from numo9.packages.models import (
    Package,
    PackagePrice,
    PackageProduct,
    PackageStatus,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/public/pricing"


def make(code: str, *products: str, status: str = PackageStatus.ACTIVE, **fields: Any) -> Package:
    package = Package.objects.create(
        code=code, name_i18n={"en-CA": code.title(), "fr-CA": f"{code.title()} FR"}, **fields
    )
    for product in products:
        PackageProduct.objects.create(package=package, product=Product.objects.get(code=product))
    if status != PackageStatus.DRAFT:
        package.status = PackageStatus.ACTIVE
        package.save()
        if status == PackageStatus.RETIRED:
            package.status = status
            package.save()
    return package


def price(package: Package, interval: str, cents: int, days: int, end: int | None = None) -> None:
    today = timezone.localdate()
    PackagePrice.objects.create(
        package=package,
        interval=interval,
        amount_cents=cents,
        effective_from=today + timedelta(days),
        effective_to=today + timedelta(end) if end is not None else None,
    )


@pytest.fixture
def catalogue() -> None:
    growth = make(
        "growth",
        "accounting",
        "tax",
        sort=2,
        is_founding_eligible=True,
        limits={"max_org_users": 10},
    )
    price(growth, "month", 3900, -30, 10)
    price(growth, "month", 4900, 10)
    price(growth, "year", 46800, -30)
    starter = make("starter", "accounting", sort=1)
    price(starter, "month", 1900, -30)
    make("draft", "accounting", status=PackageStatus.DRAFT)
    make("old", "accounting", status=PackageStatus.RETIRED)


def test_anyone_can_read_it(catalogue: None) -> None:
    response = APIClient().get(URL)
    assert response.status_code == 200
    assert response["Cache-Control"] == "public, max-age=60"


def test_active_packages_and_current_prices(catalogue: None) -> None:
    body = APIClient().get(URL).json()
    today = timezone.localdate()
    assert body["currency"] == "CAD" and body["tax_behaviour"] == "exclusive"
    assert body["as_of"] == today.isoformat()
    assert [p["code"] for p in body["packages"]] == ["starter", "growth"]  # display order
    growth = body["packages"][1]
    assert growth["name"] == "Growth"
    assert [p["code"] for p in growth["products"]] == ["accounting", "tax"]
    assert [p["code"] for p in growth["free_products"]] == ["practice", "portal"]
    assert growth["limits"] == {"max_org_users": 10}
    assert growth["founding_eligible"] is True
    month = growth["prices"]["month"]
    assert month["amount_cents"] == 3900 and month["currency"] == "CAD"
    assert month["next"] == {
        "amount_cents": 4900,
        "effective_from": (today + timedelta(10)).isoformat(),
    }
    assert growth["prices"]["year"]["amount_cents"] == 46800
    assert growth["prices"]["year"]["next"] is None
    starter = body["packages"][0]
    assert starter["prices"]["year"] is None  # not sold yearly
    assert starter["limits"] == {"max_org_users": None}
    assert body["founding_offer"] == {
        "eligible_packages": ["growth"],
        "total": None,
        "remaining": None,
    }


def test_excludes_draft_and_retired(catalogue: None) -> None:
    codes = {p["code"] for p in APIClient().get(URL).json()["packages"]}
    assert "draft" not in codes and "old" not in codes


def test_public_safe_fields_only(catalogue: None) -> None:
    text = str(APIClient().get(URL).json())
    for internal in ("public_id", "subscriber", "status", "created_at", "stripe", "'id'"):
        assert internal not in text


def test_response_is_cached_60_seconds(catalogue: None) -> None:
    client = APIClient()
    first = client.get(URL).json()
    Package.objects.filter(code="starter").update(status=PackageStatus.RETIRED)
    with mock.patch.object(public, "pricing", side_effect=AssertionError("not cached")):
        assert client.get(URL).json() == first  # served from the cache
    with mock.patch.object(cache, "set", wraps=cache.set) as setter:
        cache.clear()  # what 60 s of expiry does
        fresh = client.get(URL).json()
    assert [p["code"] for p in fresh["packages"]] == ["growth"]
    [(args, _kwargs)] = setter.call_args_list
    assert args[2] == 60


def test_cached_per_language(catalogue: None) -> None:
    client = APIClient()
    english = client.get(URL, HTTP_ACCEPT_LANGUAGE="en-CA").json()
    french = client.get(URL, HTTP_ACCEPT_LANGUAGE="fr-CA").json()
    assert english["packages"][1]["name"] == "Growth"
    assert french["packages"][1]["name"] == "Growth FR"


def test_no_packages_yet() -> None:
    body = APIClient().get(URL).json()
    assert body["packages"] == [] and body["founding_offer"]["eligible_packages"] == []
