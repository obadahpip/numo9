"""GST/HST quick method (G-03-T04): line 103 from the remittance rates, as data.

Under the quick method (TaxSettings ``quick_method`` from ``quick_method_from``) a registrant
remits a percent of its **eligible supplies including tax** instead of the tax collected, and
claims ITCs on **capital** purchases only (``docs/specs/gst-hst-return-line-mapping.md`` §3):

- **101** — taxable sales including GST/HST (zero-rated and exempt excluded);
- **103** — Σ each supply's amount including tax × the remittance rate of its component (the
  supply's province: ``gst``, ``hst_on``…) and the registrant's kind (``services`` / ``goods``,
  ``TaxSettings.quick_method_kind``), on the period's dates — effective-dated rows of
  ``data/quick_method_rates.json`` — **less the 1 % credit** on the first 30,000 of eligible
  supplies (including tax) of the fiscal year: what the fiscal year's earlier periods used of
  the 30,000 is not available again;
- **106** — the recoverable GST/HST of purchase lines posted to fixed or intangible asset
  accounts;
- the other lines as the regular method (``return_lines.totals``).

A supply with no rate in force refuses the calculation naming the component
(``tax.quick.rate_missing``) — never a guessed rate.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.utils.translation import gettext as _

from .cash_basis import RecognisedLine
from .models import TaxError
from .return_lines import _d, period_lines, totals

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
DATA = Path(__file__).resolve().parent / "data" / "quick_method_rates.json"
CAPITAL_SUBTYPES = ("fixed_asset", "intangible", "non_current_asset")


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(DATA.read_text(encoding="utf-8"))
    return loaded


def remittance_rate(component: str, kind: str, day: dt.date) -> Decimal:
    for row in _data()["rates"]:
        start = dt.date.fromisoformat(row["from"])
        end = dt.date.fromisoformat(row["to"]) if row["to"] else None
        in_force = start <= day and (end is None or day <= end)
        if row["component"] == component and row["kind"] == kind and in_force:
            return Decimal(row["pct"])
    raise TaxError(
        _("There's no quick-method rate for %(component)s on %(day)s: enter it first.")
        % {"component": component, "day": day.isoformat()},
        code="tax.quick.rate_missing",
        params={"component": component, "day": day.isoformat()},
    )


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def eligible(lines: list[RecognisedLine]) -> list[tuple[RecognisedLine, Decimal]]:
    """Taxable sales lines with their amount including tax (zero-rated: no tax, not eligible)."""
    out = []
    for row in lines:
        if row.side != "sales" or row.source != "document" or row.line.rate in (None, 0):
            continue
        out.append((row, row.basis + row.tax))
    return out


def _earlier_in_year(period: Any, kind: str) -> Decimal:
    """Eligible supplies (incl. tax) of the fiscal year before the period (the credit used)."""
    from numo9.ledger.period_close import fiscal_year_of

    from .cash_basis import recognised_lines
    from .settings import report_basis

    start, _end = fiscal_year_of(period.organisation, period.start)
    if start >= period.start:
        return ZERO
    rows = recognised_lines(
        period.organisation,
        start,
        period.start - dt.timedelta(days=1),
        basis=report_basis(period.organisation)[0],
        kind="gst_hst",
    )
    return sum((amount for _row, amount in eligible(rows)), ZERO)


def quick_lines(
    period: Any, *, entries: dict[str, Any] | None = None, basis: str | None = None
) -> dict[str, Decimal]:
    from numo9.ledger.models import JournalLine

    from .returns import adjustment_lines
    from .settings import tax_settings

    entries = entries or {}
    settings = tax_settings(period.organisation)
    kind = settings.quick_method_kind or "services"
    lines = period_lines(period, basis=basis)
    supplies = eligible(lines)
    line_101 = sum((amount for _row, amount in supplies), ZERO)
    remit = sum(
        (
            _cents(amount * remittance_rate(row.component, kind, row.line.date) / 100)
            for row, amount in supplies
        ),
        ZERO,
    )
    credit_data = _data()["credit"]
    room = max(Decimal(credit_data["threshold"]) - _earlier_in_year(period, kind), ZERO)
    credit = _cents(min(line_101, room) * Decimal(credit_data["pct"]) / 100)
    purchases = [r for r in lines if r.side == "purchase"]
    capital = {
        (entry_id, line_no)
        for entry_id, line_no in JournalLine.objects.filter(
            entry_id__in={r.line.entry_id for r in purchases},
            account__subtype__in=CAPITAL_SUBTYPES,
        ).values_list("entry_id", "line_no")
    }
    itc = sum(
        (r.recoverable for r in purchases if (r.line.entry_id, r.line.line_no) in capital), ZERO
    )
    adjustments = adjustment_lines(period)
    values = {
        "101": line_101,
        "103": max(remit - credit, ZERO),
        "104": _d(adjustments["104"]) + _d(entries.get("104")),
        "106": itc,
        "107": _d(adjustments["107"]) + _d(entries.get("107")),
        "110": _d(entries.get("110")),
        "111": _d(entries.get("111")),
        "113B": _d(entries.get("113B")),
    }
    return totals(values)
