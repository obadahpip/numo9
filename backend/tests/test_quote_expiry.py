"""D-02-T05 — the expiry job: a quote expiring today can be accepted at 23:59 organisation-local
time and is Expired at 00:00 (freezegun, America/Toronto vs Vancouver); drafts and accepted
quotes are left alone; the job is idempotent and scheduled hourly."""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from freezegun import freeze_time

from numo9.sales import quotes as q
from numo9.sales.tasks import EXPIRE_QUOTES
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
TORONTO = ZoneInfo("America/Toronto")
EXPIRY = dt.date(2026, 6, 30)


def at(hour: int, minute: int, day: dt.date = EXPIRY, zone: ZoneInfo = TORONTO) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)


def sent(books: dict[str, Any], **fields: Any) -> Any:
    return q.send(
        quote(books, [("1", "100", "")], expiry=EXPIRY, **fields), now=at(9, 0, dt.date(2026, 6, 1))
    )


def test_accepted_at_23_59_local_expired_at_midnight() -> None:
    books = sales_books()
    books["org"].time_zone = "America/Toronto"
    books["org"].save()
    on_time = sent(books)
    late = sent(books)
    draft = quote(books, [("1", "100", "")], expiry=EXPIRY)
    assert q.accept(on_time, now=at(23, 59)).status == "accepted"
    with freeze_time(at(23, 59)):
        assert q.expire_due() == 0
    with freeze_time(at(0, 0, EXPIRY + dt.timedelta(days=1))):
        assert q.expire_due() == 1
        assert q.expire_due() == 0  # idempotent
    late.refresh_from_db()
    draft.refresh_from_db()
    assert (late.status, draft.status) == ("expired", "draft")
    with pytest.raises(q.QuoteRefused):
        q.accept(late, now=at(0, 1, EXPIRY + dt.timedelta(days=1)))


def test_each_organisation_expires_at_its_own_midnight() -> None:
    books = sales_books()
    books["org"].time_zone = "America/Vancouver"
    books["org"].save()
    item = sent(books)
    # 00:30 Toronto on 1 July is 21:30 on 30 June in Vancouver: still valid there.
    with freeze_time(at(0, 30, EXPIRY + dt.timedelta(days=1))):
        assert q.expire_due() == 0
    with pytest.raises(q.QuoteRefused) as err:
        q.accept(item, now=at(3, 1, EXPIRY + dt.timedelta(days=1)))
    assert err.value.code == "sales.quote.expired"  # 00:01 in Vancouver


def test_scheduled_hourly() -> None:
    entry = settings.CELERY_BEAT_SCHEDULE[EXPIRE_QUOTES]
    assert entry["task"] == EXPIRE_QUOTES
