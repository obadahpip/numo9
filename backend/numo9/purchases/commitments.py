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
