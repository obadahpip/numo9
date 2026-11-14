"""Packages, prices and promo codes as the platform API shows them (U-02-T07).

The console works with codes (packages, products, promo codes) and public ids (price versions);
no database ids. Amounts are whole cents in CAD; dates ISO.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.utils import timezone, translation

from numo9.catalogue.texts import product_name

from .models import (
    BillingInterval,
    Package,
    PackagePrice,
    PackageStatus,
    PromoCode,
    PromoDuration,
    PromoKind,
    PromoStatus,
)
from .subscriptions import get_source

STATUS_LABELS = dict(PackageStatus.choices)
INTERVAL_LABELS = dict(BillingInterval.choices)
PROMO_KIND_LABELS = dict(PromoKind.choices)
PROMO_DURATION_LABELS = dict(PromoDuration.choices)
PROMO_STATUS_LABELS = dict(PromoStatus.choices)


def _locale() -> str:
    return translation.get_language() or "en-CA"


def price_state(price: PackagePrice, today: date) -> str:
    if price.covers(today):
        return "current"
    return "scheduled" if price.effective_from > today else "past"


def price_data(price: PackagePrice, today: date) -> dict[str, Any]:
    return {
        "id": str(price.public_id),
        "interval": price.interval,
        "interval_label": str(INTERVAL_LABELS.get(price.interval, price.interval)),
        "amount_cents": price.amount_cents,
        "currency": price.currency,
        "tax_behaviour": price.tax_behaviour,
        "effective_from": price.effective_from.isoformat(),
        "effective_to": price.effective_to.isoformat() if price.effective_to else None,
        "state": price_state(price, today),
    }


def package_data(package: Package, *, today: date | None = None) -> dict[str, Any]:
    today = today or timezone.localdate()
    locale = _locale()
    prices = sorted(package.prices.all(), key=lambda p: (p.interval, p.effective_from))
    current: dict[str, dict[str, Any] | None] = dict.fromkeys(BillingInterval.values)
    for price in prices:
        if price.covers(today):
            current[price.interval] = price_data(price, today)
    return {
        "code": package.code,
        "name": package.name(locale),
        "name_i18n": package.name_i18n,
        "description": package.description(locale),
        "description_i18n": package.description_i18n,
        "status": package.status,
        "status_label": str(STATUS_LABELS.get(package.status, package.status)),
        "is_founding_eligible": package.is_founding_eligible,
        "limits": {"max_org_users": package.limit("max_org_users")},
        "sort": package.sort,
        "products": [
            {"code": p.code, "name": product_name(p.code)}
            for p in sorted(package.products.all(), key=lambda p: (p.sort, p.code))
        ],
        "subscriber_count": get_source().count(package),
        "prices": [price_data(p, today) for p in prices],
        "current_prices": current,
        "today": today.isoformat(),
        "created_at": package.created_at.isoformat(),
        "updated_at": package.updated_at.isoformat(),
    }


def promo_data(promo: PromoCode) -> dict[str, Any]:
    now = timezone.now()
    status = promo.status_at(now)
    locale = _locale()
    return {
        "code": promo.code,
        "description": promo.description,
        "kind": promo.kind,
        "kind_label": str(PROMO_KIND_LABELS.get(promo.kind, promo.kind)),
        "percent_off": promo.percent_off,
        "amount_off_cents": promo.amount_off_cents,
        "currency": promo.currency,
        "duration": promo.duration,
        "duration_label": str(PROMO_DURATION_LABELS.get(promo.duration, promo.duration)),
        "duration_months": promo.duration_months,
        "max_redemptions": promo.max_redemptions,
        "redemptions_count": promo.redemptions_count,
        "expires_at": promo.expires_at.isoformat() if promo.expires_at else None,
        "packages": [
            {"code": p.code, "name": p.name(locale)}
            for p in sorted(promo.packages.all(), key=lambda p: (p.sort, p.code))
        ],
        "status": status,
        "status_label": str(PROMO_STATUS_LABELS.get(status, status)),
        "created_at": promo.created_at.isoformat(),
    }
