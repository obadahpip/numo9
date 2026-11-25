"""Find & recode — the audit report of a batch (C-07-T08): PDF, XLSX or CSV.

``report_rows(batch)`` → one row per recoded line (``RecodeLineChange``), in entry and line
order — exactly the batch's changes:

    Journal · Date · Line · Book · Debit · Credit · Changed · Account before · Account after ·
    Tax code before · Tax code after · Tracking before · Tracking after · Contact before ·
    Contact after · Reversal · Re-post · Undone by

Accounts read ``code · name``, contacts by name, tracking ``category: option``. The header names
the batch, who ran it and when, its status, the search and the counts (recoded, excluded,
problems) and — once undone — who undid it, when and why.

``export(batch, fmt, locale)`` → ``(bytes, content type, file name)``; text that a spreadsheet
would run as a formula is written as text (CSV injection), as in the audit log export (A-04).
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import Any

from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.audit.exports import CONTENT_TYPES, _safe
from numo9.documents.formatting import format_date, format_datetime, format_money
from numo9.tenancy.context import org_context

from .models import Account, Book, JournalLine, RecodeBatch, RecodeLineChange
from .sequence import format_journal_number

FORMATS = ("csv", "xlsx", "pdf")
COLUMNS = (
    gettext_lazy("Journal"),
    gettext_lazy("Date"),
    gettext_lazy("Line"),
    gettext_lazy("Book"),
    gettext_lazy("Debit"),
    gettext_lazy("Credit"),
    gettext_lazy("Changed"),
    gettext_lazy("Account before"),
    gettext_lazy("Account after"),
    gettext_lazy("Tax code before"),
    gettext_lazy("Tax code after"),
    gettext_lazy("Tracking before"),
    gettext_lazy("Tracking after"),
    gettext_lazy("Contact before"),
    gettext_lazy("Contact after"),
    gettext_lazy("Reversal"),
    gettext_lazy("Re-post"),
    gettext_lazy("Undone by"),
)
FIELD_LABELS = {
    "account": gettext_lazy("Account"),
    "tax_code": gettext_lazy("Tax code"),
    "tracking": gettext_lazy("Tracking"),
    "contact": gettext_lazy("Contact"),
}
MONEY_COLUMNS = (4, 5)


class _Labels:
    """Account and contact names by public id, looked up once per report."""

    def __init__(self, organisation: Any, changes: list[RecodeLineChange]) -> None:
        from numo9.contacts.models import Contact

        accounts, contacts = set(), set()
        for change in changes:
            for side in (change.before, change.after):
                if side.get("account"):
                    accounts.add(side["account"])
                if side.get("contact"):
                    contacts.add(side["contact"])
        self.accounts = {
            str(a.public_id): str(a)
            for a in Account._base_manager.filter(organisation=organisation, public_id__in=accounts)
        }
        self.contacts = {
            str(public_id): name
            for public_id, name in Contact._base_manager.filter(
                organisation=organisation, public_id__in=contacts
            ).values_list("public_id", "display_name")
        }

    def account(self, value: Any) -> str:
        return self.accounts.get(str(value), str(value or "")) if value else ""

    def contact(self, value: Any) -> str:
        return self.contacts.get(str(value), str(value)) if value else ""


def _tracking(value: Any) -> str:
    return "; ".join(f"{k}: {v}" for k, v in sorted((value or {}).items()))


def _changed(change: RecodeLineChange) -> str:
    names = [n for n in FIELD_LABELS if change.before.get(n) != change.after.get(n)]
    return ", ".join(str(FIELD_LABELS[n]) for n in names)


def _changes(batch: RecodeBatch) -> list[RecodeLineChange]:
    return list(
        RecodeLineChange.objects.filter(batch=batch)
        .select_related("entry", "reversal_entry", "repost_entry")
        .order_by("entry__date", "entry_id", "line_no")
    )


def report_rows(batch: RecodeBatch, locale: str = "en-ca") -> list[list[Any]]:
    """The batch's changes, one row per recoded line (amounts as ``Decimal``)."""
    organisation = batch.organisation
    with org_context(organisation), translation.override(locale):
        changes = _changes(batch)
        labels = _Labels(organisation, changes)
        undone_by = str(batch.undone_by) if batch.undone_by_id else ""
        books = {
            (entry_id, line_no): Book(book).label
            for entry_id, line_no, book in JournalLine.objects.filter(
                entry_id__in={c.entry_id for c in changes}
            ).values_list("entry_id", "line_no", "book")
        }

        def number(entry: Any) -> str:
            return format_journal_number(organisation, entry.number) if entry is not None else ""

        return [
            [
                number(c.entry),
                format_date(c.entry.date, locale),
                c.line_no,
                str(books.get((c.entry_id, c.line_no), "")),
                c.debit,
                c.credit,
                _changed(c),
                labels.account(c.before.get("account")),
                labels.account(c.after.get("account")),
                c.before.get("tax_code") or "",
                c.after.get("tax_code") or "",
                _tracking(c.before.get("tracking")),
                _tracking(c.after.get("tracking")),
                labels.contact(c.before.get("contact")),
                labels.contact(c.after.get("contact")),
                number(c.reversal_entry),
                number(c.repost_entry),
                undone_by,
            ]
            for c in changes
        ]


def headers() -> list[str]:
    return [str(c) for c in COLUMNS]


def header_lines(batch: RecodeBatch, locale: str) -> list[str]:
    with translation.override(locale):
        out = [
            _("Recode: %(name)s") % {"name": str(batch)},
            _("Status: %(status)s") % {"status": batch.get_status_display()},
        ]
        if batch.executed_at:
            out.append(
                _("Run by %(who)s on %(when)s")
                % {
                    "who": str(batch.executed_by or _("Numo9")),
                    "when": format_datetime(batch.executed_at, locale),
                }
            )
        out.append(
            _("%(lines)d lines recoded · %(excluded)d excluded · %(problems)d not recoded")
            % {
                "lines": batch.line_count,
                "excluded": batch.excluded_count,
                "problems": sum(len(p.get("lines", [])) for p in batch.problems or []),
            }
        )
        if batch.undone_at:
            out.append(
                _("Undone by %(who)s on %(when)s: %(reason)s")
                % {
                    "who": str(batch.undone_by),
                    "when": format_datetime(batch.undone_at, locale),
                    "reason": batch.undo_reason or "—",
                }
            )
        return out


def _cell(value: Any) -> Any:
    return f"{value:.2f}" if isinstance(value, Decimal) else value


def write_csv(batch: RecodeBatch, locale: str) -> bytes:
    rows = report_rows(batch, locale)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    with translation.override(locale):
        writer.writerow(headers())
    for row in rows:
        writer.writerow([_safe(_cell(cell)) for cell in row])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def write_xlsx(batch: RecodeBatch, locale: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    rows = report_rows(batch, locale)
    with translation.override(locale):
        book = Workbook()
        sheet = book.active
        sheet.title = _("Recode")[:31]
        for line in header_lines(batch, locale):
            sheet.append([line])
        sheet.append([])
        sheet.append(headers())
        for cell in sheet[sheet.max_row]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append([_safe(cell) for cell in row])
            for index in MONEY_COLUMNS:
                sheet.cell(row=sheet.max_row, column=index + 1).number_format = "#,##0.00"
        out = io.BytesIO()
        book.save(out)
    return out.getvalue()


def write_pdf(batch: RecodeBatch, locale: str) -> bytes:
    from numo9.documents.pdf import render_pdf

    rows = report_rows(batch, locale)
    with translation.override(locale):
        context = {
            "issuer": {"legal_name": batch.organisation.name},
            "lines": header_lines(batch, locale),
            "columns": headers(),
            "rows": [
                [
                    format_money(cell, locale) if i in MONEY_COLUMNS else cell
                    for i, cell in enumerate(row)
                ]
                for row in rows
            ],
        }
        return render_pdf("ledger/recode_report.html", context, locale=locale)


def filename(batch: RecodeBatch, fmt: str) -> str:
    return f"recode-{str(batch.public_id)[:8]}.{fmt}"


def export(batch: RecodeBatch, fmt: str, locale: str = "en-ca") -> tuple[bytes, str, str]:
    if fmt not in FORMATS:
        raise ValueError(fmt)
    writer = {"csv": write_csv, "xlsx": write_xlsx, "pdf": write_pdf}[fmt]
    return writer(batch, locale), CONTENT_TYPES[fmt], filename(batch, fmt)
