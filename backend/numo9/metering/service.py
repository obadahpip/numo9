"""Usage metering API (S-06-T07).

``meter(org, key, qty)`` records that an organisation used ``qty`` of something (``key``, e.g.
``documents.ocr.page`` or ``email.sent``). It only appends to a stream — one Redis ``XADD`` with a
250 ms timeout — and **never raises or blocks the request**: a stream that's down loses the event
and logs a warning. ``aggregate()`` (job ``numo9.metering.aggregate``, every minute) sums the
stream into ``UsageDaily`` per organisation, key and UTC day, exactly once per event.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from django.db import connection, transaction
from django.utils import timezone

from .models import StreamOffset
from .stream import STREAM, get_stream

logger = logging.getLogger(__name__)

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
#: Entries summed per database transaction.
BATCH = 5000
#: Transaction advisory lock: one aggregator at a time ("METR").
LOCK_KEY = 0x4D455452


def meter(org: Any, key: str, qty: int = 1, at: dt.datetime | None = None) -> bool:
    """Record usage; True when the event was queued. Never raises."""
    try:
        if not KEY_RE.match(key):
            raise ValueError(f"meter key must be dotted lower-case like 'email.sent', not {key!r}")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            raise ValueError(f"meter quantity must be a positive integer, not {qty!r}")
        org_id = getattr(org, "pk", org)
        if not isinstance(org_id, int):
            raise ValueError("meter needs an organisation")
        day = (at or timezone.now()).astimezone(dt.UTC).date()
        get_stream().add({"org": str(org_id), "key": key, "qty": str(qty), "day": day.isoformat()})
        return True
    except Exception:
        logger.warning("usage event dropped: %s %s", key, qty, exc_info=True)
        return False


@dataclass
class AggregateResult:
    events: int = 0
    rows: int = 0
    batches: int = 0


UPSERT = (
    "INSERT INTO metering_usagedaily "
    "(organisation_id, key, day, quantity, public_id, created_at, updated_at) "
    "VALUES (%s, %s, %s, %s, gen_random_uuid(), now(), now()) "
    "ON CONFLICT (organisation_id, key, day) DO UPDATE "
    "SET quantity = metering_usagedaily.quantity + excluded.quantity, updated_at = now()"
)


def aggregate(max_seconds: float = 50.0, batch: int = BATCH) -> AggregateResult:
    """Sum the stream into ``UsageDaily`` in batches until it's empty or time is up."""
    stream = get_stream()
    result = AggregateResult()
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])
            offset, _ = StreamOffset.objects.select_for_update().get_or_create(stream=STREAM)
            entries = stream.read_after(offset.last_id, batch)
            if not entries:
                break
            sums: Counter[tuple[int, str, str]] = Counter()
            for _entry_id, fields in entries:
                try:
                    sums[(int(fields["org"]), fields["key"], fields["day"])] += int(fields["qty"])
                except (KeyError, ValueError):
                    logger.warning("malformed usage event skipped: %s", fields)
            with connection.cursor() as cursor:
                cursor.executemany(
                    UPSERT, [(org, key, day, qty) for (org, key, day), qty in sums.items()]
                )
            offset.last_id = entries[-1][0]
            offset.save(update_fields=["last_id", "updated_at"])
        stream.trim_through(offset.last_id)  # after the commit: summed entries can go
        result.events += len(entries)
        result.rows += len(sums)
        result.batches += 1
    return result
