"""U-03-T06 — entitlement cache: versioned keys, invalidated by saves (no TTL wait).

Acceptance: a change → the next call returns the new result. Covered for every invalidating save:
subscription (status, package, founding), override (grant, removal), package products, product
status, feature keys and the organisation itself. Also: a cached call runs no query; an answer
never outlives its validity (grace end, override expiry); the version is per organisation; the
same holds on Redis (``NUMO9_TEST_REDIS_URL``, CI backend job).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone

from numo9.catalogue.models import FeatureKey, Product, ProductStatus
from numo9.entitlements.cache import cache_key, entitlements_for, version
from numo9.entitlements.models import SubscriptionStatus
from numo9.packages.models import PackageProduct
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.entitlement_helpers import grant, package, payroll_keys, subscribe

pytestmark = pytest.mark.django_db

REDIS_URL = os.environ.get("NUMO9_TEST_REDIS_URL")
PAYROLL_WRITE = "payroll.pay_runs.write"


@pytest.fixture
def org() -> Organisation:
    payroll_keys()
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


def test_cached_call_runs_no_query(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]))
    first = entitlements_for(org)
    with CaptureQueriesContext(connection) as queries:
        again = entitlements_for(org)
    assert again == first
    assert len(queries) == 0


def test_subscription_change_is_seen_on_the_next_call(org: Organisation) -> None:
    complete = package("complete", ["accounting", "payroll"])
    item = subscribe(org, package("starter", ["accounting"]))
    assert not entitlements_for(org).allows(PAYROLL_WRITE)
    item.package = complete
    item.save()
    assert entitlements_for(org).allows(PAYROLL_WRITE)
    item.status = SubscriptionStatus.CANCELLED
    item.save()
    assert entitlements_for(org).mode == "read_only"


def test_founding_flag_is_seen_on_the_next_call(org: Organisation) -> None:
    item = subscribe(org, package("starter", ["accounting"]))
    assert not entitlements_for(org).allows(PAYROLL_WRITE)
    item.founding = True
    item.save()
    assert entitlements_for(org).allows(PAYROLL_WRITE)


def test_override_grant_and_removal_are_seen_on_the_next_call(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]))
    assert not entitlements_for(org).allows(PAYROLL_WRITE)
    item = grant(org, "payroll")
    assert entitlements_for(org).allows(PAYROLL_WRITE)
    with org_context(org):
        item.soft_delete()
    assert not entitlements_for(org).allows(PAYROLL_WRITE)


def test_package_product_change_is_seen_on_the_next_call(org: Organisation) -> None:
    starter = package("starter", ["accounting"])
    subscribe(org, starter)
    assert not entitlements_for(org).allows(PAYROLL_WRITE)
    link = PackageProduct.objects.create(
        package=starter, product=Product.objects.get(code="payroll")
    )
    assert entitlements_for(org).allows(PAYROLL_WRITE)
    link.delete()
    assert not entitlements_for(org).allows(PAYROLL_WRITE)


def test_catalogue_change_is_seen_on_the_next_call(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]), founding=True)
    payroll = Product.objects.get(code="payroll")
    assert entitlements_for(org).allows(PAYROLL_WRITE)
    FeatureKey.objects.create(key="payroll.remittances.write", product=payroll)
    assert entitlements_for(org).allows("payroll.remittances.write")
    commerce = Product.objects.get(code="app.commerce")
    commerce.status = ProductStatus.ACTIVE
    commerce.save()
    assert "app.commerce" in entitlements_for(org).products


def test_organisation_status_change_is_seen_on_the_next_call(org: Organisation) -> None:
    assert entitlements_for(org).mode == "full"
    org.status = "read_only"
    org.save()
    assert entitlements_for(org).mode == "read_only"


def test_versions_are_per_organisation(org: Organisation) -> None:
    other = Organisation.objects.create(name="Birch Ltd.")
    starter = package("starter", ["accounting"])  # a package change bumps everyone (global)
    before = version(other)
    subscribe(org, starter)
    assert version(other) == before
    assert cache_key(org) != cache_key(other)


def test_answer_never_outlives_the_grace_end(org: Organisation) -> None:
    grace = timezone.now() + timedelta(minutes=10)
    subscribe(
        org, package("starter", ["accounting"]), SubscriptionStatus.PAST_DUE, grace_until=grace
    )
    assert entitlements_for(org).mode == "full"  # cached until the grace end
    assert entitlements_for(org, now=grace + timedelta(seconds=1)).mode == "read_only"


def test_answer_never_outlives_an_override(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]))
    item = grant(org, "payroll", days=1)
    assert entitlements_for(org).allows(PAYROLL_WRITE)
    later = item.expires_at + timedelta(seconds=1)
    assert not entitlements_for(org, now=later).allows(PAYROLL_WRITE)


def test_entry_timeout_stops_at_the_validity(org: Organisation, monkeypatch: Any) -> None:
    seen: list[int] = []
    real_set = cache.set

    def spy(key: str, value: Any, timeout: Any = None, **kwargs: Any) -> Any:
        if key.startswith("ent:") and ":ver:" not in key:
            seen.append(timeout)
        return real_set(key, value, timeout=timeout, **kwargs)

    monkeypatch.setattr(cache, "set", spy)
    subscribe(org, package("starter", ["accounting"]))
    item = grant(org, "payroll", days=1)
    item.expires_at = timezone.now() + timedelta(seconds=90)
    with org_context(org):
        item.save()
    entitlements_for(org)
    assert seen and 1 <= seen[-1] <= 90


# ---- the same on Redis -------------------------------------------------------------------------


@pytest.fixture
def redis_cache() -> Iterator[None]:
    assert REDIS_URL
    caches = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": f"numo9-test-{os.getpid()}",
        }
    }
    with override_settings(CACHES=caches):
        from django.core.cache import cache as redis

        redis.clear()
        yield
        redis.clear()


@pytest.mark.skipif(not REDIS_URL, reason="NUMO9_TEST_REDIS_URL not set")
def test_change_is_seen_on_the_next_call_with_redis(org: Organisation, redis_cache: None) -> None:
    from django.core.cache import cache as redis
    from django.core.cache import caches

    assert type(caches["default"]).__name__ == "RedisCache"
    item = subscribe(org, package("starter", ["accounting"]))
    assert not entitlements_for(org).allows(PAYROLL_WRITE)
    assert redis.get(cache_key(org)) is not None  # stored in Redis
    item.override = {"products": ["payroll"]}
    item.save()
    assert entitlements_for(org).allows(PAYROLL_WRITE)
