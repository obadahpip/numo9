"""G-03b-T13 — property test (Hypothesis) extended to stop & restart: any sequence of stops,
restarts, frequency switches, out-of-cycle periods and filings leaves the periods with **no
overlap**, **no period in a not-registered gap**, **every registered day in exactly one period**
(from the start to the stop date, or to the last period while registered), **filed periods
unchanged**, and a refused operation changes nothing. Plus the fixture scenarios of the plan's
edge cases (stop with postings after it is covered by test_filing_post_stop.py).

A routine run does 60 sequences; ``NUMO9_FILING_PROPERTY_EXAMPLES=1000`` runs more.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.accounts.models import User
from numo9.tax.filing import ONE_DAY
from numo9.tax.filing_service import (
    add_custom_period,
    gaps,
    registered_segments,
    switch_frequency,
)
from numo9.tax.models import (
    FilingCycle,
    FilingPeriod,
    PeriodStatus,
    RegistrationStatusEvent,
    TaxError,
)
from numo9.tax.stop_restart import is_stopped, restart, stop
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

day = dt.date
START = day(2026, 1, 1)
TODAY = day(2026, 6, 1)
SEQUENCES = int(os.environ.get("NUMO9_FILING_PROPERTY_EXAMPLES", "60"))

frequencies = st.sampled_from(["monthly", "quarterly", "annual"])
dates = st.dates(min_value=START, max_value=day(2028, 3, 31))
month_starts = st.builds(lambda d: d.replace(day=1), dates)
reasons = st.sampled_from(["deregistration", "small_supplier", "suspension", "other"])
stop_op = st.tuples(st.just("stop"), st.one_of(dates, month_starts), reasons)
restart_op = st.tuples(st.just("restart"), st.integers(1, 400), frequencies)
switch_op = st.tuples(st.just("switch"), frequencies, st.one_of(dates, month_starts))
custom_op = st.tuples(st.just("custom"), dates, st.integers(0, 90))
file_op = st.tuples(st.just("file"), st.integers(1, 4), st.none())
operations = st.lists(
    st.one_of(stop_op, restart_op, switch_op, custom_op, file_op), min_size=1, max_size=8
)


def snapshot(reg: Any) -> list[tuple[Any, ...]]:
    return [
        (p.pk, p.start, p.end, p.kind, p.status)
        for p in FilingPeriod.objects.filter(registration=reg).order_by("start")
    ]


def apply(reg: Any, user: Any, op: tuple[Any, ...]) -> None:
    kind, a, b = op
    reg.refresh_from_db()
    if kind == "stop":
        stop(reg, a, b, user=user, today=TODAY)
    elif kind == "restart":
        after = (reg.effective_to or TODAY) + dt.timedelta(days=a)
        restart(reg, after, b, user=user, today=TODAY)
    elif kind == "switch":
        switch_frequency(reg, a, b, approval_ref="2026-GST-1", today=TODAY)
    elif kind == "custom":
        add_custom_period(reg, a, a + dt.timedelta(days=b), today=TODAY)
    else:
        unfiled = FilingPeriod.objects.filter(registration=reg).exclude(
            status__in=(PeriodStatus.FILED, PeriodStatus.PAID)
        )
        for period in list(unfiled.order_by("start")[:a]):
            period.status = PeriodStatus.FILED
            period.save(update_fields=["status"])


def check_invariants(reg: Any) -> None:
    rows = snapshot(reg)
    assert rows, "no periods"
    spans = [(r[1], r[2]) for r in rows]
    for (a_start, a_end), (b_start, _b_end) in zip(spans, spans[1:], strict=False):
        assert a_start <= a_end and b_start > a_end, f"overlap at {b_start}"
    reg.refresh_from_db()
    end = reg.effective_to if reg.effective_to is not None else spans[-1][1]
    if reg.effective_to is not None:
        assert spans[-1][1] <= reg.effective_to or rows[-1][4] in (
            PeriodStatus.FILED,
            PeriodStatus.PAID,
        ), "a period after the stop"
    holes = gaps(reg)
    for start, finish in spans:
        for gap_start, gap_end in holes:
            assert finish < gap_start or (gap_end is not None and start > gap_end), (
                f"period {start}–{finish} in the gap from {gap_start}"
            )
    covered = iter(spans)
    for seg_start, seg_end in registered_segments(reg, START, end):
        cursor = seg_start
        while cursor <= seg_end:
            start, finish = next(covered)
            assert start == cursor, f"day {cursor} not covered (next period {start})"
            cursor = finish + ONE_DAY
        assert cursor == seg_end + ONE_DAY, f"a period crosses the end of {seg_start}–{seg_end}"


@pytest.fixture
def setup(db: None) -> tuple[Any, Any]:
    reg = registration("Stop Property Ltd.", start=START)
    return reg, User.objects.create_user("dana@stop.ca", name="Dana Lee")


@settings(
    max_examples=SEQUENCES,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(first=frequencies, ops=operations)
def test_stop_restart_sequences_keep_the_invariants(
    setup: tuple[Any, Any], first: str, ops: list[tuple[Any, ...]]
) -> None:
    reg, user = setup
    with org_context(reg.organisation):
        RegistrationStatusEvent.objects.filter(registration=reg).delete()
        FilingPeriod.objects.filter(registration=reg).delete()
        FilingCycle.objects.filter(registration=reg).delete()
        reg.effective_to, reg.status = None, "active"
        reg.save()
        switch_frequency(reg, first, START, today=TODAY)
        for op in ops:
            before = snapshot(reg)
            filed = [r for r in before if r[4] in (PeriodStatus.FILED, PeriodStatus.PAID)]
            events = RegistrationStatusEvent.objects.filter(registration=reg).count()
            try:
                apply(reg, user, op)
            except TaxError:
                assert snapshot(reg) == before, f"a refused {op[0]} changed the periods"
                assert RegistrationStatusEvent.objects.filter(registration=reg).count() == events
            check_invariants(reg)
            kept = {r[0]: r for r in snapshot(reg)}
            for row in filed:
                assert kept.get(row[0]) == row, f"filed period changed by {op[0]}"
            assert is_stopped(reg) == (reg.effective_to is not None)


# ---- fixture scenarios (the plan's edge cases) --------------------------------------------------


@pytest.mark.django_db
def test_scenario_same_frequency_restart_in_the_same_month() -> None:
    reg = registration("Scenario Ltd.", start=START)
    user = User.objects.create_user("sam@scenario.ca", name="Sam Patel")
    with org_context(reg.organisation):
        switch_frequency(reg, "monthly", START, today=TODAY)
    stop(reg, day(2026, 3, 10), "suspension", user=user, today=TODAY)
    restart(reg, day(2026, 3, 20), "monthly", user=user, today=TODAY)
    with org_context(reg.organisation):
        rows = [(p.start, p.end, p.kind) for p in FilingPeriod.objects.filter(registration=reg)]
        check_invariants(reg)
    assert (day(2026, 3, 1), day(2026, 3, 10), "stub") in rows
    assert (day(2026, 3, 20), day(2026, 3, 31), "stub") in rows
    assert (day(2026, 4, 1), day(2026, 4, 30), "regular") in rows
