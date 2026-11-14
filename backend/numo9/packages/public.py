"""Public pricing (U-02-T08): ``GET /api/v1/public/pricing`` — anyone, signed in or not.

What the website's Packages & Pricing page (Q-01) and the in-app comparison read: the packages
**offered** (active — never drafts or retired ones) in display order, each with its name and
description in the request's language, its products (chosen ones plus the free sets every
package includes), its limits, the founding-offer flag, and the price in force today per
interval (whole cents, CAD, before GST/HST) with the next scheduled change, if any.

``founding_offer`` names the eligible packages; the counter (``total``/``remaining``) arrives with
U-08 and is null until then.

The answer is the same for everyone, so it is cached for 60 seconds per language (server cache
and ``Cache-Control: public, max-age=60``): a change shows within a minute.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone, translation
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.models import Product, ProductKind
from numo9.catalogue.texts import product_name
from numo9.rbac.drf import PUBLIC, requires_permission

from .models import BillingInterval, Package, PackagePrice

CACHE_SECONDS = 60
CACHE_KEY = "packages:public-pricing:v1:{language}"


def _price(rows: list[PackagePrice], interval: str, today: date) -> dict[str, Any] | None:
    versions = sorted((p for p in rows if p.interval == interval), key=lambda p: p.effective_from)
    current = next((p for p in versions if p.covers(today)), None)
    if current is None:
        return None
    upcoming = next((p for p in versions if p.effective_from > today), None)
    return {
        "amount_cents": current.amount_cents,
        "currency": current.currency,
        "effective_from": current.effective_from.isoformat(),
        "next": (
            {
                "amount_cents": upcoming.amount_cents,
                "effective_from": upcoming.effective_from.isoformat(),
            }
            if upcoming is not None
            else None
        ),
    }


def pricing(today: date | None = None) -> dict[str, Any]:
    today = today or timezone.localdate()
    locale = translation.get_language() or "en-CA"
    free = [
        {"code": p.code, "name": product_name(p.code)}
        for p in Product.objects.filter(kind=ProductKind.FREE_SET).order_by("sort", "code")
    ]
    offered = (
        Package.objects.offered()
        .order_by("sort", "code")
        .prefetch_related("products", Prefetch("prices", queryset=PackagePrice.objects.all()))
    )
    packages = []
    for package in offered:
        prices = list(package.prices.all())
        packages.append(
            {
                "code": package.code,
                "name": package.name(locale),
                "description": package.description(locale),
                "products": [
                    {"code": p.code, "name": product_name(p.code)}
                    for p in sorted(package.products.all(), key=lambda p: (p.sort, p.code))
                ],
                "free_products": free,
                "limits": {"max_org_users": package.limit("max_org_users")},
                "founding_eligible": package.is_founding_eligible,
                "prices": {i: _price(prices, i, today) for i in BillingInterval.values},
            }
        )
    return {
        "currency": "CAD",
        "tax_behaviour": "exclusive",
        "as_of": today.isoformat(),
        "packages": packages,
        "founding_offer": {
            "eligible_packages": [p["code"] for p in packages if p["founding_eligible"]],
            "total": None,
            "remaining": None,
        },
    }


# ---- OpenAPI ----------------------------------------------------------------------------------


class NextPriceSerializer(serializers.Serializer[Any]):
    amount_cents = serializers.IntegerField()
    effective_from = serializers.DateField()


class PublicPriceSerializer(serializers.Serializer[Any]):
    amount_cents = serializers.IntegerField(help_text="Whole cents, before GST/HST")
    currency = serializers.CharField()
    effective_from = serializers.DateField()
    next = NextPriceSerializer(allow_null=True, help_text="The next scheduled price, if any")


class PublicPricesSerializer(serializers.Serializer[Any]):
    month = PublicPriceSerializer(allow_null=True)
    year = PublicPriceSerializer(allow_null=True)


class PublicProductSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()


class PublicLimitsSerializer(serializers.Serializer[Any]):
    max_org_users = serializers.IntegerField(allow_null=True, help_text="null = unlimited")


class PublicPackageSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    products = PublicProductSerializer(many=True)
    free_products = PublicProductSerializer(many=True)
    limits = PublicLimitsSerializer()
    founding_eligible = serializers.BooleanField()
    prices = PublicPricesSerializer()


class FoundingOfferSerializer(serializers.Serializer[Any]):
    eligible_packages = serializers.ListField(child=serializers.CharField())
    total = serializers.IntegerField(allow_null=True, help_text="U-08; null until then")
    remaining = serializers.IntegerField(allow_null=True, help_text="U-08; null until then")


class PublicPricingSerializer(serializers.Serializer[Any]):
    currency = serializers.CharField()
    tax_behaviour = serializers.CharField()
    as_of = serializers.DateField()
    packages = PublicPackageSerializer(many=True)
    founding_offer = FoundingOfferSerializer()


class PublicPricingView(APIView):
    authentication_classes: list[type] = []  # the same answer for everyone; no session needed

    @requires_permission(PUBLIC)
    @extend_schema(
        operation_id="public_pricing",
        summary="Packages offered, their products and current prices (cached 60 s)",
        responses=PublicPricingSerializer,
        auth=[],
    )
    def get(self, request: Request) -> Response:
        key = CACHE_KEY.format(language=translation.get_language() or "en-CA")
        body = cache.get(key)
        if body is None:
            body = PublicPricingSerializer(pricing()).data
            cache.set(key, body, CACHE_SECONDS)
        response = Response(body)
        response["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
        return response
