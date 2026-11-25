"""Find & recode (C-07-T03): lines in a filed GST/HST or QST period are excluded when they carry
a tax code or the recode changes tax codes — a filed return can't move."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.recode_exclusions import Key, Reason, key, register_exclusion

from .models import FilingPeriod, PeriodStatus


def filed_periods(
    organisation: Any, lines: Sequence[Any], changes: dict[str, Any], user: Any
) -> dict[Key, Reason]:
    touches_tax = "tax_code" in changes
    taxed = [line for line in lines if touches_tax or line.tax_code]
    if not taxed:
        return {}
    first = min(line.entry.date for line in taxed)
    last = max(line.entry.date for line in taxed)
    periods = list(
        FilingPeriod._base_manager.filter(
            organisation=organisation,
            registration__deleted_at__isnull=True,
            status__in=(PeriodStatus.FILED, PeriodStatus.PAID),
            start__lte=last,
            end__gte=first,
        ).select_related("registration")
    )
    out: dict[Key, Reason] = {}
    for line in taxed:
        period = next((p for p in periods if p.start <= line.entry.date <= p.end), None)
        if period is not None:
            out[key(line)] = Reason(
                "filed_period",
                _(
                    "The tax period %(start)s to %(end)s is filed: lines with tax in it can't be "
                    "recoded."
                )
                % {"start": period.start.isoformat(), "end": period.end.isoformat()},
                {
                    "start": period.start.isoformat(),
                    "end": period.end.isoformat(),
                    "registration": period.registration.type,
                },
            )
    return out


def register_recode_exclusions() -> None:
    register_exclusion(filed_periods)
