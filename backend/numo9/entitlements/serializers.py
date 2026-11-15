"""OpenAPI shape of the entitlements bootstrap (U-03-T09). The data comes from ``presenter``."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


class PackageNameSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()


class ViewerSerializer(serializers.Serializer[Any]):
    can_change_package = serializers.BooleanField(
        help_text="The organisation's owner: may change the package (accountants never)"
    )


class EntitlementsSerializer(serializers.Serializer[Any]):
    organisation = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=["full", "read_only", "none"])
    reason = serializers.CharField(
        help_text="full: trialing, active, past_due, demo, no_subscription; read_only: "
        "payment_failed, trial_ended, cancelled, platform, read_only"
    )
    since = serializers.DateTimeField(allow_null=True, help_text="Read-only since (read_only)")
    package = serializers.CharField(allow_null=True)
    package_name = serializers.CharField(allow_null=True)
    status = serializers.CharField(allow_null=True, help_text="Subscription status, if any")
    founding = serializers.BooleanField()
    products = serializers.ListField(child=serializers.CharField())
    read_products = serializers.ListField(
        child=serializers.CharField(), help_text="Kept for reading only (read retention)"
    )
    features = serializers.ListField(child=serializers.CharField())
    version = serializers.CharField(help_text="Cache version: changes when the answer may change")
    product_names = serializers.DictField(child=serializers.CharField())
    packages_by_product = serializers.DictField(child=PackageNameSerializer(many=True))
    time_zone = serializers.CharField(help_text="The organisation's time zone (banner dates)")
    viewer = ViewerSerializer()
