"""Request validation and OpenAPI shapes of the packages API (U-02-T07, T08).

Request serializers check types and ranges; the models check the business rules (codes, texts,
limits, activation…) and their messages come back in the same field form
(``{"field": ["message"]}``).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import (
    DESCRIPTION_MAX,
    LIMIT_MAX,
    NAME_MAX,
    BillingInterval,
    PackageStatus,
    PromoDuration,
    PromoKind,
    PromoStatus,
)

AMOUNT_MAX = 10_000_000  # $100,000.00

PRICE_STATES = [("past", "past"), ("current", "current"), ("scheduled", "scheduled")]


def texts_field(max_length: int, *, required: bool = True) -> serializers.DictField:
    return serializers.DictField(
        child=serializers.CharField(allow_blank=True, max_length=max_length, trim_whitespace=True),
        required=required,
        help_text='Text per language: {"en-CA": "…", "fr-CA": "…"}',
    )


# ---- requests ---------------------------------------------------------------------------------


class LimitsInputSerializer(serializers.Serializer[Any]):
    max_org_users = serializers.IntegerField(
        min_value=1,
        max_value=LIMIT_MAX,
        allow_null=True,
        required=False,
        help_text="Organisation users; null = unlimited (practice users never count)",
    )


class PackageUpdateSerializer(serializers.Serializer[Any]):
    name_i18n = texts_field(NAME_MAX)
    description_i18n = texts_field(DESCRIPTION_MAX, required=False)
    products = serializers.ListField(
        child=serializers.CharField(max_length=40),
        required=False,
        help_text="Product codes (billable, active); free sets are part of every package",
    )
    limits = LimitsInputSerializer(required=False)
    is_founding_eligible = serializers.BooleanField(required=False)
    sort = serializers.IntegerField(min_value=0, max_value=10_000, required=False)


class PackageCreateSerializer(PackageUpdateSerializer):
    code = serializers.CharField(max_length=40, help_text="growth — never changes once created")


class PriceCreateSerializer(serializers.Serializer[Any]):
    interval = serializers.ChoiceField(choices=BillingInterval.choices)
    amount_cents = serializers.IntegerField(
        min_value=0, max_value=AMOUNT_MAX, help_text="Whole cents in CAD, before GST/HST"
    )
    effective_from = serializers.DateField(help_text="First day the price applies")


class PriceImpactQuerySerializer(serializers.Serializer[Any]):
    interval = serializers.ChoiceField(choices=BillingInterval.choices)
    effective_from = serializers.DateField()


class PromoUpdateSerializer(serializers.Serializer[Any]):
    description = serializers.CharField(max_length=200, allow_blank=True, required=False)
    max_redemptions = serializers.IntegerField(
        min_value=1, max_value=1_000_000, allow_null=True, required=False
    )
    expires_at = serializers.DateTimeField(allow_null=True, required=False)
    packages = serializers.ListField(
        child=serializers.CharField(max_length=40),
        required=False,
        help_text="Package codes the code applies to; empty = every package",
    )


class PromoCreateSerializer(PromoUpdateSerializer):
    code = serializers.CharField(max_length=40)
    kind = serializers.ChoiceField(choices=PromoKind.choices)
    percent_off = serializers.IntegerField(
        min_value=1, max_value=100, allow_null=True, required=False
    )
    amount_off_cents = serializers.IntegerField(
        min_value=1, max_value=AMOUNT_MAX, allow_null=True, required=False
    )
    duration = serializers.ChoiceField(choices=PromoDuration.choices)
    duration_months = serializers.IntegerField(
        min_value=1, max_value=36, allow_null=True, required=False
    )


# ---- responses (OpenAPI) ----------------------------------------------------------------------


class PackagePriceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    interval = serializers.ChoiceField(choices=BillingInterval.choices)
    interval_label = serializers.CharField()
    amount_cents = serializers.IntegerField()
    currency = serializers.CharField()
    tax_behaviour = serializers.CharField()
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(allow_null=True)
    state = serializers.ChoiceField(choices=PRICE_STATES)


class CurrentPricesSerializer(serializers.Serializer[Any]):
    month = PackagePriceSerializer(allow_null=True)
    year = PackagePriceSerializer(allow_null=True)


class NamedCodeSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()


class LimitsSerializer(serializers.Serializer[Any]):
    max_org_users = serializers.IntegerField(allow_null=True)


class PlatformPackageSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()
    name_i18n = serializers.DictField(child=serializers.CharField())
    description = serializers.CharField()
    description_i18n = serializers.DictField(child=serializers.CharField())
    status = serializers.ChoiceField(choices=PackageStatus.choices)
    status_label = serializers.CharField()
    is_founding_eligible = serializers.BooleanField()
    limits = LimitsSerializer()
    sort = serializers.IntegerField()
    products = NamedCodeSerializer(many=True)
    subscriber_count = serializers.IntegerField(
        help_text="Subscriptions that haven't ended (0 until U-03/U-04)"
    )
    prices = PackagePriceSerializer(many=True)
    current_prices = CurrentPricesSerializer()
    today = serializers.DateField(help_text="Today in the platform's time zone")
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class PlatformPackageListSerializer(serializers.Serializer[Any]):
    packages = PlatformPackageSerializer(many=True)


class PriceImpactSerializer(serializers.Serializer[Any]):
    affected_subscriptions = serializers.IntegerField(
        help_text="Subscriptions renewing at this price at their next renewal on or after the date"
    )
    current = PackagePriceSerializer(
        allow_null=True, help_text="The price in force before that date"
    )


class PriceCreatedSerializer(serializers.Serializer[Any]):
    price = PackagePriceSerializer()
    affected_subscriptions = serializers.IntegerField()
    package = PlatformPackageSerializer()


class PromoSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    description = serializers.CharField()
    kind = serializers.ChoiceField(choices=PromoKind.choices)
    kind_label = serializers.CharField()
    percent_off = serializers.IntegerField(allow_null=True)
    amount_off_cents = serializers.IntegerField(allow_null=True)
    currency = serializers.CharField()
    duration = serializers.ChoiceField(choices=PromoDuration.choices)
    duration_label = serializers.CharField()
    duration_months = serializers.IntegerField(allow_null=True)
    max_redemptions = serializers.IntegerField(allow_null=True)
    redemptions_count = serializers.IntegerField()
    expires_at = serializers.DateTimeField(allow_null=True)
    packages = NamedCodeSerializer(many=True)
    status = serializers.ChoiceField(choices=PromoStatus.choices)
    status_label = serializers.CharField()
    created_at = serializers.DateTimeField()


class PromoListSerializer(serializers.Serializer[Any]):
    promo_codes = PromoSerializer(many=True)
