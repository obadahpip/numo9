"""Ledger balance of a bank account (F-01-T06), cached per account.

``ledger_balance(bank, as_of=None)`` is the **accounting view** of the account's ledger account:
debits minus credits of its lines in the accounting book (lines of ``book = both`` and
``accounting``) of posted and reversed entries (a reversal is itself posted, so a reversed pair
nets to zero), dated on or before ``as_of`` when given. It is the same figure as the account's row
of the accounting-book trial balance — the balance shown on the banking screens, never edited
directly. A credit card or loan owed reads negative (credit balance).

Each answer is cached per account and date. Every journal the posting service writes (posted,
reversed, a draft saved) bumps the version of each account it touches — at once and again when
the transaction commits — so the next read recomputes: the cache is never stale after a post.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from functools import partial
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

from numo9.ledger.models import LOCKED_STATUSES, Book, JournalEntry, JournalLine
from numo9.tenancy.context import org_context

from .models import BankAccount

ZERO = Decimal("0.00")
TIMEOUT = 60 * 60 * 24
BOOKS = (Book.BOTH, Book.ACCOUNTING)


def _version_key(account_id: int) -> str:
    return f"banking:balance:{account_id}:version"


def balance_version(account_id: int) -> int:
    key = _version_key(account_id)
    version = cache.get(key)
    if version is None:
        cache.add(key, 1, None)
        version = cache.get(key, 1)
    return int(version)


def bust_balance(account_id: int) -> None:
    key = _version_key(account_id)
    try:
        cache.incr(key)
    except ValueError:  # not set yet (or evicted): any new value invalidates old entries
        cache.set(key, balance_version(account_id) + 1, None)


def entry_written(entry: JournalEntry) -> None:
    """Posting-service hook: bust the balance of every account the entry has a line on."""
    with org_context(entry.organisation):
        ids = set(JournalLine.objects.filter(entry=entry).values_list("account_id", flat=True))
    for account_id in ids:
        bust_balance(account_id)
        transaction.on_commit(partial(bust_balance, account_id))


def _compute(organisation: Any, account_id: int, as_of: dt.date | None) -> Decimal:
    with org_context(organisation):
        lines = JournalLine.objects.filter(
            account_id=account_id,
            book__in=BOOKS,
            entry__status__in=sorted(LOCKED_STATUSES),
        )
        if as_of is not None:
            lines = lines.filter(entry__date__lte=as_of)
        totals = lines.aggregate(
            debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO)
        )
    return Decimal(totals["debit"] - totals["credit"]).quantize(Decimal("0.01"))


def ledger_balance(bank: BankAccount, as_of: dt.date | None = None) -> Decimal:
    """The account's ledger balance (module docstring), from the cache when it is current."""
    account_id = int(bank.gl_account_id)
    key = (
        f"banking:balance:{account_id}:{balance_version(account_id)}:"
        f"{as_of.isoformat() if as_of else 'all'}"
    )
    cached = cache.get(key)
    if cached is not None:
        return Decimal(cached)
    value = _compute(bank.organisation, account_id, as_of)
    cache.set(key, str(value), TIMEOUT)
    return value


def ledger_balances(
    banks: Iterable[BankAccount], as_of: dt.date | None = None
) -> dict[int, Decimal]:
    """``{bank account pk: ledger balance}`` for several accounts (the banking home)."""
    return {bank.pk: ledger_balance(bank, as_of) for bank in banks}
