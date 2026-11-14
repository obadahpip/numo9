"""Package lifecycle (U-02-T05) and price changes (U-02-T07) — with the guards.

Status changes:

- ``draft → active`` — offered at sign-up; needs at least one product (the model refuses
  otherwise);
- ``active → retired`` — **hidden from sign-up and the pricing page; subscribers keep it**:
  retiring never touches a subscription (renewals continue at ``price_for`` as before). The
  only package offered at sign-up can't be retired (sign-up would offer nothing);
- ``retired → active`` — offered again.

Anything else (``active → draft``, ``draft → retired``) is refused (409). Deleting: only a draft
package, and never one with subscribers (409, "retire it instead") — ``Package.delete`` checks the
subscribers too, so no other path deletes a package in use.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from numo9.audit.service import record
from numo9.catalogue.models import Product
from numo9.i18n import errors
from numo9.i18n.errors import api_error, error_detail

from .models import (
    BillingInterval,
    Package,
    PackageError,
    PackagePrice,
    PackageProduct,
    PackageStatus,
)
from .subscriptions import get_source

_ALLOWED: dict[str, frozenset[str]] = {
    PackageStatus.DRAFT: frozenset({PackageStatus.ACTIVE}),
    PackageStatus.ACTIVE: frozenset({PackageStatus.RETIRED}),
    PackageStatus.RETIRED: frozenset({PackageStatus.ACTIVE}),
}


def _status_label(status: str) -> str:
    return str(dict(PackageStatus.choices).get(status, status)).lower()


def _change_status(package: Package, wanted: str) -> Package:
    with transaction.atomic():
        locked = Package.objects.select_for_update().get(pk=package.pk)
        if wanted == locked.status:
            return locked
        if wanted not in _ALLOWED.get(locked.status, frozenset()):
            raise api_error(
                errors.PACKAGE_STATUS_CHANGE,
                current=_status_label(locked.status),
                wanted=_status_label(wanted),
            )
        if (
            wanted == PackageStatus.RETIRED
            and not Package.objects.offered().exclude(pk=locked.pk).exists()
        ):
            raise api_error(errors.PACKAGE_LAST_OFFERED, package=locked.name())
        locked.status = wanted
        try:
            locked.save()
        except PackageError as refused:
            if refused.code == "packages.no_products":
                raise api_error(errors.PACKAGE_NO_PRODUCTS) from refused
            raise
    return locked


def activate(package: Package, *, actor: Any = None) -> Package:
    """Offer the package at sign-up (draft or retired → active); its prices go to Stripe."""
    from .stripe_sync import request_sync  # the job module imports this app's models

    activated = _change_status(package, PackageStatus.ACTIVE)
    request_sync(actor=actor)
    return activated


def retire(package: Package, *, actor: Any = None) -> Package:
    """Hide the package from sign-up; its subscribers keep it (active → retired)."""
    return _change_status(package, PackageStatus.RETIRED)


def subscriber_count(package: Package) -> int:
    return get_source().count(package)


def delete_package(package: Package, *, actor: Any = None) -> None:
    """Delete a draft package nobody subscribes to (its products and prices go with it)."""
    count = subscriber_count(package)
    if count:
        raise api_error(errors.PACKAGE_IN_USE, package=package.name(), count=count)
    if package.status != PackageStatus.DRAFT:
        raise api_error(errors.PACKAGE_DELETE_NOT_DRAFT, package=package.name())
    package.delete()


# ---- prices (U-02-T07) ------------------------------------------------------------------------


def schedule_price(
    package: Package,
    *,
    interval: str,
    amount_cents: int,
    effective_from: date,
    actor: Any = None,
    today: date | None = None,
) -> PackagePrice:
    """Add a price version starting on ``effective_from``; the version in force then ends there.

    A change is always a new version (Stripe prices are immutable). It starts today or later —
    except on a draft package, which has never been sold — and after every existing version of
    that interval (to change a scheduled price, delete it first). Subscriptions renew at the new
    price only at a renewal on or after its start date (``price_for``).
    """
    today = today or timezone.localdate()
    with transaction.atomic():
        # one price change at a time per package; the stored status decides (not a stale copy)
        package = Package.objects.select_for_update().get(pk=package.pk)
        if package.status != PackageStatus.DRAFT and effective_from < today:
            raise serializers.ValidationError(
                {"effective_from": [error_detail(errors.PRICE_IN_PAST)]}
            )
        versions = PackagePrice.objects.filter(package=package, interval=interval)
        later = versions.filter(effective_from__gte=effective_from).order_by("-effective_from")
        if latest := later.first():
            raise serializers.ValidationError(
                {
                    "effective_from": [
                        error_detail(
                            errors.PRICE_NOT_LATEST,
                            interval=_interval_label(interval).lower(),
                            date=latest.effective_from.isoformat(),
                        )
                    ]
                }
            )
        previous = (
            versions.filter(effective_from__lt=effective_from)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=effective_from))
            .first()
        )
        if previous is not None:
            previous.effective_to = effective_from
            previous.save()
        created: PackagePrice = PackagePrice.objects.create(
            package=package,
            interval=interval,
            amount_cents=amount_cents,
            effective_from=effective_from,
        )
        # One readable line for the change: the price before and after the new start (U-02-T13).
        record(
            "packages.price.scheduled",
            obj=created,
            organisation=None,
            object_label=f"{package.code} · {_interval_label(interval).lower()}",
            changes={
                "amount_cents": [previous.amount_cents if previous else None, amount_cents],
                "effective_from": [
                    previous.effective_from.isoformat() if previous else None,
                    effective_from.isoformat(),
                ],
            },
            meta={
                "package": package.code,
                "interval": interval,
                "previous_price": str(previous.public_id) if previous else None,
            },
            actor=actor,
        )
        if package.status != PackageStatus.DRAFT:
            from .stripe_sync import request_sync

            request_sync(key=f"price:{created.public_id}", actor=actor)
    return created


def delete_scheduled_price(
    price: PackagePrice, *, actor: Any = None, today: date | None = None
) -> None:
    """Delete a version that hasn't started; the version before it is in force again after."""
    today = today or timezone.localdate()
    if price.effective_from <= today:
        raise api_error(errors.PRICE_STARTED)
    with transaction.atomic():
        Package.objects.select_for_update().get(pk=price.package_id)
        previous = PackagePrice.objects.filter(
            package_id=price.package_id,
            interval=price.interval,
            effective_to=price.effective_from,
        ).first()
        end = price.effective_to
        record(
            "packages.price.unscheduled",
            obj=price,
            organisation=None,
            object_label=f"{price.package.code} · {_interval_label(price.interval).lower()}",
            changes={
                "amount_cents": [price.amount_cents, previous.amount_cents if previous else None],
                "effective_from": [price.effective_from.isoformat(), None],
            },
            meta={"package": price.package.code, "interval": price.interval},
            actor=actor,
        )
        price.delete()
        if previous is not None:
            previous.effective_to = end
            previous.save()


def _interval_label(interval: str) -> str:
    return str(dict(BillingInterval.choices).get(interval, interval))


# ---- editing (U-02-T07) -----------------------------------------------------------------------


def field_errors(
    error: ValidationError, rename: dict[str, str] | None = None
) -> serializers.ValidationError:
    """A model ``ValidationError`` in the API's field form ``{"field": ["message"]}``."""
    rename = rename or {}
    if hasattr(error, "error_dict"):
        body: dict[str, list[ErrorDetail]] = {}
        for field, items in error.error_dict.items():
            key = rename.get(field, field)
            for item in items:
                text = item.message % item.params if item.params else item.message
                body.setdefault(key, []).append(ErrorDetail(str(text), code=item.code))
        return serializers.ValidationError(body)
    texts = [ErrorDetail(str(e.message), code=e.code) for e in error.error_list]
    return serializers.ValidationError({"non_field_errors": texts})


def _products(codes: list[str]) -> list[Product]:
    wanted = list(dict.fromkeys(codes))
    found = {p.code: p for p in Product.objects.filter(code__in=wanted)}
    missing = [code for code in wanted if code not in found]
    if missing:
        raise serializers.ValidationError(
            {
                "products": [
                    error_detail(errors.PACKAGE_UNKNOWN_PRODUCT, product=code) for code in missing
                ]
            }
        )
    return [found[code] for code in wanted]


def set_products(package: Package, codes: list[str]) -> None:
    """Make the package's products exactly ``codes`` (new ones first: an active package never
    goes without one)."""
    products = _products(codes)
    wanted = {p.pk for p in products}
    current = {link.product_id: link for link in package.package_products.all()}
    try:
        for product in products:
            if product.pk not in current:
                PackageProduct.objects.create(package=package, product=product)
        for product_id, link in current.items():
            if product_id not in wanted:
                link.delete()
    except PackageError as refused:
        raise field_errors(refused, {"product": "products"}) from refused


def _apply(package: Package, data: dict[str, Any]) -> None:
    for field in ("name_i18n", "description_i18n", "is_founding_eligible", "sort"):
        if field in data:
            setattr(package, field, data[field])
    if "limits" in data:
        package.limits = {**(package.limits or {}), **data["limits"]}


def create_package(data: dict[str, Any], *, actor: Any = None) -> Package:
    """A new draft package with its products."""
    code = data["code"].strip()
    if Package.objects.filter(code=code).exists():
        raise serializers.ValidationError(
            {"code": [error_detail(errors.PACKAGE_CODE_TAKEN, code=code)]}
        )
    with transaction.atomic():
        package = Package(code=code)
        _apply(package, data)
        try:
            package.save()
        except PackageError as refused:
            raise field_errors(refused) from refused
        set_products(package, data.get("products", []))
    return package


def update_package(package: Package, data: dict[str, Any], *, actor: Any = None) -> Package:
    """Change texts, products, limits, founding flag or order (never the code or status)."""
    with transaction.atomic():
        package = Package.objects.select_for_update().get(pk=package.pk)
        _apply(package, data)
        try:
            package.save()
        except PackageError as refused:
            raise field_errors(refused) from refused
        if "products" in data:
            set_products(package, data["products"])
    return package
