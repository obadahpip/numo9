"""Assurance run timings (K-09-T26): how long the nightly run takes, measured, and what that
means for N organisations in the nightly window.

``time_full_runs(organisations)`` runs each organisation's **full** run the way the nightly job
does (``runner.run(trigger=nightly)``: every enabled rule, findings written, one transaction per
organisation) and returns the seconds per organisation. ``project(seconds, target, workers)`` —
the mean time per organisation × ``target`` organisations ÷ ``workers`` (the nightly job queues one
job per organisation on the reports queue, so workers run them side by side): the projected
window. ``time_incremental(organisation, scope)`` — one incremental run (what a posting queues).

Used by ``manage.py assurance_timing`` (the full-scale measurement, ``make perf-assurance``) and by
``tests/test_assurance_performance.py`` (a scaled run in CI).
"""

from __future__ import annotations

import math
import statistics
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from django.utils import timezone

from .models import RunTrigger
from .rules.base import Scope
from .runner import run


@dataclass(frozen=True)
class Timings:
    seconds: tuple[float, ...]

    @property
    def count(self) -> int:
        return len(self.seconds)

    @property
    def total(self) -> float:
        return sum(self.seconds)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.seconds) if self.seconds else 0.0

    def percentile(self, p: float) -> float:
        if not self.seconds:
            return 0.0
        ordered = sorted(self.seconds)
        return ordered[min(len(ordered) - 1, max(0, math.ceil(p / 100 * len(ordered)) - 1))]

    @property
    def max(self) -> float:
        return max(self.seconds, default=0.0)


def time_full_runs(
    organisations: Iterable[Any],
    *,
    progress: Callable[[int, Any, float], None] | None = None,
) -> Timings:
    seconds: list[float] = []
    for done, organisation in enumerate(organisations, 1):
        started = time.perf_counter()
        run(organisation, trigger=RunTrigger.NIGHTLY, now=timezone.now())
        seconds.append(time.perf_counter() - started)
        if progress:
            progress(done, organisation, seconds[-1])
    return Timings(tuple(seconds))


def time_incremental(organisation: Any, scope: Scope) -> float:
    started = time.perf_counter()
    run(organisation, trigger=RunTrigger.POSTING, scope=scope, now=timezone.now())
    return time.perf_counter() - started


def project(timings: Timings, target: int, workers: int = 1) -> float:
    """Projected seconds for ``target`` organisations on ``workers`` workers."""
    return timings.mean * target / max(1, workers)
