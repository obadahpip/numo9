"""Late-fee / interest lines on overdue invoices (D-07-T06; FN-04 adds accrual in Phase 2).

``late_fees(organisation, as_at, contact=…)`` → ``[FeeLine]`` — what the organisation's
``LateFeePolicy`` charges, as at a date, on each open invoice (its **current revision's**
balance, ``sales.current``):

- nothing while the policy is off, before ``grace_days`` after the due date have passed, on an
  invoice without a due date, on a disputed invoice (D-07-T07), or on a fee invoice (no
  interest on interest);
- the rate is the invoice's payment term's ``late_interest_pct`` (% a year), else the policy's
  ``rate_pct``; a zero rate charges nothing;
- interest runs from the due date — or from the end of the invoice's last charge, so the same
  days are never charged twice — to ``as_at``: ``balance × rate / 100 × days / 365``, rounded
  half up to the cent; a fee below ``min_fee`` is raised to it.

Where it goes (``LateFeePolicy.target``), each charge recorded as a ``LateFeeCharge``:

- ``charge_statement(document, contact, user)`` — appended to an outstanding or activity
  statement (B-02 engine output) as lines "Late interest on INV-0042: 31 days at 24 % a year",
  running balance and amount due updated, the fees in the *current* aging bucket;
- ``charge_fee_invoice(contact, as_at, user)`` — a **draft** invoice to the customer, one line
  per fee on the policy's fee income account, no sales tax (interest on an overdue account is not
  consideration for a supply); it is approved and sent like any invoice.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError
from numo9.tenancy.context import org_context

from .current import InvoiceCurrent, current_invoices
from .models import Invoice, InvoiceLine, LateFeeCharge, LateFeePolicy, LateFeeTarget

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
DAYS_IN_YEAR = Decimal("365")


class LateFeeRefused(LedgerError):
    """A late-fee charge the policy can't make (``code`` names why)."""


@dataclass(frozen=True)
class FeeLine:
    invoice: InvoiceCurrent
    start: dt.date
    end: dt.date
    days: int
    balance: Decimal
    rate_pct: Decimal
    amount: Decimal

    @property
    def description(self) -> str:
        return _(
            "Late interest on %(invoice)s: %(days)d days at %(rate)s %% a year on %(balance)s"
        ) % {
            "invoice": self.invoice.number,
            "days": self.days,
            "rate": f"{self.rate_pct.normalize():f}",
            "balance": f"{self.balance:.2f}",
        }


def policy_of(organisation: Any) -> LateFeePolicy | None:
    with org_context(organisation):
        found: LateFeePolicy | None = LateFeePolicy.objects.filter(
            organisation=organisation
        ).first()
        return found


def fee_for(balance: Decimal, rate_pct: Decimal, days: int, min_fee: Decimal) -> Decimal:
    """Simple interest to the cent, raised to the minimum fee (module docstring)."""
    if balance <= ZERO or rate_pct <= ZERO or days <= 0:
        return ZERO
    amount = (balance * rate_pct / Decimal(100) * Decimal(days) / DAYS_IN_YEAR).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    return max(amount, Decimal(min_fee).quantize(CENT))


def late_fees(
    organisation: Any,
    as_at: dt.date,
    *,
    contact: Any = None,
    policy: LateFeePolicy | None = None,
) -> list[FeeLine]:
    """The fees due as at ``as_at`` (module docstring)."""
    policy = policy or policy_of(organisation)
    if policy is None or not policy.is_active:
        return []
    with org_context(organisation):
        open_items = current_invoices(organisation, contact=contact, as_at=as_at, open_only=True)
        rows = {
            row.pk: row
            for row in Invoice._base_manager.filter(
                pk__in=[item.invoice_id for item in open_items]
            ).select_related("terms")
        }
        fee_invoices = set(
            LateFeeCharge.objects.filter(fee_invoice_id__in=rows).values_list(
                "fee_invoice_id", flat=True
            )
        )
        charged: dict[int, dt.date] = {}
        for invoice_id, end in LateFeeCharge.objects.filter(invoice_id__in=rows).values_list(
            "invoice_id", "end"
        ):
            charged[invoice_id] = max(end, charged.get(invoice_id, end))
    lines: list[FeeLine] = []
    for item in open_items:
        row = rows[item.invoice_id]
        if item.due_date is None or getattr(row, "disputed", False):
            continue
        if item.invoice_id in fee_invoices:  # no interest on interest
            continue
        if (as_at - item.due_date).days <= policy.grace_days:
            continue
        start = max(item.due_date, charged.get(item.invoice_id, item.due_date))
        days = (as_at - start).days
        term_rate = Decimal(getattr(row.terms, "late_interest_pct", 0) or 0)
        rate = term_rate if term_rate > ZERO else Decimal(policy.rate_pct)
        amount = fee_for(item.balance, rate, days, policy.min_fee)
        if amount > ZERO:
            lines.append(FeeLine(item, start, as_at, days, item.balance, rate, amount))
    return lines


def _record(
    organisation: Any,
    lines: list[FeeLine],
    target: str,
    user: Any,
    fee_invoice: Invoice | None = None,
) -> None:
    person = user if getattr(user, "is_authenticated", False) else None
    for line in lines:
        LateFeeCharge(
            organisation=organisation,
            invoice_id=line.invoice.invoice_id,
            start=line.start,
            end=line.end,
            days=line.days,
            balance=line.balance,
            rate_pct=line.rate_pct,
            amount=line.amount,
            target=target,
            fee_invoice=fee_invoice,
            created_by=person,
        ).save()


def charge_statement(document: Any, contact: Any, user: Any = None) -> Any:
    """The statement with the contact's fees as at its date appended (module docstring)."""
    from numo9.contacts.statements import StatementLine

    with org_context(contact.organisation), transaction.atomic():
        fees = late_fees(contact.organisation, document.as_at, contact=contact)
        if not fees:
            return document
        _record(contact.organisation, fees, LateFeeTarget.STATEMENT, user)
    balance = document.amount_due
    lines = list(document.lines)
    for fee in fees:
        balance += fee.amount
        lines.append(
            StatementLine(
                document.as_at, fee.invoice.number, fee.description, None, fee.amount, balance
            )
        )
    aging = dict(document.aging)
    if aging:
        aging["current"] = aging.get("current", ZERO) + sum((f.amount for f in fees), ZERO)
    return dataclasses.replace(document, lines=lines, aging=aging)


def charge_fee_invoice(contact: Any, as_at: dt.date, user: Any = None) -> Invoice | None:
    """A draft fee invoice for the contact's fees as at ``as_at``, or None when nothing is due
    (module docstring)."""
    from .posting import recalculate

    organisation = contact.organisation
    policy = policy_of(organisation)
    with org_context(organisation), transaction.atomic():
        fees = late_fees(organisation, as_at, contact=contact, policy=policy)
        if not fees:
            return None
        if policy is None or policy.fee_account_id is None:
            raise LateFeeRefused(
                _("Choose the income account late fees are invoiced to in the late fee settings."),
                code="sales.late_fee.no_account",
            )
        invoice = Invoice(
            organisation=organisation,
            contact=contact,
            date=as_at,
            due_date=as_at,
            currency=fees[0].invoice.currency,
            reference=str(_("Late interest")),
        )
        invoice.save()
        for position, fee in enumerate(fees):
            InvoiceLine(
                organisation=organisation,
                document=invoice,
                position=position,
                description=fee.description,
                quantity=Decimal("1"),
                unit_price=fee.amount,
                account_id=policy.fee_account_id,
                tax_code=None,
            ).save()
        invoice = recalculate(invoice)
        _record(organisation, fees, LateFeeTarget.FEE_INVOICE, user, fee_invoice=invoice)
        return invoice
