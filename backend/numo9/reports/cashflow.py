"""Cash flow statements (K-02-T07, T08), as ``docs/specs/financial-statements.md`` §3.

**Cash** is the ledger accounts whose bank account type the cash definition includes
(``cash_types``): chequing, savings and cash by default; a ``bank`` sub-type account without a
banking profile counts as chequing. Every other account is classified by its sub-type, so the
sections always add up to the change in cash:

- **operating** — net income; amortization added back (the movement of the accumulated
  amortization accounts, so a write-down straight to the asset still balances); changes in working
  capital (non-cash current assets: an increase uses cash; current liabilities: an increase
  provides cash);
- **investing** — fixed, intangible and other non-current assets;
- **financing** — long-term liabilities and equity (share capital, other equity, dividends, the
  retained and current-year earnings accounts).

**Direct method** (K-02-T08): each cash movement is classified by the **other side** of its
journal — every non-cash line of a journal that touches cash, its movement with the sign turned
(a balanced journal's other lines add up to minus its cash lines, so the categories add up to the
change in cash exactly): receipts from customers (AR, revenue, other income), payments to
suppliers (AP, expenses, inventory, prepayments), payroll, sales taxes, income taxes, investing,
financing, other. A transfer between two cash accounts has no other side and is no flow.

The statement checks itself: net change in cash = cash at the end − cash at the start; a
difference is an integrity alert (K-02-T05).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .engine import Column, ParamSpec, ReportDefinition, ReportRow, register
from .parameters import COMPARISONS, DateRange
from .statements import (
    BOOKS,
    PNL_TYPES,
    ZERO,
    _accounts,
    _label,
    _period_columns,
    _range_label,
    _sum,
    _v,
    net_income,
    pnl_figures,
)

#: Bank account types that are cash unless the organisation chooses otherwise (K-02-T09).
DEFAULT_CASH_TYPES: tuple[str, ...] = ("chequing", "savings", "cash")

WORKING_CAPITAL_ASSETS = ("bank", "current_asset", "inventory", "prepayment")
WORKING_CAPITAL_LIABILITIES = ("current_liability", "sales_tax_control", "payroll_liability")
INVESTING = ("fixed_asset", "intangible", "non_current_asset")
FINANCING = (
    "non_current_liability",
    "share_capital",
    "other_equity",
    "dividends",
    "retained_earnings",
    "current_year_earnings",
)
CONTRA = "accumulated_amortisation"


def cash_types(organisation: Any) -> tuple[str, ...]:
    return DEFAULT_CASH_TYPES


def cash_account_ids(organisation: Any) -> set[int]:
    """The ledger accounts that are cash under the organisation's cash definition."""
    from numo9.banking.models import BankAccount

    types = set(cash_types(organisation))
    profiles = dict(
        BankAccount.objects.filter(deleted_at__isnull=True).values_list("gl_account_id", "type")
    )
    ids = {pk for pk, kind in profiles.items() if kind in types}
    if "chequing" in types:
        ids |= {a.pk for a in _accounts() if a.subtype == "bank" and a.pk not in profiles}
    return ids


def _movements(ranges: list[DateRange], book: str) -> dict[int, list[Decimal]]:
    from .aggregation import period_movements

    return period_movements(ranges, book=book)


def cash_change(organisation: Any, ranges: list[DateRange], book: str) -> list[Decimal]:
    moves = _movements(ranges, book)
    cash = cash_account_ids(organisation)
    return _sum([v for pk, v in moves.items() if pk in cash], len(ranges))


def cash_balances(organisation: Any, dates: Sequence[dt.date], book: str) -> list[Decimal]:
    from .aggregation import balances_at

    cash = cash_account_ids(organisation)
    balances = balances_at(list(dates), book=book, accounts=list(cash)) if cash else {}
    return _sum(list(balances.values()), len(dates))


def _integrity(
    columns: Sequence[Column], flows: Sequence[Decimal | None], cash: Sequence[Decimal]
) -> list[dict[str, Any]]:
    alerts = []
    for column, flow, actual in zip(columns, flows, cash, strict=True):
        if (flow or ZERO) != actual:
            alerts.append(
                {
                    "code": "reports.integrity.cash",
                    "level": "error",
                    "message": _(
                        "The net change in cash for %(period)s (%(flow)s) doesn't equal the "
                        "change in the cash accounts (%(cash)s) — the books need a look before "
                        "this is used."
                    )
                    % {
                        "period": column.label,
                        "flow": f"{flow or ZERO:.2f}",
                        "cash": f"{actual:.2f}",
                    },
                    "detail": {"net_change": f"{flow or ZERO:.2f}", "cash_change": f"{actual:.2f}"},
                }
            )
    return alerts


class _CashFlowBase(ReportDefinition):
    category = "financial"
    params = (
        ParamSpec("date_from", "date", required=True),
        ParamSpec("date_to", "date", required=True),
        ParamSpec("compare", "choice", "none", COMPARISONS),
        ParamSpec("periods", "int", 1),
        ParamSpec("book", "choice", "accounting", BOOKS),
    )

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [Column(f"p{i}", _range_label(r)) for i, r in enumerate(_period_columns(params))]

    def _cash_rows(self, organisation: Any, params: dict[str, Any]) -> list[ReportRow]:
        ranges = _period_columns(params)
        opening = cash_balances(
            organisation, [r.start - dt.timedelta(days=1) for r in ranges], params["book"]
        )
        closing = cash_balances(organisation, [r.end for r in ranges], params["book"])
        return [
            ReportRow("cash_opening", _("Cash at the beginning of the period"), values=_v(opening)),
            ReportRow("cash_closing", _("Cash at the end of the period"), "total", _v(closing)),
        ]

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        width = len(_period_columns(params))
        sections = [r.values for r in rows if r.key.startswith("total:")]
        change = [sum(((v[i] or ZERO) for v in sections), ZERO) for i in range(width)]
        return [ReportRow("net_change", _("Net change in cash"), "total", _v(change))]

    def run(self, organisation: Any, raw: Any = None) -> Any:
        """The statement, then cash at the beginning and end of each period under the totals."""
        import dataclasses

        from numo9.tenancy.context import org_context

        result = super().run(organisation, raw)
        with org_context(organisation):
            cash = self._cash_rows(organisation, result.params)
        return dataclasses.replace(result, totals=[*result.totals, *cash])

    def alerts(self, organisation: Any, result: Any) -> list[dict[str, Any]]:
        change = next(r for r in result.totals if r.key == "net_change").values
        ranges = _period_columns(result.params)
        return _integrity(
            result.columns, change, cash_change(organisation, ranges, result.params["book"])
        )


@register
class CashFlowIndirectReport(_CashFlowBase):
    id = "cash_flow"
    slug = "cash-flow"
    name = _lazy("Cash flow statement")
    description = _lazy(
        "Where cash came from and went for a period: operating (indirect method), investing and "
        "financing activities."
    )
    keywords = (_lazy("statement of cash flows"), _lazy("indirect method"), "flux de trésorerie")

    def query(self, organisation: Any, params: dict[str, Any]) -> dict[str, Any]:
        ranges = _period_columns(params)
        cash = cash_account_ids(organisation)
        return {
            "ranges": ranges,
            "accounts": [a for a in _accounts() if a.pk not in cash and a.type not in PNL_TYPES],
            "moves": _movements(ranges, params["book"]),
            "net_income": net_income(pnl_figures(ranges, params["book"])),
        }

    def rows(self, data: dict[str, Any], params: dict[str, Any]) -> list[ReportRow]:
        ranges: list[DateRange] = data["ranges"]
        width = len(ranges)
        moves: dict[int, list[Decimal]] = data["moves"]
        rows: list[ReportRow] = []
        drill_columns = [{"from": r.start, "to": r.end} for r in ranges]

        def change(account: Any) -> list[Decimal]:
            # A debit movement on a non-cash account is cash used (and a credit cash provided).
            return [-v for v in moves.get(account.pk, [ZERO] * width)]

        def line(account: Any, values: list[Decimal], label: str | None = None) -> None:
            rows.append(
                ReportRow(
                    f"account:{account.code}",
                    label or _label(account),
                    values=_v(values),
                    level=1,
                    drill={
                        "account": account.code,
                        "book": params["book"],
                        "columns": drill_columns,
                    },
                )
            )

        def section(key: str, label: str, members: list[Any], lead: list[ReportRow]) -> None:
            rows.append(ReportRow(f"section:{key}", label, "section"))
            rows.extend(lead)
            shown = [(a, change(a)) for a in members if any(change(a))]
            for account, values in shown:
                line(account, values)
            total = _sum([r.values for r in lead] + [v for _a, v in shown], width)
            rows.append(
                ReportRow(
                    f"total:{key}",
                    _("Net cash from %(section)s") % {"section": label.lower()},
                    "total",
                    _v(total),
                )
            )

        accounts = data["accounts"]
        contras = [a for a in accounts if a.subtype == CONTRA]
        amortisation = _sum([change(a) for a in contras], width)
        lead = [
            ReportRow("net_income", _("Net income"), values=_v(data["net_income"]), level=1),
        ]
        if any(amortisation):
            lead.append(
                ReportRow(
                    "amortisation", _("Add back amortization"), values=_v(amortisation), level=1
                )
            )
        working = [
            a for a in accounts if a.subtype in WORKING_CAPITAL_ASSETS + WORKING_CAPITAL_LIABILITIES
        ]
        section("operating", str(_("Operating activities")), working, lead)
        section(
            "investing",
            str(_("Investing activities")),
            [a for a in accounts if a.subtype in INVESTING],
            [],
        )
        section(
            "financing",
            str(_("Financing activities")),
            [a for a in accounts if a.subtype in FINANCING],
            [],
        )
        return rows


#: Direct-method categories in order: (key, label).
DIRECT_CATEGORIES: tuple[tuple[str, Any], ...] = (
    ("customers", _lazy("Receipts from customers")),
    ("suppliers", _lazy("Payments to suppliers")),
    ("payroll", _lazy("Payroll")),
    ("sales_taxes", _lazy("Sales taxes")),
    ("income_taxes", _lazy("Income taxes")),
    ("other_operating", _lazy("Other operating cash flows")),
    ("investing", _lazy("Investing activities")),
    ("financing", _lazy("Financing activities")),
)
CUSTOMER_SUBTYPES = ("revenue", "other_income")
PAYROLL_ROLES = frozenset(
    {
        "wages_payable",
        "cpp_payable",
        "qpp_payable",
        "ei_payable",
        "qpip_payable",
        "income_tax_withheld",
        "vacation_payable",
        "workers_comp_payable",
        "eht_payable",
    }
)
SUPPLIER_SUBTYPES = (
    "cost_of_sales",
    "operating_expense",
    "amortisation",
    "other_expense",
    "inventory",
    "prepayment",
)


def direct_category(account: Any) -> str:
    role = account.system_role or ""
    if role == "ar" or account.subtype in CUSTOMER_SUBTYPES:
        return "customers"
    if role == "ap" or account.subtype in SUPPLIER_SUBTYPES:
        return "suppliers"
    if account.subtype == "payroll_liability" or role in PAYROLL_ROLES:
        return "payroll"
    if account.subtype == "sales_tax_control":
        return "sales_taxes"
    if account.subtype == "income_tax":
        return "income_taxes"
    if account.subtype in (*INVESTING, CONTRA):
        return "investing"
    if account.subtype in FINANCING:
        return "financing"
    return "other_operating"


def direct_flows(organisation: Any, ranges: list[DateRange], book: str) -> dict[str, list[Decimal]]:
    from django.db.models import Sum

    from .aggregation import _lines, _net

    cash = cash_account_ids(organisation)
    categories = {a.pk: direct_category(a) for a in _accounts()}
    flows = {key: [ZERO] * len(ranges) for key, _label in DIRECT_CATEGORIES}
    if not cash:
        return flows
    for i, span in enumerate(ranges):
        lines = _lines(book, None, None).filter(date__gte=span.start, date__lte=span.end)
        entries = lines.filter(account_id__in=cash).values("entry_id")
        sums = (
            lines.filter(entry_id__in=entries)
            .exclude(account_id__in=cash)
            .values("account_id")
            .annotate(net=Sum(_net()))
        )
        for row in sums:
            key = categories.get(row["account_id"], "other_operating")
            flows[key][i] -= row["net"] or ZERO
    return flows


@register
class CashFlowDirectReport(_CashFlowBase):
    id = "cash_flow_direct"
    slug = "cash-flow-direct"
    name = _lazy("Cash flow statement (direct method)")
    description = _lazy(
        "Cash received and paid for a period by what it was for: customers, suppliers, payroll, "
        "taxes, investing and financing."
    )
    keywords = (_lazy("direct method"), _lazy("receipts and payments"), "méthode directe")

    def query(self, organisation: Any, params: dict[str, Any]) -> dict[str, Any]:
        ranges = _period_columns(params)
        return {"ranges": ranges, "flows": direct_flows(organisation, ranges, params["book"])}

    def rows(self, data: dict[str, Any], params: dict[str, Any]) -> list[ReportRow]:
        flows: dict[str, list[Decimal]] = data["flows"]
        width = len(data["ranges"])
        operating = [key for key, _l in DIRECT_CATEGORIES if key not in ("investing", "financing")]
        rows: list[ReportRow] = [
            ReportRow("section:operating", str(_("Operating activities")), "section")
        ]
        labels = dict(DIRECT_CATEGORIES)
        for key in operating:
            if any(flows[key]):
                rows.append(
                    ReportRow(f"flow:{key}", str(labels[key]), values=_v(flows[key]), level=1)
                )
        rows.append(
            ReportRow(
                "total:operating",
                _("Net cash from operating activities"),
                "total",
                _v(_sum([flows[k] for k in operating], width)),
            )
        )
        for key in ("investing", "financing"):
            rows.append(ReportRow(f"section:{key}", str(labels[key]), "section"))
            rows.append(
                ReportRow(
                    f"total:{key}",
                    _("Net cash from %(section)s") % {"section": str(labels[key]).lower()},
                    "total",
                    _v(flows[key]),
                )
            )
        return rows
