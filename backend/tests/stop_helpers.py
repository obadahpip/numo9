"""Stop/restart (G-03b) test helpers: a quarterly GST/HST registration from 1 Jan 2026."""

from __future__ import annotations

import datetime as dt
from typing import Any

from numo9.accounts.models import User
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

TODAY = dt.date(2026, 7, 15)


def quarterly(name: str = "Filing Ltd.", **kw: Any) -> tuple[Any, User]:
    reg = registration(name, **kw)
    user = User.objects.create_user(f"dana@{name.split()[0].lower()}.ca", name="Dana Lee")
    with org_context(reg.organisation):
        switch_frequency(reg, "quarterly", reg.start_date, today=TODAY)
    return reg, user


def spans(reg: Any) -> list[tuple[str, str, str]]:
    with org_context(reg.organisation):
        return [
            (p.start.isoformat(), p.end.isoformat(), p.kind)
            for p in FilingPeriod.objects.filter(registration=reg).order_by("start")
        ]


def file_period(reg: Any, end: dt.date) -> None:
    with org_context(reg.organisation):
        FilingPeriod.objects.filter(registration=reg, end=end).update(status="filed")
