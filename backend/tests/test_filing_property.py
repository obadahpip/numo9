"""G-03a-T13 — property test (Hypothesis): any sequence of frequency switches, out-of-cycle
periods (added and deleted) and filings over a three-year registration leaves the periods with
**no gaps and no overlaps**, **filed periods unchanged**, and **every date in exactly one
period**. Acceptance: 1,000 examples pass.

The pure generator runs 1,000 examples on every run (any cycles, any financial year end, any
custom periods). The database sequences run through the services (``switch_frequency``,
``add_custom_period``, ``delete_custom_period``) — a refused operation (``TaxError``) must leave
the periods exactly as they were. They take about nine minutes for 1,000 examples, so a routine
run does 200 and ``NUMO9_FILING_PROPERTY_EXAMPLES=1000`` runs the acceptance count (passed on
25 Nov 2026; run it again before a release that touches the engine).
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.tax.filing import ONE_DAY, Cycle, Span, generate_periods
from numo9.tax.filing_service import add_custom_period, delete_custom_period, switch_frequency
from numo9.tax.models import FilingCycle, FilingPeriod, PeriodKind, PeriodStatus, TaxError
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

day = dt.date
START, STOP = day(2026, 1, 1), day(2028, 12, 31)  # three years, one of them a leap year
TODAY = day(2026, 6, 1)
EXAMPLES = 1000
SEQUENCES = int(os.environ.get("NUMO9_FILING_PROPERTY_EXAMPLES", "200"))

frequencies = st.sampled_from(["monthly", "quarterly", "annual"])
dates = st.dates(min_value=START, max_value=STOP)
# Month starts as often as any other day: switches usually take effect on the 1st.
switch_dates = st.one_of(
    dates, st.builds(lambda d: d.replace(day=1), dates), st.just(day(2027, 1, 1))
)


def assert_covers(spans: list[tuple[dt.date, dt.date]], start: dt.date, end: dt.date) -> None:
    """``spans`` (in date order) cover every day of ``start``…``end`` exactly once."""
    assert spans, "no periods"
    assert spans[0][0] == start and spans[-1][1] == end
    for (a_start, a_end), (b_start, _b_end) in zip(spans, spans[1:], strict=False):
        assert a_start <= a_end
        assert b_start == a_end + ONE_DAY, f"gap or overlap between {a_end} and {b_start}"


# ---- the pure generator ---------------------------------------------------------------------


@st.composite
def customs(draw: st.DrawFn) -> list[Span]:
    out: list[Span] = []
    cursor = START
    for _ in range(draw(st.integers(0, 3))):
        start = cursor + dt.timedelta(days=draw(st.integers(0, 300)))
        end = start + dt.timedelta(days=draw(st.integers(0, 120)))
        if end > STOP:
            break
        out.append(Span(start, end))
        cursor = end + ONE_DAY
    return out


@settings(max_examples=EXAMPLES, deadline=None)
@given(
    first=frequencies,
    switches=st.lists(st.tuples(frequencies, switch_dates), max_size=4),
    fye=st.sampled_from([(12, 31), (3, 31), (6, 30), (2, 28), (2, 29), (9, 15), (1, 31)]),
    custom=customs(),
    probe=dates,
)
def test_generator_covers_every_day_exactly_once(
    first: str,
    switches: list[tuple[str, dt.date]],
    fye: tuple[int, int],
    custom: list[Span],
    probe: dt.date,
) -> None:
    cycles = [Cycle(first, START)]
    seen = {START}
    for frequency, effective in switches:
        if effective not in seen:
            seen.add(effective)
            cycles.append(Cycle(frequency, effective))
    periods = generate_periods(cycles, fye[0], fye[1], START, STOP, custom)
    assert_covers([(p.start, p.end) for p in periods], START, STOP)
    assert sum(1 for p in periods if p.start <= probe <= p.end) == 1
    emitted = [(p.start, p.end) for p in periods if p.kind == "custom"]
    assert emitted == [(c.start, c.end) for c in custom]
    for cycle in cycles:  # a period never straddles a switch outside a custom period
        for p in periods:
            if p.kind != "custom":
                assert not (p.start < cycle.effective_from <= p.end)


# ---- the services, on the database ----------------------------------------------------------

switch_op = st.tuples(st.just("switch"), frequencies, switch_dates)
custom_op = st.tuples(st.just("custom"), dates, st.integers(0, 150))
delete_op = st.tuples(st.just("delete"), st.integers(0, 5), st.none())
file_op = st.tuples(st.just("file"), st.integers(1, 6), st.none())
operations = st.lists(st.one_of(switch_op, custom_op, delete_op, file_op), min_size=1, max_size=8)


def snapshot(reg: Any) -> list[tuple[Any, ...]]:
    return [
        (p.pk, p.start, p.end, p.kind, p.status, p.sequence_no)
        for p in FilingPeriod.objects.filter(registration=reg).order_by("start")
    ]


def apply(reg: Any, op: tuple[Any, ...]) -> None:
    kind, a, b = op
    if kind == "switch":
        switch_frequency(reg, a, b, approval_ref="2026-GST-1", today=TODAY)
    elif kind == "custom":
        add_custom_period(reg, a, min(a + dt.timedelta(days=b), STOP), today=TODAY)
    elif kind == "delete":
        custom = list(
            FilingPeriod.objects.filter(registration=reg, kind=PeriodKind.CUSTOM).order_by("start")
        )
        if custom:
            delete_custom_period(custom[a % len(custom)], today=TODAY)
    else:  # file the next ``a`` unfiled periods, in order (a return is filed after the previous)
        unfiled = FilingPeriod.objects.filter(registration=reg).exclude(
            status__in=(PeriodStatus.FILED, PeriodStatus.PAID)
        )
        for period in list(unfiled.order_by("start")[:a]):
            period.status = PeriodStatus.FILED
            period.save(update_fields=["status"])


@pytest.fixture
def reg(db: None) -> Any:
    return registration("Property Ltd.", start=START, stop=STOP)


@settings(
    max_examples=SEQUENCES,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(first=frequencies, ops=operations, probes=st.lists(dates, min_size=1, max_size=5))
def test_any_sequence_keeps_the_periods_whole(
    reg: Any, first: str, ops: list[tuple[Any, ...]], probes: list[dt.date]
) -> None:
    with org_context(reg.organisation):
        FilingPeriod.objects.filter(registration=reg).delete()
        FilingCycle.objects.filter(registration=reg).delete()
        switch_frequency(reg, first, START, today=TODAY)
        for op in ops:
            before = snapshot(reg)
            filed = [row for row in before if row[4] in (PeriodStatus.FILED, PeriodStatus.PAID)]
            cycles = FilingCycle.objects.filter(registration=reg).count()
            try:
                apply(reg, op)
            except TaxError:
                assert snapshot(reg) == before, f"a refused {op[0]} changed the periods"
                assert FilingCycle.objects.filter(registration=reg).count() == cycles
            after = snapshot(reg)
            assert_covers([(row[1], row[2]) for row in after], START, STOP)
            assert [row[5] for row in after] == list(range(1, len(after) + 1))
            kept = {row[0]: row for row in after}
            for row in filed:  # same row, same dates, still filed
                assert kept.get(row[0], ())[:5] == row[:5], f"filed period changed by {op[0]}"
            for probe in probes:
                containing = FilingPeriod.objects.filter(
                    registration=reg, start__lte=probe, end__gte=probe
                )
                assert containing.count() == 1
