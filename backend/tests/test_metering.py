"""S-06-T07 — usage-metering event API: ``meter(org, key, qty)`` → stream → daily aggregates.

Acceptance: 10k events aggregate correctly. 10,000 random events over 5 organisations, 3 keys and
3 days sum to exactly the expected ``UsageDaily`` rows, in several batches, on the in-process
stream and on Redis (when ``NUMO9_TEST_REDIS_URL`` is set, as in CI). Each event is counted once:
a second run adds nothing, and an aggregator that stopped after committing but before trimming
doesn't count the batch again. ``meter`` never raises or blocks: a bad key, a bad quantity or a
stream that's down drops the event with a warning and returns False within the timeout.
"""

from __future__ import annotations

import datetime as dt
import os
import random
import time
from collections import Counter
from collections.abc import Iterator
from typing import Any

import pytest

from numo9.metering import service
from numo9.metering.models import StreamOffset, UsageDaily
from numo9.metering.stream import MemoryStream, RedisStream, Stream, set_stream
from numo9.tenancy.context import org_context
from tests.workspace_helpers import client_org, practice

pytestmark = pytest.mark.django_db

KEYS = ["documents.ocr.page", "email.sent", "api.request"]
DAYS = [dt.datetime(2026, 11, d, 12, tzinfo=dt.UTC) for d in (16, 17, 18)]
REDIS = os.environ.get("NUMO9_TEST_REDIS_URL", "")


@pytest.fixture(params=["memory", "redis"])
def stream(request: pytest.FixtureRequest) -> Iterator[Stream]:
    if request.param == "redis":
        if not REDIS:
            pytest.skip("NUMO9_TEST_REDIS_URL not set")
        made: Stream = RedisStream(REDIS, name=f"numo9:metering:test:{os.getpid()}")
        made.client.delete(made.name)  # type: ignore[attr-defined]
    else:
        made = MemoryStream()
    set_stream(made)
    yield made
    if request.param == "redis":
        made.client.delete(made.name)  # type: ignore[attr-defined]
    set_stream(None)


def _orgs(count: int) -> list[Any]:
    firm = practice("Abuodeh CPA")
    return [client_org(firm, f"Client {n}") for n in range(count)]


def _usage() -> dict[tuple[int, str, str], int]:
    rows = UsageDaily.objects.unscoped(reason="test: all organisations' usage")
    return {(r.organisation_id, r.key, r.day.isoformat()): r.quantity for r in rows}


def test_ten_thousand_events_aggregate_correctly(stream: Stream) -> None:
    orgs = _orgs(5)
    rng = random.Random(9)  # noqa: S311 — reproducible test data, not secrets
    expected: Counter[tuple[int, str, str]] = Counter()
    for _ in range(10_000):
        org, key, at, qty = rng.choice(orgs), rng.choice(KEYS), rng.choice(DAYS), rng.randint(1, 9)
        assert service.meter(org, key, qty, at=at) is True
        expected[(org.pk, key, at.date().isoformat())] += qty

    result = service.aggregate(batch=3000)
    assert result.events == 10_000
    assert result.batches == 4
    assert _usage() == dict(expected)
    assert len(expected) == 45
    assert stream.length() == 0  # summed entries are trimmed

    assert service.aggregate().events == 0  # nothing counted twice
    assert _usage() == dict(expected)


def test_a_batch_committed_but_not_trimmed_is_not_counted_again(stream: Stream) -> None:
    (org,) = _orgs(1)
    for _ in range(10):
        service.meter(org, "email.sent", 2, at=DAYS[0])
    trim = stream.trim_through
    stream.trim_through = lambda last_id: None  # type: ignore[method-assign]  # stops before trim
    service.aggregate()
    stream.trim_through = trim  # type: ignore[method-assign]
    assert stream.length() == 10
    service.aggregate()  # restarts after the saved offset
    assert _usage() == {(org.pk, "email.sent", "2026-11-16"): 20}
    assert StreamOffset.objects.get().last_id != "0-0"


@pytest.mark.parametrize(
    ("key", "qty"), [("Email Sent", 1), ("email", 1), ("email.sent", 0), ("email.sent", 1.5)]
)
def test_bad_events_are_dropped_without_raising(stream: Stream, key: str, qty: Any) -> None:
    (org,) = _orgs(1)
    assert service.meter(org, key, qty) is False
    assert stream.length() == 0


def test_a_stream_that_is_down_never_blocks_the_request() -> None:
    (org,) = _orgs(1)
    set_stream(RedisStream("redis://10.255.255.1:6390/0"))  # unroutable
    try:
        started = time.monotonic()
        assert service.meter(org, "email.sent") is False
        assert time.monotonic() - started < 1.5
    finally:
        set_stream(None)


def test_usage_is_an_organisation_record(stream: Stream) -> None:
    first, second = _orgs(2)
    service.meter(first, "email.sent", 3, at=DAYS[0])
    service.meter(second, "email.sent", 5, at=DAYS[0])
    service.aggregate()
    with org_context(first):
        assert [u.quantity for u in UsageDaily.objects.all()] == [3]


def test_aggregator_is_scheduled_every_minute() -> None:
    from django.conf import settings

    from numo9.metering.tasks import JOB, aggregate_job

    assert settings.CELERY_BEAT_SCHEDULE[JOB]["task"] == JOB == aggregate_job.name
    assert aggregate_job.atomic is False
