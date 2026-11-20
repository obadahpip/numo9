"""Per-organisation rate limit (S-06-T05): a Redis token bucket per organisation.

Every API request made **inside an organisation** (``/api/v1/o/<org>/…`` or the ``X-Numo9-Org``
header — what ``TenantContextMiddleware`` resolved) takes one token from that organisation's
bucket. The bucket holds ``burst`` tokens and refills at ``per_minute / 60`` tokens a second, so
an organisation can make ``burst`` requests at once and ``per_minute`` a minute sustained.
Defaults: 600 a minute, burst 100 (``NUMO9_ORG_RATE_PER_MINUTE`` / ``NUMO9_ORG_RATE_BURST``); a
package can set its own (``limits.api_requests_per_minute`` / ``limits.api_burst``, U-02).

An empty bucket answers **429** ``request.rate_limited`` with ``Retry-After`` (whole seconds until a
token is back) and ``X-RateLimit-Limit`` / ``X-RateLimit-Remaining`` on every limited response.
The bucket is one atomic Lua script (no race between reading and taking), so concurrent requests
of an organisation — from every app server — share it exactly. If Redis can't be reached the
request goes through (logged): the limiter protects the service, it must not take it down.

Settings: ``NUMO9_ORG_RATE_LIMIT_ENABLED`` (on; the test settings turn it off and its own tests
on), ``NUMO9_RATE_LIMIT_REDIS_URL`` (database 5 of ``REDIS_URL``; empty = in-process buckets for
a single process: dev and tests).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)

KEY = "numo9:ratelimit:org:{org}"
POLICY_CACHE_SECONDS = 60

# KEYS[1] bucket; ARGV: capacity, refill per second, now (seconds, float), cost.
# Returns {allowed (0/1), tokens left (floor), seconds until the next token (ceil, ≥1 if denied)}.
LUA = """
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local state = redis.call('HMGET', KEYS[1], 'tokens', 'at')
local tokens = tonumber(state[1])
local at = tonumber(state[2])
if tokens == nil then
  tokens = capacity
  at = now
end
if now > at then
  tokens = math.min(capacity, tokens + (now - at) * rate)
  at = now
end
local allowed = 0
local wait = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  wait = math.ceil((cost - tokens) / rate)
end
redis.call('HSET', KEYS[1], 'tokens', tostring(tokens), 'at', tostring(at))
redis.call('EXPIRE', KEYS[1], math.ceil(capacity / rate) + 60)
return {allowed, math.floor(tokens), wait}
"""


@dataclass(frozen=True)
class Policy:
    per_minute: int
    burst: int

    @property
    def rate(self) -> float:
        return self.per_minute / 60.0


@dataclass(frozen=True)
class Decision:
    allowed: bool
    remaining: int
    retry_after: int


class Buckets(Protocol):
    def take(self, key: str, policy: Policy, now: float) -> Decision: ...


class RedisBuckets:
    def __init__(self, url: str) -> None:
        import redis

        # Short timeouts: a slow Redis must not hold the request (it then goes through).
        self.client = redis.Redis.from_url(url, socket_timeout=0.25, socket_connect_timeout=0.25)
        self.script = self.client.register_script(LUA)

    def take(self, key: str, policy: Policy, now: float) -> Decision:
        allowed, remaining, wait = self.script(keys=[key], args=[policy.burst, policy.rate, now, 1])
        return Decision(bool(int(allowed)), int(remaining), int(wait))


class MemoryBuckets:
    """The same bucket in process memory (dev server without Redis, tests)."""

    def __init__(self) -> None:
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str, policy: Policy, now: float) -> Decision:
        with self._lock:
            tokens, at = self._state.get(key, (float(policy.burst), now))
            if now > at:
                tokens, at = min(policy.burst, tokens + (now - at) * policy.rate), now
            if tokens >= 1:
                self._state[key] = (tokens - 1, at)
                return Decision(True, math.floor(tokens - 1), 0)
            self._state[key] = (tokens, at)
            return Decision(
                False, math.floor(tokens), max(1, math.ceil((1 - tokens) / policy.rate))
            )

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


_buckets: Buckets | None = None
_buckets_lock = threading.Lock()


def buckets() -> Buckets:
    global _buckets
    with _buckets_lock:
        if _buckets is None:
            url = getattr(settings, "NUMO9_RATE_LIMIT_REDIS_URL", "")
            _buckets = RedisBuckets(url) if url else MemoryBuckets()
        return _buckets


def set_buckets(value: Buckets | None) -> None:
    """Swap the bucket store (tests)."""
    global _buckets
    with _buckets_lock:
        _buckets = value


def default_policy() -> Policy:
    return Policy(
        per_minute=int(settings.NUMO9_ORG_RATE_PER_MINUTE),
        burst=int(settings.NUMO9_ORG_RATE_BURST),
    )


def policy_for(organisation: Any) -> Policy:
    """The organisation's package limits, else the defaults (cached 60 s per organisation)."""
    key = f"numo9:ratelimit:policy:{organisation.public_id}"
    cached = cache.get(key)
    if cached is not None:
        return Policy(*cached)
    from numo9.entitlements.models import current_subscription

    base = default_policy()
    subscription = current_subscription(organisation)
    package = subscription.package if subscription is not None else None
    per_minute = package.limit("api_requests_per_minute") if package is not None else None
    burst = package.limit("api_burst") if package is not None else None
    policy = Policy(per_minute or base.per_minute, burst or base.burst)
    cache.set(key, (policy.per_minute, policy.burst), POLICY_CACHE_SECONDS)
    return policy


def check(organisation: Any, now: float | None = None) -> tuple[Decision, Policy] | None:
    """Take a token for the organisation; ``None`` when the limiter couldn't decide (Redis
    down): the request goes through."""
    policy = policy_for(organisation)
    try:
        decision = buckets().take(
            KEY.format(org=organisation.public_id), policy, time.time() if now is None else now
        )
    except Exception:  # noqa: BLE001 — any store failure lets the request through
        logger.warning("ratelimit.unavailable", exc_info=True)
        return None
    return decision, policy


def limited_response(decision: Decision, policy: Policy) -> HttpResponse:
    from numo9.i18n.errors import RATE_LIMITED

    seconds = max(1, decision.retry_after)
    response = JsonResponse(
        {"detail": RATE_LIMITED.text(seconds=seconds), "code": RATE_LIMITED.code},
        status=RATE_LIMITED.status,
    )
    response["Retry-After"] = str(seconds)
    response["X-RateLimit-Limit"] = str(policy.per_minute)
    response["X-RateLimit-Remaining"] = "0"
    return response


class OrgRateLimitMiddleware:
    """After ``TenantContextMiddleware``: limits requests made inside an organisation."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        organisation = getattr(request, "organisation", None)
        if (
            organisation is None
            or not getattr(settings, "NUMO9_ORG_RATE_LIMIT_ENABLED", True)
            or not request.path.startswith("/api/")
        ):
            return self.get_response(request)
        outcome = check(organisation)
        if outcome is not None and not outcome[0].allowed:
            return limited_response(*outcome)
        response = self.get_response(request)
        if outcome is not None:
            decision, policy = outcome
            response["X-RateLimit-Limit"] = str(policy.per_minute)
            response["X-RateLimit-Remaining"] = str(decision.remaining)
        return response
