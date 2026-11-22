"""Account register (F-01-T11): every transaction of a bank account with its running balance.

``register(bank, filters)`` lists the lines of the account's ledger account in the **accounting
view** (lines of ``book = both`` and ``accounting``) of posted and reversed entries — spend and
receive money, transfers, journals, payments: anything that moved the account — oldest first
(date, journal number, line), each with:

- ``received`` (debit) and ``spent`` (credit), the **running balance** after it (debits minus
  credits, the same sign as ``ledger_balance``);
- the journal (id, number, type, status), the contact, the description (the line's, else the
  journal's narration) and the reference (the bank transaction's, when it came from one), the
  bank transaction id and whether it was voided.

The running balance is computed over the **whole history** before filters apply, so a filtered
list still shows true balances; with no filter the last row's balance equals the account's ledger
balance. Filters: ``date_from`` / ``date_to``, ``contact`` (public id), ``amount_min`` /
``amount_max`` (on the amount that moved, either side), ``status`` (``posted`` / ``reversed``).

``export_register(bank, rows, fmt)`` writes the rows as CSV (UTF-8 with BOM, for Excel) or XLSX.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import LOCKED_STATUSES, JournalLine
from numo9.ledger.sequence import format_journal_number
from numo9.tenancy.context import org_context

from .balances import BOOKS
from .models import BankAccount, BankTransaction, BankTransactionStatus
from .transactions import SOURCE_TYPE

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class RegisterFilters:
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    contact: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    status: str | None = None

    def match(self, row: dict[str, Any]) -> bool:
        amount = row["received"] or row["spent"]
        return not (
            (self.date_from and row["date"] < self.date_from)
            or (self.date_to and row["date"] > self.date_to)
            or (self.contact and (row["contact"] or {}).get("id") != self.contact)
            or (self.amount_min is not None and amount < self.amount_min)
            or (self.amount_max is not None and amount > self.amount_max)
            or (self.status and row["status"] != self.status)
        )


def register(bank: BankAccount, filters: RegisterFilters | None = None) -> list[dict[str, Any]]:
    """The register rows (module docstring), oldest first."""
    organisation = bank.organisation
    with org_context(organisation):
        lines = list(
            JournalLine.objects.filter(
                account_id=bank.gl_account_id,
                book__in=BOOKS,
                entry__status__in=sorted(LOCKED_STATUSES),
            )
            .select_related("entry", "contact")
            .order_by("entry__date", "entry__number", "entry_id", "line_no")
        )
        sources = {
            line.entry.source_id
            for line in lines
            if line.entry.source_type == SOURCE_TYPE and line.entry.source_id
        }
        txns = {str(t.public_id): t for t in BankTransaction.objects.filter(public_id__in=sources)}
    rows: list[dict[str, Any]] = []
    balance = ZERO
    for line in lines:
        entry = line.entry
        balance += line.debit - line.credit
        txn = txns.get(entry.source_id) if entry.source_type == SOURCE_TYPE else None
        rows.append(
            {
                "id": f"{entry.public_id}:{line.line_no}",
                "date": entry.date,
                "journal": {
                    "id": str(entry.public_id),
                    "number": format_journal_number(organisation, entry.number)
                    if entry.number
                    else "",
                    "type": entry.type,
                },
                "status": entry.status,
                "contact": {"id": str(line.contact.public_id), "name": line.contact.display_name}
                if line.contact_id and line.contact is not None
                else None,
                "description": line.description or entry.narration,
                "reference": txn.reference if txn else "",
                "transaction": str(txn.public_id) if txn else None,
                "voided": bool(txn and txn.status == BankTransactionStatus.VOIDED),
                "received": line.debit,
                "spent": line.credit,
                "balance": balance,
            }
        )
    if filters is not None:
        rows = [row for row in rows if filters.match(row)]
    return rows


def _headers() -> list[str]:
    return [
        _("Date"),
        _("Journal"),
        _("Contact"),
        _("Description"),
        _("Reference"),
        _("Received"),
        _("Spent"),
        _("Balance"),
        _("Status"),
    ]


def _cells(row: dict[str, Any]) -> list[Any]:
    return [
        row["date"].isoformat(),
        row["journal"]["number"],
        (row["contact"] or {}).get("name", ""),
        row["description"],
        row["reference"],
        f"{row['received']:.2f}" if row["received"] else "",
        f"{row['spent']:.2f}" if row["spent"] else "",
        f"{row['balance']:.2f}",
        row["status"],
    ]


def export_register(
    bank: BankAccount, rows: list[dict[str, Any]], fmt: str
) -> tuple[bytes, str, str]:
    """``(content, content type, file name)`` of the register as CSV or XLSX."""
    stamp = dt.date.today().isoformat()
    slug = "".join(c if c.isalnum() else "-" for c in bank.display_name.lower()).strip("-")
    if fmt == "xlsx":
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.title = bank.display_name[:31] or "Register"
        sheet.append(_headers())
        for row in rows:
            cells = _cells(row)
            for index in (5, 6, 7):  # amounts as numbers
                cells[index] = float(cells[index]) if cells[index] else None
            sheet.append(cells)
        out = io.BytesIO()
        book.save(out)
        return (
            out.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{slug}-{stamp}.xlsx",
        )
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(_headers())
    writer.writerows(_cells(row) for row in rows)
    return ("﻿" + text.getvalue()).encode(), "text/csv; charset=utf-8", f"{slug}-{stamp}.csv"
