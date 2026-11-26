"""Query helpers shared by the rules: posted journals in scope, the ledger view, labels."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db.models import Prefetch, QuerySet, Sum

from numo9.ledger.cash_guard import is_cash
from numo9.ledger.models import (
    Account,
    AccountSubtype,
    AccountType,
    Book,
    JournalEntry,
    JournalLine,
    JournalSequence,
    JournalStatus,
    JournalType,
)

from .base import Context, Hit

ZERO = Decimal("0.00")
#: The accounting book: lines in both books or the accounting book (as the cash guard).
ACCOUNTING_VIEW = (Book.BOTH, Book.ACCOUNTING)
#: Posted and reversed entries carry ledger lines.
LEDGER_STATUSES = (JournalStatus.POSTED, JournalStatus.REVERSED)
ENTRY = "ledger.JournalEntry"
ACCOUNT = "ledger.Account"

__all__ = [
    "ACCOUNT",
    "ACCOUNTING_VIEW",
    "ENTRY",
    "LEDGER_STATUSES",
    "ZERO",
    "Numbers",
    "cash_accounts",
    "entry_hit",
    "entry_total",
    "is_cash",
    "not_fixes",
    "posted_entries",
]


def not_fixes(entries: QuerySet[JournalEntry]) -> QuerySet[JournalEntry]:
    """Leave out the engine's own correcting journals (fixes reviewed and posted by an
    accountant, K-09-T16): a fix dated back to the problem is not itself a problem."""
    return entries.exclude(assurance_findings__isnull=False)


def posted_entries(ctx: Context, *, manual: bool = False) -> QuerySet[JournalEntry]:
    """Posted journals (not reversed, not reversals) — in the scope for an incremental run —
    with their lines and accounts."""
    entries = not_fixes(
        JournalEntry.objects.filter(status=JournalStatus.POSTED, reversal_of__isnull=True)
    )
    if manual:
        entries = entries.filter(type=JournalType.MANUAL)
    if ctx.scope is not None:
        entries = entries.filter(public_id__in=sorted(ctx.scope.entries))
    lines = JournalLine.objects.select_related("account").order_by("line_no")
    return entries.prefetch_related(Prefetch("lines", queryset=lines)).order_by("date", "pk")


def accounting_lines(entry: JournalEntry) -> list[JournalLine]:
    return [line for line in entry.lines.all() if line.book in ACCOUNTING_VIEW]


def entry_total(entry: JournalEntry) -> Decimal:
    """The journal's amount: its accounting-book debits (the tax book's when it has none)."""
    lines = list(entry.lines.all())
    view = [line for line in lines if line.book in ACCOUNTING_VIEW] or lines
    return sum((line.debit for line in view), ZERO)


class Numbers:
    """Journal numbers as the organisation shows them (one query for the sequence)."""

    def __init__(self, organisation: Any) -> None:
        self.sequence = (
            JournalSequence._base_manager.filter(organisation=organisation).first()
            or JournalSequence()
        )

    def label(self, entry: JournalEntry) -> str:
        return self.sequence.format(entry.number) if entry.number else str(entry)


def entry_hit(
    entry: JournalEntry,
    numbers: Numbers,
    amount: Decimal | None,
    **details: Any,
) -> Hit:
    label = numbers.label(entry)
    return Hit(
        ENTRY,
        str(entry.public_id),
        label,
        amount,
        {
            "journal": label,
            "number": entry.number,
            "date": entry.date.isoformat(),
            "narration": entry.narration,
            **details,
        },
    )


def cash_accounts() -> QuerySet[Account]:
    return Account.objects.filter(type=AccountType.ASSET, subtype=AccountSubtype.BANK).order_by(
        "code"
    )


def daily_movements(
    account: Account, until: dt.date | None = None
) -> list[tuple[dt.date, Decimal]]:
    """The account's net movement (debits − credits) per day in the ledger view, oldest first."""
    rows = JournalLine.objects.filter(
        account=account, book__in=ACCOUNTING_VIEW, entry__status__in=LEDGER_STATUSES
    )
    if until is not None:
        rows = rows.filter(entry__date__lte=until)
    days = (
        rows.values("entry__date")
        .order_by("entry__date")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
    )
    return [(d["entry__date"], (d["debit"] or ZERO) - (d["credit"] or ZERO)) for d in days]
