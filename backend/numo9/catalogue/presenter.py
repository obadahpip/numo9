"""Catalogue data as the API, the exports and the screens show it (U-01-T09, T10).

Public-safe fields only: codes, translated names and descriptions, kinds, statuses, the key →
product → packages mapping. No database ids, no timestamps, no internal notes.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Prefetch

from .models import FeatureKey, Product, ProductKind, ProductStatus
from .packages import PackageRef, get_source
from .texts import text_for

KIND_LABELS = dict(ProductKind.choices)
STATUS_LABELS = dict(ProductStatus.choices)


def product_data(product: Product, *, features: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "code": product.code,
        "name": text_for(product.name_i18n_key, product.code),
        "name_i18n_key": product.name_i18n_key,
        "kind": product.kind,
        "kind_label": str(KIND_LABELS.get(product.kind, product.kind)),
        "status": product.status,
        "status_label": str(STATUS_LABELS.get(product.status, product.status)),
        "billable": product.kind != ProductKind.FREE_SET,
        "sort": product.sort,
        "feature_count": getattr(product, "feature_count", None),
    }
    if features:
        data["features"] = [feature_data(f) for f in product.feature_keys.all()]
        data["feature_count"] = len(data["features"])
    elif data["feature_count"] is None:
        data["feature_count"] = product.feature_keys.count()
    return data


def feature_data(feature: FeatureKey) -> dict[str, Any]:
    return {
        "key": feature.key,
        "description": text_for(feature.description_i18n_key, feature.key),
        "description_i18n_key": feature.description_i18n_key,
        "area": feature.area,
        "action": feature.action,
        "is_read_only": feature.is_read_only,
    }


def products(*, features: bool = False) -> list[dict[str, Any]]:
    queryset = Product.objects.order_by("sort", "code")
    if features:
        keys = FeatureKey.objects.order_by("sort", "key")
        queryset = queryset.prefetch_related(Prefetch("feature_keys", queryset=keys))
    else:
        queryset = queryset.annotate(feature_count=Count("feature_keys"))
    return [product_data(p, features=features) for p in queryset]


def package_data(package: PackageRef) -> dict[str, Any]:
    return {"code": package.code, "name": package.name, "products": sorted(package.products)}


def feature_matrix() -> dict[str, Any]:
    """Every feature key once: its product and the packages that include that product."""
    packages = get_source().packages()
    rows = []
    for feature in FeatureKey.objects.select_related("product").order_by(
        "product__sort", "product__code", "sort", "key"
    ):
        code = feature.product.code
        rows.append(
            {
                **feature_data(feature),
                "product": code,
                "product_name": text_for(feature.product.name_i18n_key, code),
                "packages": [p.code for p in packages if code in p.products],
            }
        )
    return {
        "products": products(),
        "packages": [package_data(p) for p in packages],
        "features": rows,
    }
