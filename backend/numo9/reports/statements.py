"""Core financial statements (K-02), on the report engine (K-01): the presentation of
``docs/specs/financial-statements.md``.

- ``profit_and_loss`` (K-02-T02) — revenue, cost of sales, **gross profit**, operating expenses,
  **operating income**, other income and expenses, income taxes, **net income**, for a period and
  its comparatives (none / N previous periods / prior year, up to 12);
- ``balance_sheet`` (K-02-T03) — Assets, Liabilities and Equity **always printed** (0.00 for an
  empty organisation), contra accounts (accumulated amortization) directly under their asset,
  retained earnings (the account + every revenue and expense before the financial year) and
  **current year earnings** computed, as at a date (today by default) and comparatives;
- ``integrity(organisation, as_of, book)`` (K-02-T05) — assets = liabilities + equity and net
  income = Δ retained earnings + Δ current-year earnings; a failure is a red banner on the run
  (``ReportResult.alerts``) and a ``reports.integrity_failed`` event for monitoring (S-04).

Figures are read with the K-01 aggregation (``period_movements`` / ``balances_at``: posted lines
only, book filter ``book ∈ (both, X)``). Each figure drills down per column (``drill.columns``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .engine import Column, ParamSpec, ReportDefinition, ReportRow, register
from .parameters import COMPARISONS, MAX_COMPARISONS, DateRange, comparison_ranges

ZERO = Decimal("0.00")
BOOKS = ("accounting", "tax")

# ---- classification (C-01 sub-types) -------------------------------------------------------

#: Income-statement sections: (key, label, sub-types, sign) — sign 1 shows a debit balance
#: positive (expenses), −1 a credit balance positive (income).
PNL_SECTIONS: tuple[tuple[str, Any, tuple[str, ...], int], ...] = (
    ("revenue", _lazy("Revenue"), ("revenue",), -1),
    ("cost_of_sales", _lazy("Cost of sales"), ("cost_of_sales",), 1),
    ("operating_expenses", _lazy("Operating expenses"), ("operating_expense", "amortisation"), 1),
    ("other_income", _lazy("Other income"), ("other_income",), -1),
    ("other_expenses", _lazy("Other expenses"), ("other_expense",), 1),
    ("income_taxes", _lazy("Income taxes"), ("income_tax",), 1),
)
CURRENT_ASSETS = ("bank", "current_asset", "inventory", "prepayment")
NON_CURRENT_ASSETS = ("fixed_asset", "accumulated_amortisation", "intangible", "non_current_asset")
CURRENT_LIABILITIES = ("current_liability", "sales_tax_control", "payroll_liability")
LONG_TERM_LIABILITIES = ("non_current_liability",)
EQUITY = ("share_capital", "other_equity", "dividends")
PNL_TYPES = ("revenue", "expense")


def _accounts() -> list[Any]:
    from numo9.ledger.models import Account

    return list(Account.objects.filter(deleted_at__isnull=True).order_by("code"))


def _label(account: Any) -> str:
    return f"{account.code} · {account.name}"


def _period_columns(params: dict[str, Any]) -> list[DateRange]:
    base = DateRange(params["date_from"], params["date_to"])
    compare = params.get("compare") or "none"
    periods = max(1, min(int(params.get("periods") or 1), MAX_COMPARISONS))
    return [base, *comparison_ranges(base, compare, periods)] if compare != "none" else [base]


def _range_label(span: DateRange) -> str:
    from numo9.documents.formatting import format_date

    return _("%(start)s to %(end)s") % {
        "start": format_date(span.start),
        "end": format_date(span.end),
    }


def _v(values: Sequence[Decimal]) -> list[Decimal | None]:
    return list(values)


def _sum(values: Sequence[Sequence[Decimal | None]], width: int) -> list[Decimal]:
    return [sum((v[i] or ZERO for v in values), ZERO) for i in range(width)]


# ---- income statement (K-02-T02) -----------------------------------------------------------


@dataclass
class PnlData:
    ranges: list[DateRange]
    sections: dict[str, list[tuple[Any, list[Decimal]]]]


def pnl_figures(ranges: list[DateRange], book: str = "accounting") -> PnlData:
    from .aggregation import period_movements

    accounts = [a for a in _accounts() if a.type in PNL_TYPES]
    movements = period_movements(ranges, book=book, accounts=[a.pk for a in accounts])
    sections: dict[str, list[tuple[Any, list[Decimal]]]] = {key: [] for key, *_rest in PNL_SECTIONS}
    for account in accounts:
        figures = movements.get(account.pk)
        if figures is None:
            continue
        for key, _name, subtypes, sign in PNL_SECTIONS:
            if account.subtype in subtypes:
                sections[key].append((account, [sign * value for value in figures]))
                break
    return PnlData(ranges, sections)


def net_income(data: PnlData) -> list[Decimal]:
    width = len(data.ranges)
    total = [ZERO] * width
    for key, _name, _subtypes, sign in PNL_SECTIONS:
        sums = _sum([v for _a, v in data.sections[key]], width)
        total = [t + (s if sign < 0 else -s) for t, s in zip(total, sums, strict=True)]
    return total


@register
class ProfitAndLossReport(ReportDefinition):
    id = "profit_and_loss"
    slug = "profit-and-loss"
    name = _lazy("Profit and loss")
    description = _lazy(
        "Revenue, cost of sales, gross profit, expenses and net income for a period, with "
        "comparisons."
    )
    category = "financial"
    keywords = (_lazy("income statement"), _lazy("P&L"), _lazy("net income"), "état des résultats")
    params = (
        ParamSpec("date_from", "date", required=True),
        ParamSpec("date_to", "date", required=True),
        ParamSpec("compare", "choice", "none", COMPARISONS),
        ParamSpec("periods", "int", 1),
        ParamSpec("book", "choice", "accounting", BOOKS),
    )

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [Column(f"p{i}", _range_label(r)) for i, r in enumerate(_period_columns(params))]

    def query(self, organisation: Any, params: dict[str, Any]) -> PnlData:
        return pnl_figures(_period_columns(params), params["book"])

    def rows(self, data: PnlData, params: dict[str, Any]) -> list[ReportRow]:
        width = len(data.ranges)
        rows: list[ReportRow] = []
        drill_columns = [{"from": r.start, "to": r.end} for r in data.ranges]

        def section(key: str, label: Any) -> list[Decimal]:
            rows.append(ReportRow(f"section:{key}", str(label), "section"))
            for account, figures in data.sections[key]:
                rows.append(
                    ReportRow(
                        f"account:{account.code}",
                        _label(account),
                        values=_v(figures),
                        level=1,
                        drill={
                            "account": account.code,
                            "book": params["book"],
                            "columns": drill_columns,
                        },
                    )
                )
            total = _sum([f for _a, f in data.sections[key]], width)
            rows.append(
                ReportRow(
                    f"total:{key}",
                    _("Total %(section)s") % {"section": str(label).lower()},
                    "total",
                    _v(total),
                )
            )
            return total

        names = {key: name for key, name, *_rest in PNL_SECTIONS}
        revenue = section("revenue", names["revenue"])
        cogs = section("cost_of_sales", names["cost_of_sales"])
        gross = [r - c for r, c in zip(revenue, cogs, strict=True)]
        rows.append(ReportRow("gross_profit", _("Gross profit"), "total", _v(gross)))
        opex = section("operating_expenses", names["operating_expenses"])
        operating = [g - o for g, o in zip(gross, opex, strict=True)]
        rows.append(ReportRow("operating_income", _("Operating income"), "total", _v(operating)))
        other_in = section("other_income", names["other_income"])
        other_out = section("other_expenses", names["other_expenses"])
        before_tax = [o + i - x for o, i, x in zip(operating, other_in, other_out, strict=True)]
        rows.append(
            ReportRow("income_before_tax", _("Income before income taxes"), "total", _v(before_tax))
        )
        section("income_taxes", names["income_taxes"])
        return rows

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        by_key = {row.key: row for row in rows}
        before = by_key["income_before_tax"].values
        taxes = by_key["total:income_taxes"].values
        net = [(b or ZERO) - (t or ZERO) for b, t in zip(before, taxes, strict=True)]
        return [ReportRow("net_income", _("Net income"), "total", _v(net))]
