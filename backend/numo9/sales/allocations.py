"""Allocating payments and customer credits to invoices (D-05-T02).

``open_balance(invoice)`` — what the customer still owes on a posted invoice: its total less
what payments and credits paid (``amount_paid``) and less the credit notes applied to it.

``auto_allocate(contact, amount)`` — the plan of "Auto-allocate": the customer's open invoices
**oldest due first** (due date, then invoice date, then the order they were posted), each taking
as much as it is owed until the amount runs out; ``[(invoice, amount)]``, what is left over is the
caller's (an overpayment, D-05-T04).

``allocate(source, plan, user, date)`` — apply a ``CustomerPayment`` or a ``CustomerCredit`` to
invoices, in one transaction: every invoice is locked and must be a posted invoice of the same
customer with an open balance of at least its amount (``sales.allocation.over_invoice``), and the
plan's total can't be more than the source has left (``sales.allocation.over_source``); each
allocation adds its amount to the invoice's ``amount_paid`` and refreshes its status (Partially
paid / Paid, D-05-T07). ``unallocate(allocation, user)``
removes one (kept, dated) and gives the amount back. Allocating moves nothing in the general
ledger: the payment already credited accounts receivable (D-05-T03); a credit is a credit
balance of the customer on the same control account.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError
from numo9.tenancy.context import org_context

from .invoice_status import refresh_status
from .models import (
    CreditApplication,
    CustomerCredit,
    CustomerPayment,
    Invoice,
    InvoiceStatus,
    PaymentAllocation,
    PaymentStatus,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
#: Posted invoices that can still be owed money.
OPEN_STATUSES = (InvoiceStatus.APPROVED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID)

Plan = list[tuple[Invoice, Decimal]]


class AllocationRefused(LedgerError):
    """An allocation the rules refuse (``code`` names the rule)."""


def _refuse(message: str, code: str, **params: Any) -> AllocationRefused:
    return AllocationRefused(message, code=code, params={k: str(v) for k, v in params.items()})


def _money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def credited(invoice: Invoice) -> Decimal:
    """The credit notes applied to the invoice (still applied)."""
    total = CreditApplication.objects.filter(invoice=invoice, reversed_at__isnull=True).aggregate(
        total=Sum("amount")
    )["total"]
    return _money(total)


def open_balance(invoice: Invoice) -> Decimal:
    if invoice.status not in OPEN_STATUSES:
        return ZERO
    return max(ZERO, _money(invoice.total) - _money(invoice.amount_paid) - credited(invoice))


def open_invoices(contact: Any) -> list[Invoice]:
    """The customer's invoices with money owed, oldest due first."""
    rows = Invoice.objects.filter(
        contact=contact, status__in=OPEN_STATUSES, deleted_at__isnull=True
    ).order_by("due_date", "date", "pk")
    return [invoice for invoice in rows if open_balance(invoice) > ZERO]


def auto_allocate(contact: Any, amount: Decimal) -> Plan:
    """Oldest due first (module docstring)."""
    left = _money(amount)
    plan: Plan = []
    for invoice in open_invoices(contact):
        if left <= ZERO:
            break
        take = min(left, open_balance(invoice))
        plan.append((invoice, take))
        left -= take
    return plan


def available(source: CustomerPayment | CustomerCredit) -> Decimal:
    """What the payment hasn't allocated / what the credit has left."""
    if isinstance(source, CustomerPayment):
        return _money(source.unallocated)
    return _money(source.remaining)


def allocate(
    source: CustomerPayment | CustomerCredit,
    plan: Iterable[tuple[Invoice, Decimal]],
    user: Any = None,
    *,
    date: dt.date | None = None,
) -> list[PaymentAllocation]:
    """Apply ``source`` to invoices (module docstring)."""
    person = user if getattr(user, "is_authenticated", False) else None
    wanted = [(invoice, _money(amount)) for invoice, amount in plan]
    with org_context(source.organisation), transaction.atomic():
        model = type(source)
        locked = model._base_manager.select_for_update().get(pk=source.pk)
        if isinstance(locked, CustomerPayment) and locked.status != PaymentStatus.POSTED:
            raise _refuse(_("A void payment can't be allocated."), "sales.allocation.void_source")
        if any(amount <= ZERO for _invoice, amount in wanted):
            raise _refuse(_("Each allocation is more than zero."), "sales.allocation.not_positive")
        total = sum((amount for _invoice, amount in wanted), ZERO)
        left = available(locked)
        if total > left:
            raise _refuse(
                _("That allocates %(total)s, but only %(left)s is left to allocate."),
                "sales.allocation.over_source",
                total=total,
                left=left,
            )
        made: list[PaymentAllocation] = []
        day = date or getattr(locked, "date", None) or timezone.localdate()
        for invoice, amount in wanted:
            row = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
            if row.contact_id != locked.contact_id:
                raise _refuse(
                    _("%(invoice)s is another customer's invoice."),
                    "sales.allocation.wrong_customer",
                    invoice=row.number or row,
                )
            owed = open_balance(row)
            if amount > owed:
                raise _refuse(
                    _("%(invoice)s has %(owed)s open: %(amount)s is more than it is owed."),
                    "sales.allocation.over_invoice",
                    invoice=row.number or row,
                    owed=owed,
                    amount=amount,
                )
            allocation = PaymentAllocation(
                organisation=row.organisation,
                invoice=row,
                amount=amount,
                date=day,
                created_by=person,
                **(
                    {"payment": locked}
                    if isinstance(locked, CustomerPayment)
                    else {"credit": locked}
                ),
            )
            allocation.save()
            row.amount_paid = _money(row.amount_paid) + amount
            row.save(update_fields=["amount_paid"])
            refresh_status(row)  # Partially paid / Paid (D-05-T07)
            made.append(allocation)
        return made


def unallocate(allocation: PaymentAllocation, user: Any = None) -> PaymentAllocation:
    """Remove an allocation: kept with the time it was removed; the invoice owes it again."""
    with org_context(allocation.organisation), transaction.atomic():
        row = PaymentAllocation._base_manager.select_for_update().get(pk=allocation.pk)
        if row.reversed_at is not None:
            return row
        invoice = Invoice._base_manager.select_for_update().get(pk=row.invoice_id)
        invoice.amount_paid = max(ZERO, _money(invoice.amount_paid) - _money(row.amount))
        invoice.save(update_fields=["amount_paid"])
        row.reversed_at = timezone.now()
        row.save(update_fields=["reversed_at"])
        refresh_status(invoice)  # back to Partially paid / Sent (D-05-T07)
        return row
