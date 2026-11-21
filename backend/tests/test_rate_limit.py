"""S-06-T05 — per-organisation rate limiter (Redis token bucket) with package-based limits.

Acceptance: exceeding returns 429 + Retry-After. Also: the burst is served at once and the bucket
refills at per_minute/60 a second; organisations have separate buckets; a package's limits replace
the defaults (600/min, burst 100); requests outside an organisation aren't limited; Redis down →
requests go through; the Lua bucket behaves like the in-process one on a real Redis.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

from numo9.accounts.models import User
from numo9.scale import ratelimit
from numo9.scale.ratelimit import MemoryBuckets, Policy, RedisBuckets, check, policy_for
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.entitlement_helpers import package, subscribe

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def memory() -> Iterator[MemoryBuckets]:
    store = MemoryBuckets()
    ratelimit.set_buckets(store)
    cache.clear()
    with override_settings(
        NUMO9_ORG_RATE_LIMIT_ENABLED=True, NUMO9_ORG_RATE_PER_MINUTE=60, NUMO9_ORG_RATE_BURST=3
    ):
        yield store
    ratelimit.set_buckets(None)


def org_client(name: str) -> tuple[Organisation, Client]:
    organisation = Organisation.objects.create(name=name)
    person = User.objects.create_user(f"{organisation.public_id.hex[:8]}@x.ca", password="x" * 12)
    OrganisationMember.objects.create(organisation=organisation, user=person, role="owner")
    browser = Client()
    browser.force_login(person)
    return organisation, browser


def settings_url(organisation: Organisation) -> str:
    return f"/api/v1/o/{organisation.public_id}/settings"


def test_exceeding_returns_429_with_retry_after() -> None:
    org, browser = org_client("Maple Bakery Inc.")
    codes = [browser.get(settings_url(org)).status_code for _ in range(3)]
    assert codes == [200, 200, 200]
    limited = browser.get(settings_url(org))
    assert limited.status_code == 429
    assert limited["Retry-After"] == "1"  # 60/min: one token a second
    assert limited.json()["code"] == "request.rate_limited"
    assert "1 seconds" in limited.json()["detail"]
    assert limited["X-RateLimit-Limit"] == "60"


def test_burst_then_refill_at_the_rate() -> None:
    org = Organisation.objects.create(name="Birch Ltd.")
    policy = Policy(per_minute=60, burst=3)
    results = [check(org, now=1000.0) for _ in range(4)]
    assert [r[0].allowed for r in results if r] == [True, True, True, False]
    assert check(org, now=1000.5)[0].allowed is False  # type: ignore[index]
    assert check(org, now=1001.0)[0].allowed is True  # type: ignore[index]
    assert policy_for(org) == policy


def test_each_organisation_has_its_own_bucket() -> None:
    maple, maple_browser = org_client("Maple")
    birch, birch_browser = org_client("Birch")
    for _ in range(3):
        maple_browser.get(settings_url(maple))
    assert maple_browser.get(settings_url(maple)).status_code == 429
    assert birch_browser.get(settings_url(birch)).status_code == 200


def test_package_limits_replace_the_defaults() -> None:
    org = Organisation.objects.create(name="Pine Co.")
    plan = package("enterprise", ["accounting"])
    plan.limits = {"api_requests_per_minute": 1200, "api_burst": 300}
    plan.save()
    subscribe(org, plan)
    assert policy_for(org) == Policy(per_minute=1200, burst=300)
    other = Organisation.objects.create(name="Fir Co.")
    assert policy_for(other) == Policy(per_minute=60, burst=3)  # the defaults


def test_requests_outside_an_organisation_are_not_limited() -> None:
    _org, browser = org_client("Cedar")
    assert all(browser.get("/api/v1/me/organisations").status_code == 200 for _ in range(6))


def test_redis_down_lets_requests_through() -> None:
    ratelimit.set_buckets(RedisBuckets("redis://127.0.0.1:1/0"))
    org, browser = org_client("Spruce")
    assert all(browser.get(settings_url(org)).status_code == 200 for _ in range(6))


def test_switched_off() -> None:
    org, browser = org_client("Oak")
    with override_settings(NUMO9_ORG_RATE_LIMIT_ENABLED=False):
        assert all(browser.get(settings_url(org)).status_code == 200 for _ in range(6))


@pytest.mark.skipif(not os.environ.get("NUMO9_TEST_REDIS_URL"), reason="needs NUMO9_TEST_REDIS_URL")
def test_lua_bucket_on_redis() -> None:
    store = RedisBuckets(os.environ["NUMO9_TEST_REDIS_URL"])
    key = "numo9:ratelimit:test:lua"
    store.client.delete(key)
    policy = Policy(per_minute=60, burst=2)
    decisions = [store.take(key, policy, 500.0) for _ in range(3)]
    assert [d.allowed for d in decisions] == [True, True, False]
    assert decisions[2].retry_after == 1
    assert store.take(key, policy, 501.0).allowed is True
    assert store.client.ttl(key) > 0
    store.client.delete(key)
