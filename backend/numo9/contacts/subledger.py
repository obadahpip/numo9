"""Sub-ledger sources: what a contact owes or is owed, for statements and reconciliation
(B-02-T03).

Statements and supplier reconciliation don't read invoices or bills directly: they ask the
**sources** registered for a side — ``receivables`` (customers: invoices, credit notes, payments
received; D, Phase 1) and ``payables`` (suppliers: bills, supplier credits, payments made; E,
Phase 1). A source answers two questions about one contact, in the contact's currency:

- ``open_items(contact, as_at)`` — documents not fully paid at the end of ``as_at``, each with
  what is still owed (positive = owed to us for receivables, owed by us for payables);
- ``activity(contact, start, end)`` — every document and payment dated in the range (documents
  positive, payments and credits negative).

``FixtureSource`` implements the contract from plain documents and payments (tests, the demo,
and the shape Phase 1 sources must keep — ``tests/test_contacts_subledger.py`` is the contract
test they reuse).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

ZERO = Decimal("0.00")
Side = Literal["receivables", "payables"]


@dataclass(frozen=True)
class OpenItem:
    date: dt.date
    document: str  # "INV-1043"
    due_date: dt.date | None
    original: Decimal  # the document's total
    outstanding: Decimal  # what is still owed at the date asked
    description: str = ""
    ref: str = ""  # public id of the document


@dataclass(frozen=True)
class ActivityItem:
    date: dt.date
    document: str
    amount: Decimal  # documents positive; payments and credits negative
    description: str = ""
    due_date: dt.date | None = None
    ref: str = ""


class SubLedgerSource(Protocol):
    side: Side

    def open_items(self, contact: Any, as_at: dt.date) -> list[OpenItem]: ...

    def activity(self, contact: Any, start: dt.date, end: dt.date) -> list[ActivityItem]: ...


_sources: dict[Side, list[SubLedgerSource]] = defaultdict(list)


def register_source(source: SubLedgerSource) -> SubLedgerSource:
    if source not in _sources[source.side]:
        _sources[source.side].append(source)
    return source


def unregister_source(source: SubLedgerSource) -> None:
    if source in _sources[source.side]:
        _sources[source.side].remove(source)


def sources(side: Side) -> list[SubLedgerSource]:
    return list(_sources[side])


def open_items(side: Side, contact: Any, as_at: dt.date) -> list[OpenItem]:
    found = [item for s in sources(side) for item in s.open_items(contact, as_at)]
    return sorted(found, key=lambda i: (i.date, i.document))


def activity(side: Side, contact: Any, start: dt.date, end: dt.date) -> list[ActivityItem]:
    found = [item for s in sources(side) for item in s.activity(contact, start, end)]
    return sorted(found, key=lambda i: (i.date, i.amount < 0, i.document))


# ---- fixture implementation ---------------------------------------------------------------------


@dataclass
class FixtureDocument:
    contact_id: int
    number: str
    date: dt.date
    total: Decimal  # negative for a credit note
    due_date: dt.date | None = None
    description: str = ""
    payments: list[tuple[dt.date, Decimal, str]] = field(default_factory=list)  # date, amount, ref


@dataclass
class FixtureSource:
    """Documents and their payments in memory; answers the contract like a Phase 1 module."""

    side: Side = "receivables"
    documents: list[FixtureDocument] = field(default_factory=list)

    def add(self, document: FixtureDocument) -> FixtureDocument:
        self.documents.append(document)
        return document

    def _of(self, contact: Any) -> list[FixtureDocument]:
        return [d for d in self.documents if d.contact_id == contact.pk]

    def open_items(self, contact: Any, as_at: dt.date) -> list[OpenItem]:
        items = []
        for doc in self._of(contact):
            if doc.date > as_at:
                continue
            paid = sum((amount for day, amount, _ref in doc.payments if day <= as_at), ZERO)
            left = doc.total - paid
            if left != ZERO:
                items.append(
                    OpenItem(
                        doc.date,
                        doc.number,
                        doc.due_date,
                        doc.total,
                        left,
                        doc.description,
                        doc.number,
                    )
                )
        return items

    def activity(self, contact: Any, start: dt.date, end: dt.date) -> list[ActivityItem]:
        items = []
        for doc in self._of(contact):
            if start <= doc.date <= end:
                items.append(
                    ActivityItem(
                        doc.date, doc.number, doc.total, doc.description, doc.due_date, doc.number
                    )
                )
            for day, amount, ref in doc.payments:
                if start <= day <= end:
                    items.append(
                        ActivityItem(day, ref, -amount, f"Payment — {doc.number}", None, ref)
                    )
        return items
