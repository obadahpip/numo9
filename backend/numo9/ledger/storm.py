"""Posting storm (C-02-T12): many concurrent postings through the real service.

``post_storm(organisation, n=1000, workers=20)`` posts ``n`` balanced journals from ``workers``
threads, each on its own database connection, all at once (a barrier releases them together).
Every ``fail_every``-th posting fails **after** its lines were written and its number taken (the
transaction is rolled back), which is exactly where a gap could appear.

The report (``StormReport``) checks what C-02 promises under load:

- the posted numbers are exactly ``1..n`` (no gap, no duplicate) — the failed postings gave their
  numbers back;
- every entry balances and both books' trial balances sum to zero;
- no line of a failed posting is left behind.

Used by ``tests/test_ledger_post_storm.py`` (CI) and ``manage.py post_storm --n 1000`` against a
staging copy (it posts real journals: never run it on production data).
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Count, F, Q, Sum

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import Account, AccountStatus, JournalEntry, JournalLine, JournalStatus
from .services import post_journal
from .trial_balance import trial_balance
from .validation import JournalSpec, LineSpec


class StormFailure(RuntimeError):
    """The deliberate failure of every ``fail_every``-th posting (rolled back)."""


@dataclass
class StormReport:
    posted: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    numbers: list[int] = field(default_factory=list)
    unbalanced: list[int] = field(default_factory=list)
    books_balanced: bool = False
    orphan_lines: int = 0
    seconds: float = 0.0

    @property
    def gap_free(self) -> bool:
        return self.numbers == list(range(1, len(self.numbers) + 1))

    @property
    def ok(self) -> bool:
        return (
            not self.errors
            and self.gap_free
            and not self.unbalanced
            and self.books_balanced
            and self.orphan_lines == 0
        )


def _accounts(organisation: Organisation) -> list[Account]:
    with org_context(organisation):
        accounts = [
            a
            for a in Account.objects.filter(status=AccountStatus.ACTIVE).order_by("code")
            if not a.children.exists()
        ][:2]
    if len(accounts) < 2:
        raise ValueError("The organisation needs at least two active leaf accounts.")
    return accounts


def post_storm(
    organisation: Organisation,
    *,
    n: int = 1000,
    workers: int = 20,
    fail_every: int = 0,
    date: dt.date | None = None,
) -> StormReport:
    """Post ``n`` journals from ``workers`` threads at once (successful postings: ``n``)."""
    debit_account, credit_account = _accounts(organisation)
    day = date or dt.date.today()
    report = StormReport()
    lock = threading.Lock()
    counter = iter(range(1, 10**9))
    barrier = threading.Barrier(workers)

    def one(index: int) -> None:
        amount = Decimal(index % 9973 + 1) / 100
        spec = JournalSpec(
            date=day,
            narration=f"Storm {index}",
            lines=(
                LineSpec(debit_account, debit=amount),
                LineSpec(credit_account, credit=amount),
            ),
        )
        fail = fail_every and index % fail_every == 0
        with transaction.atomic():
            post_journal(spec, user=None)
            if fail:
                raise StormFailure(index)

    def worker() -> None:
        try:
            with org_context(organisation):
                barrier.wait()
                while True:
                    with lock:
                        if report.posted >= n:
                            return
                        index = next(counter)
                        report.posted += 1  # reserved; given back below if it fails
                    try:
                        one(index)
                    except StormFailure:
                        with lock:
                            report.posted -= 1
                            report.failed += 1
        except Exception as error:  # pragma: no cover - reported, not raised
            with lock:
                report.errors.append(repr(error))
        finally:
            connection.close()

    started = time.monotonic()
    threads = [threading.Thread(target=worker, name=f"storm-{i}") for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    report.seconds = time.monotonic() - started

    with org_context(organisation):
        report.numbers = list(
            JournalEntry.objects.filter(status=JournalStatus.POSTED)
            .order_by("number")
            .values_list("number", flat=True)
        )
        sums = JournalEntry.objects.annotate(
            d=Sum("lines__debit"), c=Sum("lines__credit"), k=Count("lines")
        ).filter(~Q(d=F("c")) | Q(k__lt=2))
        report.unbalanced = [e.number for e in sums]
        report.books_balanced = all(
            trial_balance(book).total_balance == 0 for book in ("accounting", "tax")
        )
        report.orphan_lines = JournalLine.objects.exclude(
            entry__status__in=[JournalStatus.POSTED, JournalStatus.REVERSED]
        ).count()
    return report
