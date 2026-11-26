"""``InvoiceCurrent`` — the one query layer every receivables report reads (D-03b-T12, ADR-0006).

A posted invoice may have several revisions ("101", "101-1", "101-2"); reports must only ever
see the **current** one — its number, total and tax — and never add a superseded version. Rather
than each report filtering revisions its own way (and one day getting it wrong), they all go
through this module:

- ``current_invoices(organisation, contact=…, as_at=…, open_only=…)`` → ``[InvoiceCurrent]`` — the
  posted, not void invoices dated on or before ``as_at`` with the figures of their current
  revision (``number`` is the revision's "101-1"; ``total`` / ``tax_total`` are the revision's)
  and what is paid (payment and credit allocations) and credited (credit notes applied) **as at**
  ``as_at`` — allocations dated after it, or removed before it, don't count; ``balance`` is what
  the customer still owes. ``current_of(invoice)`` is one invoice's; ``current_number(invoice)``
  its number as shown.
- **AR aging** — ``ar_aging(organisation, as_at)``: per customer, the aging buckets of the open
  items (B-02 buckets: current, 1–30, 31–60, 61–90, over 90 days past due).
- **Statements** — ``InvoiceReceivables``, the ``receivables`` sub-ledger source (B-02-T03)
  registered at start-up: open items as at a date (the invoices' balances; unapplied customer
  credits and credit notes as negative items) and activity in a range (each invoice once, at its
  current revision; payments and credit notes negative; credit refunds positive). Statements
  and AR aging therefore agree to the cent (B-02-T13).
- **Reminders** — ``reminder_context`` (D-07) shows ``current_number`` and is given
  ``balance`` as the amount due: the current revision's, after partial payments.
- **Tax reports** — ``current_tax_lines(organisation, start, end, …)``: the posted tax lines with a
  superseded pair (a revision's original and its reversal, both in the range) left out
  (G-05-T02 ``posted_tax_lines(current_only=True)``); the detail labels a revised invoice with its
  current number. A period then shows the revised invoice once, at 1,017.00 — never 1,130.00
  and −1,130.00 beside it.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, OuterRef, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _

from numo9.contacts.subledger import ActivityItem, OpenItem, Side

from .models import (
    CreditApplication,
    CreditNote,
    CreditNoteStatus,
    CustomerCredit,
    CustomerCreditRefund,
    CustomerPayment,
    Invoice,
    InvoiceStatus,
    PaymentAllocation,
    PaymentStatus,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
#: Posted credit notes (a void one nets to zero).
NOTES_LIVE = (
    CreditNoteStatus.APPROVED,
    CreditNoteStatus.PARTIALLY_APPLIED,
    CreditNoteStatus.APPLIED,
)
#: Posted invoices a report shows (a void one nets to zero and is left out).
LIVE = (
    InvoiceStatus.APPROVED,
    InvoiceStatus.SENT,
    InvoiceStatus.PARTIALLY_PAID,
    InvoiceStatus.PAID,
)
MONEY = DecimalField(max_digits=18, decimal_places=2)


@dataclass(frozen=True)
class InvoiceCurrent:
    """One posted invoice as its current revision shows it (module docstring)."""

    invoice_id: int
    public_id: str
    contact_id: int
    number: str  # the current revision's "101-1" ("101" before any revision)
    base_number: str  # "101"
    revision: int
    date: dt.date
    due_date: dt.date | None
    currency: str
    status: str
    total: Decimal
    tax_total: Decimal
    paid: Decimal  # payments and customer credits allocated, as at
    credited: Decimal  # credit notes applied, as at

    @property
    def balance(self) -> Decimal:
        return max(ZERO, self.total - self.paid - self.credited)


def _live_on(as_at: dt.date | None) -> Q:
    """An allocation or application that counts at the end of ``as_at`` (all live ones if None)."""
    if as_at is None:
        return Q(reversed_at__isnull=True)
    return Q(date__lte=as_at) & (Q(reversed_at__isnull=True) | Q(reversed_at__date__gt=as_at))


def _summed(model: Any, as_at: dt.date | None) -> Coalesce:
    rows = (
        model._base_manager.filter(_live_on(as_at), invoice_id=OuterRef("pk"))
        .order_by()
        .values("invoice_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return Coalesce(Subquery(rows, output_field=MONEY), Value(ZERO, output_field=MONEY))


def _queryset(
    organisation: Any, contact: Any = None, as_at: dt.date | None = None
) -> QuerySet[Invoice]:
    rows = Invoice._base_manager.filter(
        organisation=organisation, status__in=LIVE, deleted_at__isnull=True
    )
    if contact is not None:
        rows = rows.filter(contact=contact)
    if as_at is not None:
        rows = rows.filter(date__lte=as_at)
    return (
        rows.select_related("current_revision")
        .annotate(paid_as_at=_summed(PaymentAllocation, as_at))
        .annotate(credited_as_at=_summed(CreditApplication, as_at))
        .order_by("due_date", "date", "pk")
    )


def _money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def _current(row: Invoice) -> InvoiceCurrent:
    revision = row.current_revision
    return InvoiceCurrent(
        invoice_id=row.pk,
        public_id=str(row.public_id),
        contact_id=row.contact_id,
        number=(revision.number_display if revision else "") or row.number,
        base_number=row.number,
        revision=revision.revision if revision else 0,
        date=row.date,
        due_date=row.due_date,
        currency=row.currency,
        status=row.status,
        total=_money(revision.total if revision else row.total),
        tax_total=_money(revision.tax_total if revision else row.tax_total),
        paid=_money(getattr(row, "paid_as_at", row.amount_paid)),
        credited=_money(getattr(row, "credited_as_at", ZERO)),
    )


def current_invoices(
    organisation: Any,
    *,
    contact: Any = None,
    as_at: dt.date | None = None,
    open_only: bool = False,
) -> list[InvoiceCurrent]:
    """The posted invoices at their current revision (module docstring), oldest due first."""
    found = [_current(row) for row in _queryset(organisation, contact, as_at)]
    return [item for item in found if item.balance > ZERO] if open_only else found


def current_of(invoice: Invoice, as_at: dt.date | None = None) -> InvoiceCurrent | None:
    """One invoice at its current revision, or None if it isn't posted (or is void)."""
    row = _queryset(invoice.organisation, as_at=as_at).filter(pk=invoice.pk).first()
    return _current(row) if row is not None else None


def current_number(invoice: Any) -> str:
    """The number the invoice is shown with: its current revision's ("101-1")."""
    revision = getattr(invoice, "current_revision", None)
    return str((revision.number_display if revision else "") or invoice.number or "")


def open_balance(invoice: Invoice, as_at: dt.date | None = None) -> Decimal:
    found = current_of(invoice, as_at)
    return found.balance if found is not None else ZERO


def current_tax_lines(organisation: Any, start: dt.date, end: dt.date, **filters: Any) -> Any:
    """The tax lines of the range at the documents' current revisions (module docstring)."""
    from numo9.tax.tax_lines import posted_tax_lines

    return posted_tax_lines(organisation, start, end, current_only=True, **filters)


# ---- the receivables sub-ledger source: statements and AR aging ---------------------------------


def _credit_left(credit: CustomerCredit, as_at: dt.date) -> Decimal:
    applied = PaymentAllocation._base_manager.filter(_live_on(as_at), credit=credit).aggregate(
        total=Sum("amount")
    )["total"]
    refunded = CustomerCreditRefund._base_manager.filter(credit=credit, date__lte=as_at).aggregate(
        total=Sum("amount")
    )["total"]
    return _money(credit.amount) - _money(applied) - _money(refunded)


def _note_left(note: CreditNote, as_at: dt.date) -> Decimal:
    applied = CreditApplication._base_manager.filter(_live_on(as_at), credit_note=note).aggregate(
        total=Sum("amount")
    )["total"]
    return _money(note.total) - _money(applied) - _money(note.amount_refunded)


def _notes(contact: Any) -> QuerySet[CreditNote]:
    return CreditNote._base_manager.filter(
        organisation_id=contact.organisation_id,
        contact=contact,
        status__in=NOTES_LIVE,
        deleted_at__isnull=True,
    )


class InvoiceReceivables:
    """The ``receivables`` sub-ledger source of sales (module docstring)."""

    side: Side = "receivables"

    def open_items(self, contact: Any, as_at: dt.date) -> list[OpenItem]:
        items = [
            OpenItem(
                date=item.date,
                document=item.number,
                due_date=item.due_date,
                original=item.total,
                outstanding=item.balance,
                ref=item.public_id,
            )
            for item in current_invoices(
                contact.organisation, contact=contact, as_at=as_at, open_only=True
            )
        ]
        for credit in CustomerCredit._base_manager.filter(
            organisation_id=contact.organisation_id, contact=contact, date__lte=as_at
        ):
            left = _credit_left(credit, as_at)
            if left > ZERO:
                items.append(
                    OpenItem(
                        date=credit.date,
                        document=str(credit.get_source_display()),
                        due_date=None,
                        original=-_money(credit.amount),
                        outstanding=-left,
                        ref=str(credit.public_id),
                    )
                )
        for note in _notes(contact).filter(date__lte=as_at):
            left = _note_left(note, as_at)
            if left > ZERO:
                items.append(
                    OpenItem(
                        date=note.date,
                        document=note.number,
                        due_date=None,
                        original=-_money(note.total),
                        outstanding=-left,
                        ref=str(note.public_id),
                    )
                )
        return items

    def activity(self, contact: Any, start: dt.date, end: dt.date) -> list[ActivityItem]:
        org = contact.organisation
        moves = [
            ActivityItem(item.date, item.number, item.total, due_date=item.due_date)
            for item in current_invoices(org, contact=contact, as_at=end)
            if item.date >= start
        ]
        for payment in CustomerPayment._base_manager.filter(
            organisation=org,
            contact=contact,
            status=PaymentStatus.POSTED,
            date__gte=start,
            date__lte=end,
        ):
            label = payment.reference or str(_("Payment received"))
            moves.append(ActivityItem(payment.date, label, -_money(payment.amount)))
        for refund in CustomerCreditRefund._base_manager.filter(
            organisation=org, credit__contact=contact, date__gte=start, date__lte=end
        ):
            label = refund.reference or str(_("Credit refund"))
            moves.append(ActivityItem(refund.date, label, _money(refund.amount)))
        for note in _notes(contact).filter(date__gte=start, date__lte=end):
            moves.append(ActivityItem(note.date, note.number, -_money(note.total)))
            if note.amount_refunded:  # D-06-T05 dates refunds; until then, at the note's date
                moves.append(ActivityItem(note.date, note.number, _money(note.amount_refunded)))
        return moves


RECEIVABLES = InvoiceReceivables()


def register_receivables() -> None:
    from numo9.contacts.subledger import register_source

    register_source(RECEIVABLES)


def ar_aging(organisation: Any, as_at: dt.date) -> dict[int, dict[str, Decimal]]:
    """Per customer (contact id): the aging buckets of the open items as at ``as_at``."""
    from numo9.contacts.models import Contact
    from numo9.contacts.statements import StatementLine, aging_of

    out: dict[int, dict[str, Decimal]] = {}
    contacts: set[int] = set()
    contacts.update(
        Invoice._base_manager.filter(organisation=organisation, status__in=LIVE).values_list(
            "contact_id", flat=True
        )
    )
    contacts.update(
        CustomerCredit._base_manager.filter(organisation=organisation).values_list(
            "contact_id", flat=True
        )
    )
    contacts.update(
        CreditNote._base_manager.filter(
            organisation=organisation, status__in=NOTES_LIVE
        ).values_list("contact_id", flat=True)
    )
    grouped: dict[int, list[StatementLine]] = defaultdict(list)
    for contact in Contact._base_manager.filter(pk__in=contacts):
        for item in RECEIVABLES.open_items(contact, as_at):
            grouped[contact.pk].append(
                StatementLine(item.date, item.document, "", item.due_date, item.outstanding)
            )
    for contact_id, lines in grouped.items():
        out[contact_id] = aging_of(lines, as_at)
    return out
