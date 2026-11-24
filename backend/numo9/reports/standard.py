"""The standard reports (K-01-T02 registers the first two; K-02… add the statements).

- ``trial_balance`` — every account's debit or credit balance in one book as at a date
  (C-02-T11 ``trial_balance``), with the totals of both columns;
- ``account_activity`` — for a period, each account's debits, credits and net movement in one
  book, from posted lines; accounts without activity are left out.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from .engine import Column, ParamSpec, ReportDefinition, ReportRow, register

BOOKS = ("accounting", "tax")
ZERO = Decimal("0.00")


@register
class TrialBalanceReport(ReportDefinition):
    id = "trial_balance"
    slug = "trial-balance"
    name = _("Trial balance")
    description = _("Every account's debit or credit balance on a date, in one book.")
    category = "financial"
    keywords = (_("TB"), _("balances"), "balance de vérification")
    params = (ParamSpec("as_of", "date"), ParamSpec("book", "choice", "accounting", BOOKS))

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [Column("debit", str(_("Debit"))), Column("credit", str(_("Credit")))]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        from numo9.ledger.trial_balance import trial_balance

        return trial_balance(params["book"], as_of=params["as_of"])

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        return [
            ReportRow(
                key=f"account:{row.code}",
                label=f"{row.code} · {row.name}",
                values=[row.debit_balance or None, row.credit_balance or None],
                drill={"account": row.code, "book": params["book"], "to": params["as_of"]},
            )
            for row in data.rows
            if row.balance != 0
        ]

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        debit = sum((r.values[0] or ZERO for r in rows), ZERO)
        credit = sum((r.values[1] or ZERO for r in rows), ZERO)
        return [ReportRow("total", str(_("Total")), "total", [debit, credit])]


@register
class AccountActivityReport(ReportDefinition):
    id = "account_activity"
    slug = "account-activity"
    name = _("Account activity")
    description = _("Debits, credits and net movement of each account for a period.")
    category = "financial"
    keywords = (_("movements"), _("account summary"), "mouvements")
    params = (
        ParamSpec("date_from", "date", required=True),
        ParamSpec("date_to", "date", required=True),
        ParamSpec("book", "choice", "accounting", BOOKS),
    )

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [
            Column("debit", str(_("Debits"))),
            Column("credit", str(_("Credits"))),
            Column("net", str(_("Net movement"))),
        ]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        from numo9.ledger.models import LOCKED_STATUSES, Account, JournalLine
        from numo9.ledger.trial_balance import book_lines_filter

        start: dt.date = params["date_from"]
        end: dt.date = params["date_to"]
        sums = (
            JournalLine.objects.filter(
                entry__status__in=LOCKED_STATUSES,
                entry__date__gte=start,
                entry__date__lte=end,
                book__in=book_lines_filter(params["book"]),
            )
            .values("account_id")
            .annotate(debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO))
        )
        by_account = {row["account_id"]: row for row in sums}
        accounts = Account.objects.filter(pk__in=by_account).order_by("code")
        return [(account, by_account[account.pk]) for account in accounts]

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        return [
            ReportRow(
                key=f"account:{account.code}",
                label=f"{account.code} · {account.name}",
                values=[sums["debit"], sums["credit"], sums["debit"] - sums["credit"]],
                drill={
                    "account": account.code,
                    "book": params["book"],
                    "from": params["date_from"],
                    "to": params["date_to"],
                },
            )
            for account, sums in data
        ]

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        sums = [sum((r.values[i] or ZERO for r in rows), ZERO) for i in range(3)]
        return [ReportRow("total", str(_("Total")), "total", list(sums))]
