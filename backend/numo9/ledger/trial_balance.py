"""Trial balance per book (C-02-T11, ADR-0003 §1).

``trial_balance(book, as_of=None)`` — every account's debits, credits and net balance in one book
of the active organisation, from posted (and reversed) entries dated on or before ``as_of``:

- the **accounting** book is the lines with ``book`` ∈ {both, accounting}; the **tax** book the
  lines with ``book`` ∈ {both, tax}. The book is required: every report states which book it
  shows;
- a reversed entry stays in the ledger with its reversal, so together they net to zero; drafts and
  entries awaiting approval never count;
- one grouped query over the organisation's lines (index ``(organisation, account, book)``; with
  C-02-T03, one partition), joined to the entries for status and date, then the accounts for code
  and name;
- because every posted entry balances in each book it touches (C-02-T06), the totals are equal:
  Σ debit = Σ credit and Σ net balance = 0 — ``TrialBalance.balanced``.

Rows are in account-code order; ``balance`` = debits − credits (positive = debit balance), shown in
the Debit or Credit column of the report (``debit_balance`` / ``credit_balance``).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from numo9.tenancy.context import current_org

from .models import LOCKED_STATUSES, Account, Book, JournalLine

ZERO = Decimal("0.00")
TB_BOOKS = (Book.ACCOUNTING, Book.TAX)


@dataclass(frozen=True)
class TrialBalanceRow:
    account_id: int
    code: str
    name: str
    type: str
    debit: Decimal  # Σ debits of the account's lines in the book
    credit: Decimal  # Σ credits

    @property
    def balance(self) -> Decimal:
        return self.debit - self.credit

    @property
    def debit_balance(self) -> Decimal:
        return self.balance if self.balance > 0 else ZERO

    @property
    def credit_balance(self) -> Decimal:
        return -self.balance if self.balance < 0 else ZERO


@dataclass(frozen=True)
class TrialBalance:
    book: str
    as_of: dt.date | None
    rows: tuple[TrialBalanceRow, ...] = field(default_factory=tuple)

    @property
    def total_debit(self) -> Decimal:
        return sum((row.debit for row in self.rows), ZERO)

    @property
    def total_credit(self) -> Decimal:
        return sum((row.credit for row in self.rows), ZERO)

    @property
    def total_balance(self) -> Decimal:
        """Σ net balances — zero for every ledger the engine posted."""
        return sum((row.balance for row in self.rows), ZERO)

    @property
    def balanced(self) -> bool:
        return self.total_debit == self.total_credit and self.total_balance == ZERO


def book_lines_filter(book: str) -> list[str]:
    """The line books that make up ``book`` (both + the book itself)."""
    if book not in TB_BOOKS:
        raise ValueError(f"A trial balance is for the accounting or the tax book, not {book!r}.")
    return [Book.BOTH, book]


def trial_balance(
    book: str, as_of: dt.date | None = None, *, include_zero: bool = False
) -> TrialBalance:
    """The active organisation's trial balance in ``book`` (module docstring)."""
    organisation = current_org()
    if organisation is None:
        raise ValueError("A trial balance needs an active organisation.")
    lines = JournalLine.objects.filter(
        organisation=organisation,
        book__in=book_lines_filter(book),
        entry__status__in=sorted(LOCKED_STATUSES),
    )
    if as_of is not None:
        lines = lines.filter(entry__date__lte=as_of)
    sums = (
        lines.values("account_id")
        .annotate(debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO))
        .order_by()
    )
    totals = {row["account_id"]: (row["debit"], row["credit"]) for row in sums}
    accounts = Account._base_manager.filter(organisation=organisation, pk__in=list(totals)).only(
        "pk", "code", "name_i18n", "type"
    )
    rows = []
    for account in sorted(accounts, key=lambda item: (item.code.casefold(), item.pk)):
        debit, credit = totals[account.pk]
        if not include_zero and debit == credit:
            continue
        rows.append(
            TrialBalanceRow(account.pk, account.code, account.name, account.type, debit, credit)
        )
    return TrialBalance(book, as_of, tuple(rows))
