"""Registrations for the G-03a filing-cycle tests."""

from __future__ import annotations

import datetime as dt
from typing import Any

from numo9.orgsettings.models import TaxRegistration
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation


def registration(
    name: str = "Filing Ltd.",
    *,
    start: dt.date | None = dt.date(2026, 1, 1),
    stop: dt.date | None = None,
    kind: str = "rt",
    **settings: Any,
) -> TaxRegistration:
    """A GST/HST (or QST) registration of a new organisation; ``settings`` go on its
    organisation settings (``fye_month``, ``fye_day``, ``structure``…)."""
    from numo9.orgsettings.service import get_settings

    org = Organisation.objects.create(name=name)
    with org_context(org):
        if settings:
            current = get_settings(org)
            for key, value in settings.items():
                setattr(current, key, value)
            current.save()
        number = "123456782RT0001" if kind == "rt" else "1234567890TQ0001"
        item = TaxRegistration(
            organisation=org, type=kind, number=number, effective_from=start, effective_to=stop
        )
        item.save()
    return item
