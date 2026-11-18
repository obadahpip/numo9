"""Entitlement engine (U-03-T04, T05; ADR-0004).

``resolve_entitlements(org, now)`` answers, in one call, what an organisation may use now:

    Entitlements(mode="full", reason="active", products={"accounting", "practice", "portal"},
                 features={"accounting.contacts.read", "accounting.contacts.write", …}, …)

**Mode** (``full`` / ``read_only`` / ``none``) and **reason** come from the organisation's current
subscription (``models.current_subscription``):

=========================================  ===========  =======================================
Subscription                               Mode         Reason
=========================================  ===========  =======================================
``trialing``                               full         ``trialing``
``active``                                 full         ``active``
``past_due`` until ``grace_until``         full         ``past_due``
``past_due`` after ``grace_until``         read_only    ``payment_failed`` (since grace end)
``read_only``                              read_only    its ``status_reason`` (else ``read_only``)
``cancelled``                              read_only    ``cancelled`` (read and export only)
``demo``                                   full         ``demo``
none — ``Organisation.status`` demo        full         ``demo``
none — read_only / cancelled               read_only    the organisation's status
none — otherwise (self sign-up)            full         ``no_subscription`` (trial)
no organisation                            none         ``no_organisation``
=========================================  ===========  =======================================

**Products** entitled: the subscription's package (``trialing`` / ``demo`` / no subscription
without a package: ``settings.NUMO9_TRIAL_PACKAGE`` / ``NUMO9_DEMO_PACKAGE``, else every active
product), plus every active product when ``founding`` (U-08 — products that ship later included),
plus ``override["products"]``, plus each unexpired ``EntitlementOverride``, plus the free sets
(Practice, Client portal — in every package). Planned products are never entitled (not shipped).

**Features**: in ``full`` mode every key of the entitled products; in ``read_only`` mode only their
``*.read`` keys. **Read retention** (T05): every product entitled in ``full`` mode is recorded in
``OrgProductHistory``; a product in the history that is no longer entitled keeps its ``*.read``
keys (``read_products``) — after a downgrade Payroll read = true, write = false. Approval inside a
product is part of the product (``accounting.*.approve``), never sold separately (gap-06).

Practice users acting inside an organisation get the organisation's answer: the engine never
looks at the user. ``valid_until`` is the next moment the answer changes on its own (grace end, an
override expiring): the cache (``cache.py``) never keeps an answer past it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone

from numo9.catalogue.models import FeatureKey, Product, ProductKind, ProductStatus
from numo9.packages.models import Package, PackageStatus
from numo9.tenancy.models import OrganisationStatus

from .models import (
    OrgProductHistory,
    StatusReason,
    Subscription,
    SubscriptionStatus,
    active_overrides,
    current_subscription,
)

if TYPE_CHECKING:
    from numo9.tenancy.models import Organisation

FULL = "full"
READ_ONLY = "read_only"
NONE = "none"
MODES: tuple[str, ...] = (FULL, READ_ONLY, NONE)

#: Reasons of the ``full`` and ``none`` modes (``read_only`` reasons are ``StatusReason`` values,
#: ``read_only`` or ``cancelled``).
NO_SUBSCRIPTION = "no_subscription"
NO_ORGANISATION = "no_organisation"


@dataclass(frozen=True)
class Entitlements:
    mode: str
    reason: str
    #: Products the organisation is entitled to now (write in ``full`` mode).
    products: frozenset[str] = frozenset()
    #: Products kept for reading only: in the history but not entitled now (T05).
    read_products: frozenset[str] = frozenset()
    features: frozenset[str] = frozenset()
    #: Since when the organisation is read-only (``read_only`` mode), else None.
    since: datetime | None = None
    #: Package code (the subscription's, or the trial/demo package), None when none applies.
    package: str | None = None
    #: Subscription status, None without a subscription.
    status: str | None = None
    founding: bool = False
    #: Next moment the answer changes by itself (grace end, an override expiring).
    valid_until: datetime | None = None
    organisation_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict, compare=False)

    def allows(self, key: str) -> bool:
        return key in self.features

    @property
    def is_read_only(self) -> bool:
        return self.mode == READ_ONLY

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe form (the cache and the bootstrap API)."""
        return {
            "organisation": self.organisation_id,
            "mode": self.mode,
            "reason": self.reason,
            "since": self.since.isoformat() if self.since else None,
            "package": self.package,
            "status": self.status,
            "founding": self.founding,
            "products": sorted(self.products),
            "read_products": sorted(self.read_products),
            "features": sorted(self.features),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entitlements:
        def moment(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        return cls(
            mode=data["mode"],
            reason=data["reason"],
            products=frozenset(data["products"]),
            read_products=frozenset(data["read_products"]),
            features=frozenset(data["features"]),
            since=moment(data["since"]),
            package=data["package"],
            status=data["status"],
            founding=data["founding"],
            valid_until=moment(data["valid_until"]),
            organisation_id=data["organisation"],
        )


# ---- catalogue reads ---------------------------------------------------------------------------


def _shipped_products() -> dict[str, Product]:
    """Products that can be entitled: not planned (active or retired)."""
    rows = Product.objects.exclude(status=ProductStatus.PLANNED)
    return {p.code: p for p in rows}


def _features_by_product() -> dict[str, tuple[list[str], list[str]]]:
    """product code → (every key, read keys)."""
    out: dict[str, tuple[list[str], list[str]]] = defaultdict(lambda: ([], []))
    for key, product, read_only in FeatureKey.objects.values_list(
        "key", "product__code", "is_read_only"
    ):
        out[product][0].append(key)
        if read_only:
            out[product][1].append(key)
    return out


def _package_products(package: Package | None) -> set[str]:
    if package is None:
        return set()
    return set(package.products.values_list("code", flat=True))


def _configured_package(setting: str) -> Package | None:
    code = getattr(settings, setting, "") or ""
    if not code:
        return None
    found: Package | None = (
        Package.objects.filter(code=code).exclude(status=PackageStatus.DRAFT).first()
    )
    return found


# ---- resolution --------------------------------------------------------------------------------


def _mode_and_reason(
    organisation: Organisation, subscription: Subscription | None, now: datetime
) -> tuple[str, str, datetime | None, datetime | None]:
    """(mode, reason, since, valid_until) of the organisation's state."""
    if subscription is None:
        status = organisation.status
        if status in (OrganisationStatus.READ_ONLY, OrganisationStatus.CANCELLED):
            return READ_ONLY, str(status), organisation.updated_at, None
        if status == OrganisationStatus.DEMO:
            return FULL, SubscriptionStatus.DEMO.value, None, None
        return FULL, NO_SUBSCRIPTION, None, None
    status = subscription.status
    if status == SubscriptionStatus.PAST_DUE:
        grace = subscription.grace_until
        if grace is not None and now >= grace:  # grace over, even before the job flips it
            return READ_ONLY, StatusReason.PAYMENT_FAILED.value, grace, None
        return FULL, status, None, grace
    if status == SubscriptionStatus.TRIALING:
        end = subscription.current_period_end
        if end is not None and now > end:  # trial over, even before the expiry job flips it
            return READ_ONLY, StatusReason.TRIAL_ENDED.value, end, None
        return FULL, status, None, end
    if status == SubscriptionStatus.READ_ONLY:
        reason = subscription.status_reason or SubscriptionStatus.READ_ONLY.value
        if reason == StatusReason.PAYMENT_FAILED and subscription.grace_until is not None:
            return READ_ONLY, reason, subscription.grace_until, None
        return READ_ONLY, reason, subscription.status_changed_at, None
    if status == SubscriptionStatus.CANCELLED:
        return READ_ONLY, SubscriptionStatus.CANCELLED.value, subscription.status_changed_at, None
    return FULL, status, None, None


def resolve_entitlements(
    organisation: Organisation | None, now: datetime | None = None, *, record: bool = True
) -> Entitlements:
    """What ``organisation`` may use at ``now`` (uncached; ``cache.entitlements_for`` caches it).

    ``record`` writes the products entitled in ``full`` mode to the history (read retention).
    """
    now = now or timezone.now()
    if organisation is None:
        return Entitlements(mode=NONE, reason=NO_ORGANISATION)
    subscription = current_subscription(organisation)
    mode, reason, since, valid_until = _mode_and_reason(organisation, subscription, now)

    shipped = _shipped_products()
    active = {code for code, p in shipped.items() if p.status == ProductStatus.ACTIVE}
    free = {code for code in active if shipped[code].kind == ProductKind.FREE_SET}

    package: Package | None = subscription.package if subscription else None
    if package is None:
        trial_like = subscription is None or subscription.status in (
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.DEMO,
        )
        if trial_like:
            demo = (
                subscription is not None and subscription.status == SubscriptionStatus.DEMO
            ) or (subscription is None and organisation.status == OrganisationStatus.DEMO)
            package = _configured_package("NUMO9_DEMO_PACKAGE" if demo else "NUMO9_TRIAL_PACKAGE")
            products = _package_products(package) if package is not None else set(active)
        else:
            products = set()
    else:
        products = _package_products(package)

    founding = bool(subscription and subscription.founding)
    if founding:
        products |= active
    if subscription is not None:
        products |= set(subscription.extra_products)
    for grant in active_overrides(organisation, now):
        products.add(grant.product.code)
        if valid_until is None or grant.expires_at < valid_until:
            valid_until = grant.expires_at
    products |= free
    products &= set(shipped)  # planned products are never entitled

    if record and mode == FULL:
        _record_history(organisation, products, now)
    history = set(
        OrgProductHistory._base_manager.filter(organisation_id=organisation.pk).values_list(
            "product__code", flat=True
        )
    )
    keys = _features_by_product()
    features: set[str] = set()
    for code in products:
        every, reads = keys.get(code, ([], []))
        features.update(every if mode == FULL else reads)
    read_products = (history - products) & set(shipped)
    for code in read_products:
        features.update(keys.get(code, ([], []))[1])

    return Entitlements(
        mode=mode,
        reason=reason,
        products=frozenset(products),
        read_products=frozenset(read_products),
        features=frozenset(features),
        since=since,
        package=package.code if package is not None else None,
        status=subscription.status if subscription is not None else None,
        founding=founding,
        valid_until=valid_until,
        organisation_id=str(organisation.public_id),
    )


def _record_history(organisation: Organisation, products: set[str], now: datetime) -> None:
    """Remember every product entitled now (T05): insert the new ones, touch the others."""
    ids = dict(Product.objects.filter(code__in=products).values_list("code", "pk"))
    rows = OrgProductHistory._base_manager.filter(organisation_id=organisation.pk)
    known = set(rows.values_list("product_id", flat=True))
    missing = [pk for pk in ids.values() if pk not in known]
    if missing:
        OrgProductHistory._base_manager.bulk_create(
            [
                OrgProductHistory(
                    organisation_id=organisation.pk,
                    product_id=pk,
                    first_entitled_at=now,
                    last_entitled_at=now,
                )
                for pk in missing
            ],
            ignore_conflicts=True,
        )
    rows.filter(product_id__in=list(ids.values()), last_entitled_at__lt=now).update(
        last_entitled_at=now
    )


class Engine:
    """``settings.NUMO9_ENTITLEMENT_RESOLVER`` (U-01-T05 interface): cached, per organisation."""

    def allows(self, organisation: Organisation | None, key: str) -> bool:
        from numo9.catalogue.drf import CORE

        if key == CORE:
            return True
        from .cache import entitlements_for

        return entitlements_for(organisation).allows(key)
