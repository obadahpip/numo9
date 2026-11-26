"""Commitment report query (E-01-T08): what the organisation has ordered and not yet been billed.

The **open value** of a PO line is its amount before tax, after discounts (``net``), for the part
not billed yet: ``net × (ordered − billed) / ordered`` (never below zero). Open POs are the
approved, partially received and received ones — billed, closed and cancelled POs commit nothing,
nor do drafts or POs waiting for approval.

``commitments(organisation, by="account" | "supplier" | "month", date_from=…, date_to=…)``
→ ``Commitments(by, rows, total)``: one row per account (code and name), supplier, or month of the
PO date (``2026-06``), largest first (months in order), with the open value, the number of open
lines and POs, and ``budget`` — empty until budgets (K-04). ``total`` is the sum of every open
line, whatever the grouping: the report total equals the open PO lines.

``export_commitments(result, "csv" | "xlsx")`` — the same rows and total as a download (E-01-T14).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from numo9.tenancy.context import org_context

from .models import OPEN_STATUSES, PurchaseOrderLine

CENT = Decimal("0.01")
GROUPINGS = ("account", "supplier", "month")


@dataclass
class CommitmentRow:
    key: str
    label: str
    amount: Decimal = Decimal("0")
    lines: int = 0
    orders: set[int] = field(default_factory=set)
    budget: Decimal | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "amount": f"{self.amount:.2f}",
            "lines": self.lines,
            "orders": len(self.orders),
            "budget": None if self.budget is None else f"{self.budget:.2f}",
        }


@dataclass(frozen=True)
class Commitments:
    by: str
    rows: list[CommitmentRow]
    total: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "by": self.by,
            "rows": [row.as_dict() for row in self.rows],
            "total": f"{self.total:.2f}",
        }


def open_value(line: PurchaseOrderLine) -> Decimal:
    ordered = Decimal(line.quantity)
    if ordered <= 0:
        return Decimal("0")
    unbilled = max(ordered - Decimal(line.quantity_billed), Decimal("0"))
    return (Decimal(line.net) * unbilled / ordered).quantize(CENT, ROUND_HALF_UP)


def _key(line: PurchaseOrderLine, by: str) -> tuple[str, str]:
    if by == "account":
        account = line.account
        if account is None:
            return "", ""
        return str(account.public_id), f"{account.code} · {account.name}"
    if by == "supplier":
        contact = line.document.contact
        return str(contact.public_id), contact.display_name
    month = line.document.date.strftime("%Y-%m")
    return month, month


def commitments(
    organisation: Any,
    *,
    by: str = "account",
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> Commitments:
    if by not in GROUPINGS:
        raise ValueError(f"group by one of {GROUPINGS}")
    with org_context(organisation):
        lines = PurchaseOrderLine.objects.select_related(
            "account", "document", "document__contact"
        ).filter(
            document__status__in=sorted(OPEN_STATUSES),
            document__deleted_at__isnull=True,
        )
        if date_from is not None:
            lines = lines.filter(document__date__gte=date_from)
        if date_to is not None:
            lines = lines.filter(document__date__lte=date_to)
        rows: dict[str, CommitmentRow] = {}
        total = Decimal("0")
        for line in lines.order_by("document__date", "document_id", "position", "pk"):
            value = open_value(line)
            if value == 0:
                continue
            key, label = _key(line, by)
            row = rows.setdefault(key, CommitmentRow(key, label))
            row.amount += value
            row.lines += 1
            row.orders.add(line.document_id)
            total += value
    ordered = (
        sorted(rows.values(), key=lambda r: r.key)
        if by == "month"
        else sorted(rows.values(), key=lambda r: (-r.amount, r.label))
    )
    return Commitments(by, ordered, total)


def _headers(by: str) -> list[str]:
    from django.utils.translation import gettext as _

    first = {"account": _("Account"), "supplier": _("Supplier"), "month": _("Month")}[by]
    return [first, _("Open POs"), _("Open lines"), _("Open value"), _("Budget")]


def export_commitments(
    result: Commitments, fmt: str, *, locale: str | None = None
) -> tuple[bytes, str, str]:
    """``(content, content type, file name)``: the report as CSV or XLSX — the rows and the total
    the screen shows, in the same order (E-01-T14 "export = screen")."""
    import csv
    import io

    from django.utils import translation
    from django.utils.translation import gettext as _

    with translation.override(locale or translation.get_language()):
        headers = _headers(result.by)
        total_label = _("Total")
        name = f"{_('commitments')}-{result.by}-{dt.date.today().isoformat()}"
    rows = [[row.label, len(row.orders), row.lines, row.amount, row.budget] for row in result.rows]
    total: list[Any] = [total_label, "", "", result.total, ""]
    table: list[list[Any]] = [*rows, total]
    if fmt == "xlsx":
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.title = name[:31]
        sheet.append(headers)
        for cells in table:
            sheet.append(
                [float(c) if isinstance(c, Decimal) else ("" if c is None else c) for c in cells]
            )
        out = io.BytesIO()
        book.save(out)
        return (
            out.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{name}.xlsx",
        )
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(headers)
    for cells in table:
        writer.writerow(
            [f"{c:.2f}" if isinstance(c, Decimal) else ("" if c is None else c) for c in cells]
        )
    return ("\ufeff" + text.getvalue()).encode(), "text/csv; charset=utf-8", f"{name}.csv"
