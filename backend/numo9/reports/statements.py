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

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.utils import timezone
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


def _date_columns(params: dict[str, Any]) -> list[dt.date]:
    """The balance dates: the date (today by default), then N month-ends-style months back
    (``previous``, the same day of each earlier month, a month end staying a month end) or the
    same date N years back (``prior_year``)."""
    from .parameters import _add_months, _month_end, _year_back

    as_of: dt.date = params.get("as_of") or timezone.localdate()
    compare = params.get("compare") or "none"
    if compare == "none":
        return [as_of]
    periods = max(1, min(int(params.get("periods") or 1), MAX_COMPARISONS))
    month_end = as_of == _month_end(as_of.year, as_of.month)
    dates = [as_of]
    for n in range(1, periods + 1):
        if compare == "previous":
            day = _add_months(as_of, -n)
            dates.append(_month_end(day.year, day.month) if month_end else day)
        else:
            day = _year_back(as_of, n)
            dates.append(_month_end(day.year, day.month) if month_end else day)
    return dates


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

    def alerts(self, organisation: Any, result: Any) -> list[dict[str, Any]]:
        net = next(row for row in result.totals if row.key == "net_income").values
        found = []
        for span, column, income in zip(
            _period_columns(result.params), result.columns, net, strict=True
        ):
            change = _earnings_change(organisation, span, result.params["book"])
            alert = _earnings_mismatch(column.label, income or ZERO, change)
            if alert:
                found.append(alert)
        return found


# ---- balance sheet (K-02-T03) --------------------------------------------------------------


def fiscal_start(organisation: Any, day: dt.date) -> dt.date:
    from numo9.orgsettings.fiscal import fiscal_year
    from numo9.orgsettings.service import get_settings

    return fiscal_year(get_settings(organisation), day)[0]


#: F-07-T09: who says which asset bank/cash accounts are overdrawn at the balance-sheet dates —
#: ``hook(organisation, accounts, balances, dates) -> [Overdrawn(account, column, date, balance,
#: account_type)]`` (``numo9.banking.presentation.overdrawn_accounts``, registered by banking).
OVERDRAFT_HOOKS: list[Any] = []


@dataclass
class BalanceData:
    dates: list[dt.date]
    accounts: list[Any]
    balances: dict[int, list[Decimal]]
    retained: list[Decimal]
    current_year: list[Decimal]
    #: F-07-T09: the overdrawn asset bank/cash accounts, per date (K-02-T04 reclassifies them).
    overdrawn: list[Any] = field(default_factory=list)


def balance_figures(
    organisation: Any, dates: list[dt.date], book: str = "accounting"
) -> BalanceData:
    """Balances at each date; retained earnings = the RE account(s) + revenue − expenses before
    the financial year of the date; current-year earnings = revenue − expenses since its start."""
    from .aggregation import balances_at

    accounts = _accounts()
    balances = balances_at(dates, book=book)
    pnl = [a for a in accounts if a.type in PNL_TYPES]
    starts = [fiscal_start(organisation, day) for day in dates]
    before = balances_at([s - dt.timedelta(days=1) for s in starts], book=book)
    retained, current = [], []
    for i in range(len(dates)):
        prior = -sum((before.get(a.pk, [ZERO] * len(dates))[i] for a in pnl), ZERO)
        total = -sum((balances.get(a.pk, [ZERO] * len(dates))[i] for a in pnl), ZERO)
        retained.append(prior)
        current.append(total - prior)
    overdrawn = [
        found for hook in OVERDRAFT_HOOKS for found in hook(organisation, accounts, balances, dates)
    ]
    return BalanceData(dates, accounts, balances, retained, current, overdrawn)


def _ordered_non_current(accounts: list[Any]) -> list[Any]:
    """Each contra account directly after its asset: after the parent it sits under, or after the
    last of that parent's other sub-accounts ("Equipment — cost"); unparented contras after the
    last fixed asset."""
    contras = [a for a in accounts if a.subtype == "accumulated_amortisation"]
    out = [a for a in accounts if a.subtype != "accumulated_amortisation"]
    for contra in contras:
        anchor = None
        for i, item in enumerate(out):
            parent = contra.parent_id
            under = parent is not None and parent in (item.pk, item.parent_id)
            if under or (parent is None and item.subtype == "fixed_asset"):
                anchor = i
        if anchor is None:
            out.append(contra)
        else:
            out.insert(anchor + 1, contra)
    return out


@register
class BalanceSheetReport(ReportDefinition):
    id = "balance_sheet"
    slug = "balance-sheet"
    name = _lazy("Balance sheet")
    description = _lazy("Assets, liabilities and equity on a date, with comparisons.")
    category = "financial"
    keywords = (_lazy("statement of financial position"), _lazy("BS"), "bilan")
    params = (
        ParamSpec("as_of", "date"),
        ParamSpec("compare", "choice", "none", COMPARISONS),
        ParamSpec("periods", "int", 1),
        ParamSpec("book", "choice", "accounting", BOOKS),
    )

    def columns(self, params: dict[str, Any]) -> list[Column]:
        from numo9.documents.formatting import format_date

        return [Column(f"b{i}", format_date(day)) for i, day in enumerate(_date_columns(params))]

    def query(self, organisation: Any, params: dict[str, Any]) -> BalanceData:
        return balance_figures(organisation, _date_columns(params), params["book"])

    def rows(self, data: BalanceData, params: dict[str, Any]) -> list[ReportRow]:
        width = len(data.dates)
        rows: list[ReportRow] = []
        drill_columns = [{"to": day} for day in data.dates]

        def figures(account: Any, sign: int) -> list[Decimal]:
            values = data.balances.get(account.pk, [ZERO] * width)
            return [sign * v for v in values]

        def group(
            key: str, label: Any, subtypes: tuple[str, ...], sign: int, level: int = 1
        ) -> list[Decimal]:
            members = [a for a in data.accounts if a.subtype in subtypes]
            if key == "non_current_assets":
                members = _ordered_non_current(members)
            shown = [a for a in members if any(figures(a, sign))]
            rows.append(ReportRow(f"group:{key}", str(label), "section", level=level))
            for account in shown:
                rows.append(
                    ReportRow(
                        f"account:{account.code}",
                        _label(account),
                        values=_v(figures(account, sign)),
                        level=level + (2 if account.subtype == "accumulated_amortisation" else 1),
                        drill={
                            "account": account.code,
                            "book": params["book"],
                            "columns": drill_columns,
                        },
                    )
                )
            total = _sum([figures(a, sign) for a in shown], width)
            rows.append(
                ReportRow(
                    f"total:{key}",
                    _("Total %(group)s") % {"group": str(label).lower()},
                    "total",
                    _v(total),
                    level=level,
                )
            )
            return total

        rows.append(ReportRow("section:assets", _("Assets"), "section"))
        current = group("current_assets", _("Current assets"), CURRENT_ASSETS, 1)
        non_current = group("non_current_assets", _("Non-current assets"), NON_CURRENT_ASSETS, 1)
        assets = [a + b for a, b in zip(current, non_current, strict=True)]
        rows.append(ReportRow("total:assets", _("Total assets"), "total", _v(assets)))

        rows.append(ReportRow("section:liabilities", _("Liabilities"), "section"))
        short = group("current_liabilities", _("Current liabilities"), CURRENT_LIABILITIES, -1)
        long = group("long_term_liabilities", _("Long-term liabilities"), LONG_TERM_LIABILITIES, -1)
        liabilities = [a + b for a, b in zip(short, long, strict=True)]
        rows.append(
            ReportRow("total:liabilities", _("Total liabilities"), "total", _v(liabilities))
        )

        rows.append(ReportRow("section:equity", _("Equity"), "section"))
        equity_accounts = [a for a in data.accounts if a.subtype in EQUITY]
        for account in equity_accounts:
            values = figures(account, -1)
            if any(values):
                rows.append(
                    ReportRow(
                        f"account:{account.code}",
                        _label(account),
                        values=_v(values),
                        level=1,
                        drill={
                            "account": account.code,
                            "book": params["book"],
                            "columns": drill_columns,
                        },
                    )
                )
        re_accounts = [a for a in data.accounts if a.subtype == "retained_earnings"]
        retained = [
            r + sum((figures(a, -1)[i] for a in re_accounts), ZERO)
            for i, r in enumerate(data.retained)
        ]
        rows.append(
            ReportRow(
                "retained_earnings",
                _("Retained earnings"),
                values=_v(retained),
                level=1,
                drill={
                    "account": re_accounts[0].code,
                    "book": params["book"],
                    "columns": drill_columns,
                }
                if re_accounts
                else None,
            )
        )
        cye_accounts = [a for a in data.accounts if a.subtype == "current_year_earnings"]
        current_year = [
            c + sum((figures(a, -1)[i] for a in cye_accounts), ZERO)
            for i, c in enumerate(data.current_year)
        ]
        rows.append(
            ReportRow(
                "current_year_earnings",
                _("Current year earnings"),
                values=_v(current_year),
                level=1,
            )
        )
        equity = [
            sum((figures(a, -1)[i] for a in equity_accounts), ZERO) + retained[i] + current_year[i]
            for i in range(width)
        ]
        rows.append(ReportRow("total:equity", _("Total equity"), "total", _v(equity)))
        return rows

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        by_key = {row.key: row for row in rows}
        liabilities = by_key["total:liabilities"].values
        equity = by_key["total:equity"].values
        both = [(a or ZERO) + (b or ZERO) for a, b in zip(liabilities, equity, strict=True)]
        return [
            ReportRow(
                "total:liabilities_and_equity", _("Total liabilities and equity"), "total", _v(both)
            )
        ]

    def alerts(self, organisation: Any, result: Any) -> list[dict[str, Any]]:
        by_key = {row.key: row for row in [*result.rows, *result.totals]}
        assets = by_key["total:assets"].values
        other = by_key["total:liabilities_and_equity"].values
        found = []
        for column, a, b in zip(result.columns, assets, other, strict=True):
            alert = _imbalance(column.label, a or ZERO, b or ZERO)
            if alert:
                found.append(alert)
        return found


# ---- movements in equity (K-02-T12) -------------------------------------------------------


def earnings_at(organisation: Any, dates: list[dt.date], book: str) -> list[Decimal]:
    """Retained earnings + current-year earnings + dividends on each date, as the balance sheet
    shows them (credit positive; dividends, a debit, reduce it)."""
    data = balance_figures(organisation, dates, book)
    held = [
        a
        for a in data.accounts
        if a.subtype in ("retained_earnings", "current_year_earnings", "dividends")
    ]
    return [
        data.retained[i]
        + data.current_year[i]
        - sum((data.balances.get(a.pk, [ZERO] * len(dates))[i] for a in held), ZERO)
        for i in range(len(dates))
    ]


@register
class MovementsInEquityReport(ReportDefinition):
    id = "retained_earnings"
    slug = "retained-earnings"
    name = _lazy("Statement of retained earnings")
    description = _lazy(
        "Opening retained earnings, net income, dividends, other movements and closing retained "
        "earnings for a period, with comparisons."
    )
    category = "financial"
    keywords = (_lazy("movements in equity"), _lazy("retained earnings"), "bénéfices non répartis")
    params = ProfitAndLossReport.params

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [Column(f"p{i}", _range_label(r)) for i, r in enumerate(_period_columns(params))]

    def query(self, organisation: Any, params: dict[str, Any]) -> dict[str, Any]:
        from .aggregation import period_movements

        ranges = _period_columns(params)
        book = params["book"]
        accounts = _accounts()
        dividends = [a.pk for a in accounts if a.subtype == "dividends"]
        moves = period_movements(ranges, book=book, accounts=dividends) if dividends else {}
        return {
            "ranges": ranges,
            "opening": earnings_at(
                organisation, [r.start - dt.timedelta(days=1) for r in ranges], book
            ),
            "closing": earnings_at(organisation, [r.end for r in ranges], book),
            "net_income": net_income(pnl_figures(ranges, book)),
            "dividends": [-v for v in _sum(list(moves.values()), len(ranges))],
        }

    def rows(self, data: dict[str, Any], params: dict[str, Any]) -> list[ReportRow]:
        opening, closing = data["opening"], data["closing"]
        income, dividends = data["net_income"], data["dividends"]
        other = [
            c - o - n - d for c, o, n, d in zip(closing, opening, income, dividends, strict=True)
        ]
        rows = [
            ReportRow(
                "opening", _("Retained earnings at the beginning of the period"), values=_v(opening)
            ),
            ReportRow("net_income", _("Net income"), values=_v(income), level=1),
            ReportRow("dividends", _("Dividends"), values=_v(dividends), level=1),
        ]
        if any(other):
            rows.append(ReportRow("other", _("Other movements"), values=_v(other), level=1))
        return rows

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        width = len(rows[0].values)
        closing = _sum([r.values for r in rows], width)
        return [
            ReportRow(
                "closing", _("Retained earnings at the end of the period"), "total", _v(closing)
            )
        ]


# ---- integrity (K-02-T05) ------------------------------------------------------------------


def _imbalance(label: str, assets: Decimal, other: Decimal) -> dict[str, Any] | None:
    if assets == other:
        return None
    return {
        "code": "reports.integrity.unbalanced",
        "level": "error",
        "message": _(
            "The balance sheet at %(date)s doesn't balance by %(difference)s — the books need a "
            "look before this is used."
        )
        % {"date": label, "difference": f"{abs(assets - other):.2f}"},
        "detail": {"assets": f"{assets:.2f}", "liabilities_and_equity": f"{other:.2f}"},
    }


def _earnings_change(organisation: Any, span: DateRange, book: str) -> Decimal:
    """Δ (retained earnings + current-year earnings) over the period, from the balance sheet's
    balances. Entries posted straight to the retained earnings accounts (opening balances, a
    conversion) are other movements in equity, not income, so they are left out."""
    data = balance_figures(organisation, [span.start - dt.timedelta(days=1), span.end], book)
    return (data.retained[1] + data.current_year[1]) - (data.retained[0] + data.current_year[0])


def _earnings_mismatch(label: str, income: Decimal, change: Decimal) -> dict[str, Any] | None:
    if income == change:
        return None
    return {
        "code": "reports.integrity.earnings",
        "level": "error",
        "message": _(
            "Net income for %(period)s (%(income)s) doesn't equal the change in retained and "
            "current year earnings (%(change)s) — the books need a look before this is used."
        )
        % {"period": label, "income": f"{income:.2f}", "change": f"{change:.2f}"},
        "detail": {"net_income": f"{income:.2f}", "earnings_change": f"{change:.2f}"},
    }


def integrity(organisation: Any, as_of: dt.date, book: str = "accounting") -> list[dict[str, Any]]:
    """Both checks on one date: the balance sheet balances, and the financial year's net income
    equals the change in retained and current-year earnings since its start."""
    from numo9.tenancy.context import org_context

    with org_context(organisation):
        sheet = registry_get("balance_sheet").run(organisation, {"as_of": as_of, "book": book})
        span = DateRange(fiscal_start(organisation, as_of), as_of)
        income = net_income(pnl_figures([span], book))[0]
        change = _earnings_change(organisation, span, book)
    alerts = list(sheet.alerts)
    mismatch = _earnings_mismatch(_range_label(span), income, change)
    return [*alerts, mismatch] if mismatch else alerts


def registry_get(report_id: str) -> Any:
    from .engine import registry

    return registry.get(report_id)
