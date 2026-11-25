"""G-03a-T17 — nightly job: 24 months of periods ahead, closed / due soon / overdue recomputed,
events for the O-04 calendar and notifications. Acceptance: the job is idempotent across two
workers (run twice, and run at once on two threads: the same periods, each event once)."""

from __future__ import annotations

import datetime as dt
import threading
from typing import Any

import pytest
from django.db import connection
from freezegun import freeze_time

from numo9.accounts.models import User
from numo9.notifications.models import Notification
from numo9.tax import filing_service, tasks
from numo9.tax.filing_service import roll_forward, switch_frequency
from numo9.tax.models import FilingPeriod, PeriodStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.filing_helpers import registration

day = dt.date


def rows(reg: Any) -> list[tuple[str, str, str, str, str]]:
    with org_context(reg.organisation):
        return [
            (p.start.isoformat(), p.end.isoformat(), p.kind, p.status, p.attention)
            for p in FilingPeriod.objects.filter(registration=reg).order_by("start")
        ]


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        filing_service, "FILING_EVENTS", [lambda period, state: seen.append((str(period), state))]
    )
    return seen


@pytest.mark.django_db
def test_rolls_24_months_and_recomputes_attention(events: list[tuple[str, str]]) -> None:
    reg = registration()
    owner = User.objects.create_user("dana@filing.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=reg.organisation, user=owner, role="owner")
    switch_frequency(reg, "quarterly", day(2026, 1, 1), today=day(2026, 2, 1))
    assert rows(reg)[-1][:3] == ("2028-01-01", "2028-03-31", "regular")
    with freeze_time("2026-07-20 15:00:00"):  # Q1 was due 30 Apr; Q2 is due 31 Jul
        first = roll_forward()
    assert first == {"registrations": 1, "added": 2, "due_soon": 1, "overdue": 1}
    after = rows(reg)
    assert after[-1][:3] == ("2028-07-01", "2028-09-30", "regular")  # whole, not cut at 31 Jul
    assert [r[3:] for r in after[:3]] == [
        ("closed", "overdue"), ("closed", "due_soon"), ("open", ""),
    ]  # fmt: skip
    assert events == [
        ("2026-01-01 – 2026-03-31", "overdue"),
        ("2026-04-01 – 2026-06-30", "due_soon"),
    ]
    with org_context(reg.organisation):
        told = Notification.objects.filter(recipient=owner).order_by("pk")
        assert [n.title_key for n in told] == [
            "notifications.tax.filing.overdue",
            "notifications.tax.filing.due_soon",
        ]
    with freeze_time("2026-07-20 23:00:00"):
        again = roll_forward()
    assert again == {"registrations": 1, "added": 0, "due_soon": 0, "overdue": 0}
    assert rows(reg) == after and len(events) == 2  # idempotent: nothing new, no event twice
    with org_context(reg.organisation):  # filing Q1 clears it; Q2 goes overdue in August
        q1 = FilingPeriod.objects.filter(registration=reg).order_by("start")[0]
        q1.status = PeriodStatus.FILED
        q1.save()
    with freeze_time("2026-08-03 15:00:00"):
        later = roll_forward()
    assert (later["due_soon"], later["overdue"]) == (0, 1)
    assert [r[3:] for r in rows(reg)[:2]] == [("filed", ""), ("closed", "overdue")]
    assert events[-1] == ("2026-04-01 – 2026-06-30", "overdue")


@pytest.mark.django_db
def test_a_period_cut_at_the_old_horizon_is_made_whole() -> None:
    reg = registration()
    switch_frequency(reg, "quarterly", day(2026, 1, 1), today=day(2026, 2, 1))
    with org_context(reg.organisation):  # as the engine left it before the horizon fix
        last = FilingPeriod.objects.filter(registration=reg).order_by("-start")[0]
        last.end, last.kind = day(2028, 2, 29), "stub"
        last.save()
    with freeze_time("2026-03-10 15:00:00"):
        roll_forward()
    assert [r[:3] for r in rows(reg)[-2:]] == [
        ("2027-10-01", "2027-12-31", "regular"),
        ("2028-01-01", "2028-03-31", "regular"),
    ]


@pytest.mark.django_db
def test_stopped_and_unconfigured_registrations() -> None:
    stopped = registration("Stopped Ltd.", stop=day(2026, 12, 31))
    switch_frequency(stopped, "monthly", day(2026, 1, 1), today=day(2026, 2, 1))
    registration("No cycle Ltd.")  # no frequency: skipped
    before = rows(stopped)
    with freeze_time("2026-03-10 15:00:00"):
        result = tasks.roll_filing_periods.run()
    assert result["registrations"] == 1 and result["added"] == 0
    after = rows(stopped)
    assert [r[:3] for r in after] == [r[:3] for r in before] and after[-1][1] == "2026-12-31"


@pytest.mark.django_db(transaction=True)
def test_two_workers_at_once_do_the_work_once(events: list[tuple[str, str]]) -> None:
    reg = registration("Two workers Ltd.")
    switch_frequency(reg, "monthly", day(2026, 1, 1), today=day(2026, 2, 1))
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            # ``now`` passed in: a frozen clock would break the threads' database connections.
            roll_forward(dt.datetime(2026, 7, 20, 15, tzinfo=dt.UTC))
        except BaseException as error:  # noqa: BLE001 - reported by the assertion below
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    after = rows(reg)
    assert after[-1][:2] == ("2028-07-01", "2028-07-31") and len(after) == 31
    for a, b in zip(after, after[1:], strict=False):
        assert dt.date.fromisoformat(b[0]) == dt.date.fromisoformat(a[1]) + dt.timedelta(days=1)
    assert (
        sorted(events) == sorted(set(events)) and len(events) == 6
    )  # Jan–May overdue, Jun due soon
