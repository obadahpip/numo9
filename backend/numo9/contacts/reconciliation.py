"""Supplier statement reconciliation (B-02-T08, gap-23 — Xero has none).

``reconcile(statement)`` compares a supplier's statement (``SupplierStatementLine`` rows, B-02-T07)
with **our** documents for that supplier from the payables sources (bills, supplier credits,
payments — B-02-T03) dated from the statement's first line to its date:

1. lines matched **by hand** (``manual_ref``) first;
2. then by **document number**, ignoring case, spaces and dashes (``INV-0042`` = ``inv 0042``);
3. then by **amount and date within 3 days**, for what is left.

The report lists the pairs (with any amount difference on a number match), their lines we don't
have, our documents they don't list, and the totals: their balance, ours, and the difference
explained by the unmatched items.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from . import subledger
from .subledger import ActivityItem

ZERO = Decimal("0.00")
DATE_TOLERANCE = dt.timedelta(days=3)


def number_key(text: str) -> str:
    return re.sub(r"[\s\-_/#.]", "", text or "").casefold()


@dataclass
class Pair:
    line_id: int
    ours: ActivityItem
    how: str  # "manual" | "number" | "amount_date"
    difference: Decimal  # theirs − ours


@dataclass
class Report:
    pairs: list[Pair] = field(default_factory=list)
    unmatched_theirs: list[Any] = field(default_factory=list)  # SupplierStatementLine rows
    unmatched_ours: list[ActivityItem] = field(default_factory=list)
    their_total: Decimal = ZERO
    our_total: Decimal = ZERO

    @property
    def difference(self) -> Decimal:
        return self.their_total - self.our_total


def reconcile(statement: Any) -> Report:
    from .models import SupplierStatementLine

    lines = list(SupplierStatementLine.objects.filter(statement=statement).order_by("position"))
    report = Report(their_total=sum((line.amount for line in lines), ZERO))
    if not lines:
        return report
    start = min(line.date for line in lines)
    ours = subledger.activity("payables", statement.contact, start, statement.statement_date)
    report.our_total = sum((item.amount for item in ours), ZERO)
    left = list(ours)

    def take(item: ActivityItem) -> ActivityItem:
        left.remove(item)
        return item

    pending = []
    for line in lines:
        hit = next((o for o in left if line.manual_ref and o.ref == line.manual_ref), None)
        if hit is not None:
            report.pairs.append(Pair(line.pk, take(hit), "manual", line.amount - hit.amount))
        else:
            pending.append(line)
    unmatched = []
    for line in pending:
        key = number_key(line.invoice_number or line.reference)
        hit = next((o for o in left if key and number_key(o.document) == key), None)
        if hit is not None:
            report.pairs.append(Pair(line.pk, take(hit), "number", line.amount - hit.amount))
        else:
            unmatched.append(line)
    for line in unmatched:
        hit = next(
            (
                o
                for o in left
                if o.amount == line.amount and abs(o.date - line.date) <= DATE_TOLERANCE
            ),
            None,
        )
        if hit is not None:
            report.pairs.append(Pair(line.pk, take(hit), "amount_date", ZERO))
        else:
            report.unmatched_theirs.append(line)
    report.unmatched_ours = left
    return report
