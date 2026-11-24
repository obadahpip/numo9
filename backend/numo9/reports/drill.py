"""Drill-down (K-01-T05): from a report figure to its lines, and from a line to its source
document.

``drill(organisation, account=…, date_from=…, date_to=…, book=…, tracking=…, page=1)`` →
``Drill(account, total, count, page, pages, lines)``: the posted (and reversed) lines of one
account in the range and book — the same filter as the aggregation (K-01-T04) — oldest first,
50 a page. ``total`` is the sum of **every** line (debits − credits), so it equals the figure the
report showed, whatever page is read. Without ``date_from`` the lines start at the beginning of
the books (a balance-sheet figure).

Each line links to the document that posted it (``source_link``): a source type registers how its
URL is built (``register_source``); a journal without a registered source (manual journals,
reversals of them) opens the journal itself.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from .aggregation import ZERO
from .engine import ReportError
from .parameters import book_filter, tracking_filter

PAGE_SIZE = 50
SourceLink = Callable[[Any, str], str | None]
_sources: dict[str, SourceLink] = {}


def register_source(source_type: str, link: SourceLink) -> None:
    """``link(organisation, source_id)`` → the document's URL (``None``: open the journal)."""
    _sources[source_type] = link


def source_link(organisation: Any, entry: Any) -> dict[str, str]:
    org = organisation.public_id
    journal = f"/o/{org}/accounting/journals/{entry.public_id}"
    builder = _sources.get(entry.source_type)
    url = builder(organisation, entry.source_id) if builder and entry.source_id else None
    return {
        "type": entry.source_type or "ledger.journalentry",
        "url": url or journal,
        "journal_url": journal,
    }


def _builtin_sources() -> None:
    register_source(
        "sales.invoice", lambda org, sid: f"/o/{org.public_id}/sales/invoices/{sid}/email"
    )

    def bank(org: Any, sid: str) -> str | None:
        from numo9.banking.models import BankTransaction

        txn = BankTransaction.objects.filter(public_id=sid).select_related("bank_account").first()
        return f"/o/{org.public_id}/banking/{txn.bank_account.public_id}" if txn else None

    register_source("banking.banktransaction", bank)


_builtin_sources()


@dataclass(frozen=True)
class Drill:
    account: dict[str, str]
    total: Decimal
    count: int
    page: int
    pages: int
    lines: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "account": self.account,
            "total": f"{self.total:.2f}",
            "count": self.count,
            "page": self.page,
            "pages": self.pages,
            "page_size": PAGE_SIZE,
            "lines": self.lines,
        }


def drill(
    organisation: Any,
    *,
    account: str,
    date_to: dt.date,
    date_from: dt.date | None = None,
    book: str = "accounting",
    tracking: dict[str, list[str]] | None = None,
    page: int = 1,
) -> Drill:
    from numo9.ledger.models import LOCKED_STATUSES, Account, JournalLine
    from numo9.ledger.sequence import format_journal_number
    from numo9.tenancy.context import org_context

    with org_context(organisation):
        found = Account.objects.filter(code=account).first() or (
            Account.objects.filter(public_id=account).first() if _uuid(account) else None
        )
        if found is None:
            raise ReportError(f"There's no account {account!r}.", code="reports.drill.account")
        rows = JournalLine.objects.filter(
            account=found,
            book__in=book_filter(book),
            entry__status__in=LOCKED_STATUSES,
            date__lte=date_to,
        ).filter(tracking_filter(tracking))
        if date_from is not None:
            rows = rows.filter(date__gte=date_from)
        summary = rows.aggregate(
            total=Coalesce(Sum(F("debit") - F("credit")), ZERO), count=Coalesce(Sum(1), 0)
        )
        count = int(summary["count"] or 0)
        pages = max(1, math.ceil(count / PAGE_SIZE))
        if not 1 <= page <= pages:
            raise ReportError(f"There's no page {page}.", code="reports.drill.page")
        chunk = rows.select_related("entry", "contact").order_by("date", "entry_id", "line_no")[
            (page - 1) * PAGE_SIZE : page * PAGE_SIZE
        ]
        lines = [
            {
                "date": line.date.isoformat() if line.date else None,
                "journal": format_journal_number(organisation, line.entry.number)
                if line.entry.number
                else "",
                "narration": line.entry.narration,
                "description": line.description,
                "contact": line.contact.display_name if line.contact_id and line.contact else "",
                "debit": f"{line.debit:.2f}",
                "credit": f"{line.credit:.2f}",
                "amount": f"{line.debit - line.credit:.2f}",
                "status": line.entry.status,
                "source": source_link(organisation, line.entry),
            }
            for line in chunk
        ]
        return Drill(
            {"id": str(found.public_id), "code": found.code, "name": found.name},
            Decimal(summary["total"]),
            count,
            page,
            pages,
            lines,
        )


def _uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True
