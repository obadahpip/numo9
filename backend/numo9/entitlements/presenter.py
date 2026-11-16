"""The entitlements bootstrap body (U-03-T09).

``entitlements_data(org)`` = the cached ``Entitlements`` plus the names the screens show, in the
request's language: every product's name and, for each product, the packages offered that include
it (the locked panel names them, gap-41). The names are cached per language and global version, so
a cached call reads two cache entries and runs no query.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.utils import translation

from numo9.catalogue.models import Product
from numo9.catalogue.packages import get_source as package_source
from numo9.catalogue.texts import product_name

from .cache import GLOBAL_VERSION, PREFIX, TTL, _version, entitlements_for, version

if TYPE_CHECKING:
    from numo9.tenancy.models import Organisation


def catalogue_names() -> dict[str, Any]:
    language = translation.get_language() or "en-ca"
    key = f"{PREFIX}:names:{language}:{_version(GLOBAL_VERSION)}"
    found = cache.get(key)
    if found is not None:
        names: dict[str, Any] = found
        return names
    by_product: dict[str, list[dict[str, str]]] = defaultdict(list)
    package_names: dict[str, str] = {}
    for package in package_source().packages():
        package_names[package.code] = package.name
        for code in sorted(package.products):
            by_product[code].append({"code": package.code, "name": package.name})
    names = {
        "product_names": {
            code: product_name(code) for code in Product.objects.values_list("code", flat=True)
        },
        "packages_by_product": dict(by_product),
        "package_names": package_names,
    }
    cache.set(key, names, timeout=TTL)
    return names


def entitlements_data(organisation: Organisation) -> dict[str, Any]:
    answer = entitlements_for(organisation)
    names = catalogue_names()
    body = answer.as_dict()
    valid_until = body.pop("valid_until")
    # Payment overdue (U-04-T13): the end of the grace period, for the payment-due notice.
    body["grace_until"] = valid_until if body.get("reason") == "past_due" else None
    package = answer.package
    body["package_name"] = names["package_names"].get(package, package) if package else None
    body["version"] = version(organisation)
    body.update(
        product_names=names["product_names"], packages_by_product=names["packages_by_product"]
    )
    return body
