"""OpenAPI shapes of the catalogue API (U-01-T09). The data comes from ``presenter``."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import ProductKind, ProductStatus


class FeatureSerializer(serializers.Serializer[Any]):
    key = serializers.CharField(help_text="<product>.<area>.<action>")
    description = serializers.CharField(help_text="Plain language, in the request's language")
    description_i18n_key = serializers.CharField()
    area = serializers.CharField()
    action = serializers.ChoiceField(choices=["read", "write", "approve"])
    is_read_only = serializers.BooleanField()


class ProductSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()
    name_i18n_key = serializers.CharField()
    kind = serializers.ChoiceField(choices=ProductKind.choices)
    kind_label = serializers.CharField()
    status = serializers.ChoiceField(choices=ProductStatus.choices)
    status_label = serializers.CharField()
    billable = serializers.BooleanField(help_text="False for free product sets")
    sort = serializers.IntegerField()
    feature_count = serializers.IntegerField()


class ProductDetailSerializer(ProductSerializer):
    features = FeatureSerializer(many=True)


class ProductListSerializer(serializers.Serializer[Any]):
    products = ProductDetailSerializer(many=True)


class PackageSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    name = serializers.CharField()
    products = serializers.ListField(child=serializers.CharField())


class MatrixRowSerializer(FeatureSerializer):
    product = serializers.CharField()
    product_name = serializers.CharField()
    packages = serializers.ListField(
        child=serializers.CharField(), help_text="Codes of the packages that include the product"
    )


class FeatureMatrixSerializer(serializers.Serializer[Any]):
    products = ProductSerializer(many=True)
    packages = PackageSerializer(many=True, help_text="Empty until U-02 (packages) ships")
    features = MatrixRowSerializer(many=True, help_text="Every feature key once")


class OrganisationMatrixSerializer(FeatureMatrixSerializer):
    current_package = serializers.CharField(
        allow_null=True, help_text="Code of the organisation's package; null before U-03/U-04"
    )
