"""Trial funnel events (U-05-T13): recorded by the trial life cycle, counted by the metrics (U-06).

``record_step(organisation, step, …)`` stores the step once (``TrialFunnelEvent`` is unique per
organisation, step and reminder milestone; a repeat is ignored) in the caller's transaction, so a
rolled-back conversion or expiry leaves no event. Demo organisations are skipped.
``funnel_counts(start, end)`` counts each step in a window — what the console's metrics show.
"""

from __future__ import annotations

import datetime as dt

from django.db import IntegrityError, transaction
from django.db.models import Count

from numo9.tenancy.models import Organisation, OrganisationStatus

from .models import FunnelStep, TrialFunnelEvent


def _is_demo(organisation: Organisation) -> bool:
    return bool(organisation.is_demo) or organisation.status == OrganisationStatus.DEMO


def record_step(
    organisation: Organisation,
    step: str,
    *,
    at: dt.datetime,
    milestone: int = -1,
    package: str = "",
) -> TrialFunnelEvent | None:
    if _is_demo(organisation):
        return None
    try:
        with transaction.atomic():
            return TrialFunnelEvent.objects.create(
                organisation=organisation, step=step, milestone=milestone, package=package, at=at
            )
    except IntegrityError:
        return None  # already recorded


def funnel_counts(start: dt.datetime, end: dt.datetime) -> dict[str, int]:
    """Each step's count with ``start <= at < end`` (reminders: every milestone sent)."""
    counts = dict.fromkeys(FunnelStep.values, 0)
    rows = (
        TrialFunnelEvent.objects.filter(at__gte=start, at__lt=end)
        .values("step")
        .annotate(n=Count("id"))
    )
    for row in rows:
        counts[row["step"]] = row["n"]
    return counts
