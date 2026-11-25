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
    register_recode_rates()


def tax_amounts(organisation: Any, code: str, day: Any, base: Any) -> dict[str, Any]:
    """The tax ``base`` carries under ``code`` on ``day``: {component key: amount} — the version
    of the code and the components in force that day, rounded per component (G-01)."""
    from decimal import ROUND_HALF_UP, Decimal

    from .models import TaxCode

    versions = TaxCode._base_manager.filter(
        organisation=organisation, code=code, deleted_at__isnull=True
    ).order_by("version")
    version = next((v for v in versions if v.is_active_on(day)), None)
    if version is None:
        return {}
    out: dict[str, Any] = {}
    for link in version.components.select_related("component").order_by("position"):
        component = link.component
        if component.is_active_on(day):
            amount = (Decimal(base) * Decimal(component.rate) / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            out[component.key] = out.get(component.key, Decimal("0.00")) + amount
    return out


def register_recode_rates() -> None:
    from numo9.ledger.recode_preview import register_tax_rates

    register_tax_rates(tax_amounts)
