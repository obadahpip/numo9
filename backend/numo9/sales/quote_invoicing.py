"""Quotes into invoices (D-02-T08, T09).

- ``create_deposit_invoice(quote)`` — on acceptance (the lifecycle's ``accept``, D-02-T04), a quote
  that asks for a deposit (an amount, or a % of the **accepted** total — the options the customer
  chose) gets a **draft** deposit invoice (D-03a), linked as ``quote.deposit_invoice``: one line
  "Deposit for quote QU-0001 (30 %)" on the organisation's *Customer deposits* liability account,
  no tax code, due on the day of acceptance. It is a draft so that the organisation's approval
  rule, lock dates and numbering apply when someone approves and sends it — a customer clicking
  Accept never posts to the ledger. The tax of the work is charged in full on the final invoice
  (below), where the deposit is deducted. A deposit larger than the total is capped at the total.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.tenancy.context import org_context

from .models import Invoice, InvoiceLine, Quote

ZERO = Decimal("0.00")


def deposit_account() -> Any:
    """The organisation's *Customer deposits* account (template row 2300): an active current
    liability a sales line may use; by code 2300 first, then by a name with "deposit" in it.
    None when the chart has none (the draft's line then waits for an account)."""
    from numo9.ledger.contexts import allowed_in_context
    from numo9.ledger.models import Account

    candidates = [
        account
        for account in Account.objects.active().filter(subtype="current_liability").order_by("code")
        if allowed_in_context(account, "sales")
    ]
    for account in candidates:
        if account.code == "2300":
            return account
    for account in candidates:
        names = " ".join(str(v) for v in (account.name_i18n or {}).values()).lower()
        if "deposit" in names or "dépôt" in names or "acompte" in names:
            return account
    return None


def deposit_due(quote: Quote) -> Decimal:
    """The deposit the quote asks on acceptance, to the cent, never more than its total."""
    from .pdf import deposit_amount

    amount: Decimal = deposit_amount(quote)
    return max(ZERO, min(amount, Decimal(quote.total)))


def create_deposit_invoice(
    quote: Quote, *, user: Any = None, now: dt.datetime | None = None
) -> Invoice | None:
    """The draft deposit invoice of an accepted quote, linked to it (module docstring); None
    when the quote asks no deposit. Idempotent: a quote that already has one keeps it."""
    from numo9.audit import service as audit

    from .posting import recalculate
    from .quotes import local_today

    if quote.deposit_invoice_id is not None:
        return quote.deposit_invoice
    amount = deposit_due(quote)
    if amount <= ZERO:
        return None
    person = user if getattr(user, "is_authenticated", False) else None
    organisation = quote.organisation
    with org_context(organisation), transaction.atomic():
        day = max(local_today(organisation, now), quote.date)
        invoice = Invoice(
            organisation=organisation,
            contact=quote.contact,
            date=day,
            due_date=day,
            reference=quote.number,
            currency=quote.currency,
            tax_mode=quote.tax_mode,
            ship_to_country=quote.ship_to_country,
            ship_to_province=quote.ship_to_province,
            created_by=person,
        )
        invoice.save()
        if quote.deposit_type == "percent":
            description = _("Deposit for quote %(number)s (%(percent)s %%)") % {
                "number": quote.number,
                "percent": f"{Decimal(quote.deposit_value).normalize():f}",
            }
        else:
            description = _("Deposit for quote %(number)s") % {"number": quote.number}
        InvoiceLine(
            organisation=organisation,
            document=invoice,
            position=0,
            description=description,
            quantity=Decimal("1"),
            unit_price=amount,
            account=deposit_account(),
            tax_code=None,
        ).save()
        invoice = recalculate(invoice)
        Quote._base_manager.filter(pk=quote.pk).update(deposit_invoice=invoice)
        quote.deposit_invoice = invoice
        audit.record(
            "sales.quote.deposit_invoiced",
            obj=quote,
            meta={"number": quote.number, "deposit": f"{amount:.2f}"},
            actor=person,
        )
        return invoice
