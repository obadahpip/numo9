"""Line-level ledger reports (K-02-T10, T11), as ``docs/specs/financial-statements.md`` §4.

- ``general_ledger`` — every account with activity or an opening balance, sorted by code: the
  opening balance, each posted line of the period (date, journal number, narration) with its
  debit, credit and **running balance**, then the closing balance, which equals the trial
  balance's;
- ``account_transactions`` — the same for one account (``account`` = its code).

Balances are debit-positive (net = debit − credit), the way the trial balance computes them.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .engine import Column, ParamSpec, ReportDefinition, ReportError, ReportRow, register
from .statements import BOOKS, ZERO, _accounts, _label


def _line_label(line: Any) -> str:
    from numo9.documents.formatting import format_date

    number = line.entry.number
    parts = [format_date(line.date or line.entry.date)]
    if number:
        parts.append(_("Journal %(number)s") % {"number": number})
    text = line.description or line.entry.narration
    if text:
        parts.append(text)
    return " · ".join(parts)


def ledger_detail(
    start: dt.date, end: dt.date, book: str, codes: Sequence[str] | None = None
) -> list[tuple[Any, Decimal, list[Any]]]:
    """(account, opening balance, lines of the period in date and number order) per account."""
    from .aggregation import _lines, balances_at

    accounts = [a for a in _accounts() if codes is None or a.code in codes]
    ids = [a.pk for a in accounts]
    opening = balances_at([start - dt.timedelta(days=1)], book=book, accounts=ids)
    lines = (
        _lines(book, None, ids)
        .filter(date__gte=start, date__lte=end)
        .select_related("entry")
        .order_by("account__code", "date", "entry__number", "entry_id", "line_no")
    )
    by_account: dict[int, list[Any]] = {}
    for line in lines:
        by_account.setdefault(line.account_id, []).append(line)
    out = []
    for account in accounts:
        before = opening.get(account.pk, [ZERO])[0]
        items = by_account.get(account.pk, [])
        if before or items or codes is not None:
            out.append((account, before, items))
    return out


class _LedgerBase(ReportDefinition):
    category = "financial"

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [
            Column("debit", str(_("Debit"))),
            Column("credit", str(_("Credit"))),
            Column("balance", str(_("Balance"))),
        ]

    def _codes(self, params: dict[str, Any]) -> list[str] | None:
        return None

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        return ledger_detail(
            params["date_from"], params["date_to"], params["book"], self._codes(params)
        )

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        rows: list[ReportRow] = []
        for account, opening, lines in data:
            code = account.code
            rows.append(ReportRow(f"section:{code}", _label(account), "section"))
            rows.append(
                ReportRow(
                    f"opening:{code}",
                    _("Opening balance"),
                    values=[None, None, opening],
                    level=1,
                )
            )
            balance = opening
            debits = credits = ZERO
            for line in lines:
                balance += line.debit - line.credit
                debits += line.debit
                credits += line.credit
                rows.append(
                    ReportRow(
                        f"line:{line.entry_id}:{line.line_no}",
                        _line_label(line),
                        values=[line.debit or None, line.credit or None, balance],
                        level=1,
                    )
                )
            rows.append(
                ReportRow(
                    f"closing:{code}",
                    _("Closing balance"),
                    "total",
                    [debits, credits, balance],
                    level=1,
                    drill={
                        "account": code,
                        "book": params["book"],
                        "from": params["date_from"],
                        "to": params["date_to"],
                    },
                )
            )
        return rows

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        closing = [r for r in rows if r.key.startswith("closing:")]
        debit = sum((r.values[0] or ZERO for r in closing), ZERO)
        credit = sum((r.values[1] or ZERO for r in closing), ZERO)
        return [ReportRow("total", _("Total"), "total", [debit, credit, None])]


_PERIOD = (
    ParamSpec("date_from", "date", required=True),
    ParamSpec("date_to", "date", required=True),
    ParamSpec("book", "choice", "accounting", BOOKS),
)


@register
class GeneralLedgerReport(_LedgerBase):
    id = "general_ledger"
    slug = "general-ledger"
    name = _lazy("General ledger detail")
    description = _lazy(
        "Every posted line of each account for a period, with opening, running and closing "
        "balances."
    )
    keywords = (_lazy("GL"), _lazy("ledger detail"), "grand livre")
    params = _PERIOD


@register
class AccountTransactionsReport(_LedgerBase):
    id = "account_transactions"
    slug = "account-transactions"
    name = _lazy("Account transactions")
    description = _lazy("One account's posted lines for a period, with a running balance.")
    keywords = (_lazy("account history"), _lazy("running balance"), "transactions du compte")
    params = (ParamSpec("account", "text", required=True), *_PERIOD)

    def _codes(self, params: dict[str, Any]) -> list[str]:
        code = str(params["account"]).strip()
        if code not in {a.code for a in _accounts()}:
            raise ReportError(
                _("There's no account %(code)s.") % {"code": code}, code="reports.account.unknown"
            )
        return [code]
