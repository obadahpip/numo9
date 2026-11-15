"""Entitlement cache (U-03-T06; ADR-0004): versioned keys, invalidated by saves — no TTL wait.

``entitlements_for(org)`` returns the cached ``Entitlements`` of an organisation, resolving and
storing them on a miss. The key carries two counters:

    ent:{org public id}:{org version}.{global version}

- the **organisation version** goes up when one of its ``Subscription`` or
  ``EntitlementOverride`` rows (or the ``Organisation`` itself) is saved or deleted;
- the **global version** goes up when a ``Package``, ``PackageProduct``, ``Product`` or
  ``FeatureKey`` changes (every organisation's answer may change).

A bump makes the next call build a new key, so the change is visible on the next request — the
old entry is simply never read again and expires (``TTL``). Bumps run at once and again when the
transaction commits, so a reader that cached the old rows during the transaction is outrun.
An answer never outlives its ``valid_until`` (grace end, override expiry): the entry's timeout
stops there. The cache is Django's default cache — Redis in staging and production.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.utils import timezone

from .engine import Entitlements, resolve_entitlements

if TYPE_CHECKING:
    from numo9.tenancy.models import Organisation

TTL = 60 * 60  # seconds: old versions are never read again; this only frees the memory
PREFIX = "ent"
GLOBAL_VERSION = f"{PREFIX}:gver"


def _org_version_key(org_id: str) -> str:
    return f"{PREFIX}:ver:{org_id}"


def _version(key: str) -> int:
    cache.add(key, 1, timeout=None)
    value = cache.get(key)
    return int(value) if value is not None else 1


def _bump(key: str) -> None:
    try:
        cache.incr(key)
    except ValueError:  # not in the cache (never read, or evicted): any new value is fresh
        cache.set(key, _version(key) + 1, timeout=None)


def version(organisation: Organisation) -> str:
    return f"{_version(_org_version_key(str(organisation.public_id)))}.{_version(GLOBAL_VERSION)}"


def cache_key(organisation: Organisation) -> str:
    return f"{PREFIX}:{organisation.public_id}:{version(organisation)}"


def bump_organisation(org_public_id: str) -> None:
    key = _org_version_key(org_public_id)
    _bump(key)
    transaction.on_commit(lambda: _bump(key))


def bump_global() -> None:
    _bump(GLOBAL_VERSION)
    transaction.on_commit(lambda: _bump(GLOBAL_VERSION))


def _timeout(answer: Entitlements, now: datetime) -> int:
    if answer.valid_until is None:
        return TTL
    left = int((answer.valid_until - now).total_seconds())
    return max(1, min(TTL, left))


def entitlements_for(
    organisation: Organisation | None, now: datetime | None = None
) -> Entitlements:
    """The organisation's entitlements, from the cache when fresh (see the module docstring)."""
    if organisation is None:
        return resolve_entitlements(None)
    moment = now or timezone.now()
    key = cache_key(organisation)
    stored = cache.get(key)
    if stored is not None:
        answer = Entitlements.from_dict(stored)
        if answer.valid_until is None or moment < answer.valid_until:
            return answer
    answer = resolve_entitlements(organisation, moment)
    cache.set(key, answer.as_dict(), timeout=_timeout(answer, moment))
    return answer


# ---- invalidation signals ----------------------------------------------------------------------


def _organisation_row(sender: Any, instance: Any, **kwargs: Any) -> None:
    if kwargs.get("raw"):
        return
    organisation = getattr(instance, "organisation", None)
    if organisation is not None:
        bump_organisation(str(organisation.public_id))


def _organisation_itself(sender: Any, instance: Any, **kwargs: Any) -> None:
    if not kwargs.get("raw"):
        bump_organisation(str(instance.public_id))


def _catalogue_row(sender: Any, instance: Any, **kwargs: Any) -> None:
    if not kwargs.get("raw"):
        bump_global()


def connect_signals() -> None:
    from numo9.catalogue.models import FeatureKey, Product
    from numo9.packages.models import Package, PackageProduct
    from numo9.tenancy.models import Organisation

    from .models import EntitlementOverride, Subscription

    for model in (Subscription, EntitlementOverride):
        uid = f"entitlements_bump_{model._meta.label_lower}"
        post_save.connect(_organisation_row, sender=model, dispatch_uid=f"{uid}_save")
        post_delete.connect(_organisation_row, sender=model, dispatch_uid=f"{uid}_delete")
    post_save.connect(
        _organisation_itself, sender=Organisation, dispatch_uid="entitlements_bump_organisation"
    )
    for catalogue_model in (Package, PackageProduct, Product, FeatureKey):
        uid = f"entitlements_bump_{catalogue_model._meta.label_lower}"
        post_save.connect(_catalogue_row, sender=catalogue_model, dispatch_uid=f"{uid}_save")
        post_delete.connect(_catalogue_row, sender=catalogue_model, dispatch_uid=f"{uid}_delete")
