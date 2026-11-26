"""Receiving payments, customer credits and refunds (D-05-T04, T06).

``receive_payment(contact, bank_account, date, amount, user, allocations=None, reference="")``
— in one transaction: record the ``CustomerPayment``, post it (Dr the bank account / Cr accounts
receivable for the customer — through the posting engine: the AR and general ledger lock dates
and closed periods apply), allocate it — the plan given, or **auto-allocate** oldest due first
when ``allocations`` is ``None`` — and keep what is left as a ``CustomerCredit``: an
**overpayment** when part of the payment paid invoices, a **prepayment** when none did (D-05-T04).
The credit is a credit balance of the customer on the AR control account.

``apply_credit(credit, invoice, amount, user, date=None)`` — use a credit on an invoice later
(the allocation rules of D-05-T02: ≤ the invoice's open balance and ≤ what the credit has left).

``refund_credit(credit, bank_account, date, amount, user, reference="")`` — pay a credit back to
the customer (D-06-T06 has the credit note's refund): posts Dr accounts receivable (the
customer's credit) / Cr the bank account and records the ``CustomerCreditRefund``; the amount
can't be more than the credit has left (``sales.credit.over_refund``).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.ledger.models import Account, JournalType, LedgerError, SystemRole
from numo9.ledger.renumber import acting_as
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .allocations import CENT, ZERO, Plan, allocate, auto_allocate
from .models import (
    CreditSource,
    CustomerCredit,
    CustomerCreditRefund,
    CustomerPayment,
    Invoice,
    PaymentAllocation,
)

PAYMENT_SOURCE = "sales.payment"
REFUND_SOURCE = "sales.credit_refund"


class ReceiptRefused(LedgerError):
    """A payment, credit or refund the rules refuse (``code`` names the rule)."""


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _ar() -> Account:
    found = Account.objects.filter(system_role=SystemRole.AR).first()
    if found is None:
        raise ReceiptRefused(
            _("The organisation has no accounts receivable account: add it to the chart."),
            code="sales.payment.no_ar",
        )
    return found


def receive_payment(
    contact: Any,
    bank_account: Any,
    date: dt.date,
    amount: Decimal,
    user: Any = None,
    *,
    allocations: Plan | None = None,
    reference: str = "",
) -> CustomerPayment:
    """Record, post, allocate and keep the rest as a credit (module docstring)."""
    person = _person(user)
    value = Decimal(amount).quantize(CENT)
    if value <= ZERO:
        raise ReceiptRefused(
            _("A payment received is more than zero."), code="sales.payment.not_positive"
        )
    organisation = contact.organisation
    with org_context(organisation), transaction.atomic(), acting_as(person):
        payment = CustomerPayment(
            organisation=organisation,
            contact=contact,
            bank_account=bank_account,
            date=date,
            amount=value,
            currency=getattr(bank_account, "currency", "CAD") or "CAD",
            reference=" ".join((reference or "").split()),
            created_by=person,
        )
        payment.save()
        entry = post_journal(
            JournalSpec(
                date=date,
                type=JournalType.PAYMENT,
                narration=_("Payment from %(contact)s") % {"contact": contact.display_name},
                source_type=PAYMENT_SOURCE,
                source_id=str(payment.public_id),
                lines=[
                    LineSpec(bank_account.gl_account, debit=value),
                    LineSpec(_ar(), credit=value, contact=contact),
                ],
            ),
            organisation=organisation,
            user=person,
            module=LockModule.AR,
        )
        payment.journal_entry = entry
        payment.save(update_fields=["journal_entry"])
        plan = auto_allocate(contact, value) if allocations is None else allocations
        made = allocate(payment, plan, person, date=date) if plan else []
        left = payment.unallocated
        if left > ZERO:
            CustomerCredit(
                organisation=organisation,
                contact=contact,
                source=CreditSource.OVERPAYMENT if made else CreditSource.PREPAYMENT,
                payment=payment,
                date=date,
                amount=left,
                currency=payment.currency,
            ).save()
        return payment


def apply_credit(
    credit: CustomerCredit,
    invoice: Invoice,
    amount: Decimal,
    user: Any = None,
    *,
    date: dt.date | None = None,
) -> PaymentAllocation:
    """Use a customer credit on an invoice (module docstring)."""
    (made,) = allocate(credit, [(invoice, Decimal(amount))], user, date=date)
    return made


def refund_credit(
    credit: CustomerCredit,
    bank_account: Any,
    date: dt.date,
    amount: Decimal,
    user: Any = None,
    *,
    reference: str = "",
) -> CustomerCreditRefund:
    """Pay a customer credit back to the customer (module docstring)."""
    person = _person(user)
    value = Decimal(amount).quantize(CENT)
    with org_context(credit.organisation), transaction.atomic(), acting_as(person):
        locked = CustomerCredit._base_manager.select_for_update().get(pk=credit.pk)
        left = locked.remaining
        if value <= ZERO or value > left:
            raise ReceiptRefused(
                _("Refund between 0.01 and %(left)s: what the credit has left.")
                % {"left": f"{left:.2f}"},
                code="sales.credit.over_refund",
                params={"left": f"{left:.2f}"},
            )
        refund = CustomerCreditRefund(
            organisation=locked.organisation,
            credit=locked,
            bank_account=bank_account,
            date=date,
            amount=value,
            reference=" ".join((reference or "").split()),
            created_by=person,
        )
        refund.save()
        entry = post_journal(
            JournalSpec(
                date=date,
                type=JournalType.PAYMENT,
                narration=_("Refund to %(contact)s") % {"contact": locked.contact.display_name},
                source_type=REFUND_SOURCE,
                source_id=str(refund.public_id),
                lines=[
                    LineSpec(_ar(), debit=value, contact=locked.contact),
                    LineSpec(bank_account.gl_account, credit=value),
                ],
            ),
            organisation=locked.organisation,
            user=person,
            module=LockModule.AR,
        )
        refund.journal_entry = entry
        refund.save(update_fields=["journal_entry"])
        locked.amount_refunded = Decimal(locked.amount_refunded) + value
        locked.save(update_fields=["amount_refunded"])
        return refund
