"""Recurring invoices (D-04) — the schedule (T02), placeholders (T03) and proration (T04).

**Schedule** — the recurring-journal engine (C-04-T05) reused as is: an RFC 5545 rule from the
template's start date, monthly and yearly rules on the 29th–31st clamped to the month's last day
(31 January → 28 February → 31 March; 29 February in a leap year), up to the end date.

- ``occurrences(template, …)`` — the dates; ``first_run(template)`` — the first;
- ``period_of(template, day)`` — the period an occurrence bills: from its date to the day before
  the schedule's next date (31 January → 27 February);
- ``due_for(template, day)`` — the due date of the invoice of that occurrence: the template's terms,
  else the contact's default sales terms, else the organisation's (D-01-T07).

**Generation** (T05) — ``RecurringInvoiceGenerator`` on the shared ``RecurringGenerator``
(``numo9.documents.recurring``, reused by recurring bills): one invoice per occurrence, the
``RecurringInvoiceRun`` row unique per (template, date) being the idempotency row;
``build_invoice(template, day)`` is the draft, the mode (draft / approve / approve and send) is
applied by ``finish``. The hourly job ``numo9.sales.recurring_invoices`` (``tasks.py``) runs each
organisation on its own date.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from numo9.documents import due_dates
from numo9.documents.recurring import REFUSALS, Outcome, RecurringGenerator, reason
from numo9.ledger import recurring as engine
from numo9.orgsettings.models import LockModule

from .models import RecurringInvoiceMode, RecurringInvoiceRun, RecurringInvoiceTemplate


def validate_schedule(template: Any) -> None:
    """``ValidationError`` for a rule the engine can't read or an end before the start."""
    engine.parse_rule(template.rrule, template.start_date)
    if template.end_date is not None and template.end_date < template.start_date:
        raise ValidationError(
            {
                "end_date": ValidationError(
                    _("The end date is before the start date."),
                    code="sales.recurring.end_before_start",
                )
            }
        )


def occurrences(
    template: Any,
    *,
    after: dt.date | None = None,
    until: dt.date | None = None,
    limit: int | None = None,
) -> list[dt.date]:
    return engine.occurrences(
        template.rrule,
        template.start_date,
        template.end_date,
        after=after,
        until=until,
        limit=limit,
    )


def first_run(template: Any) -> dt.date | None:
    dates = occurrences(template, limit=1)
    return dates[0] if dates else None


def next_after(template: Any, day: dt.date) -> dt.date | None:
    """The schedule's next date after ``day`` — within the end date."""
    dates = occurrences(template, after=day, limit=1)
    return dates[0] if dates else None


def _open_rule(rule: str) -> str:
    """The rule without its own COUNT / UNTIL — the cadence only."""
    text = rule.strip()
    if text.upper().startswith("RRULE:"):
        text = text[6:]
    return ";".join(p for p in text.split(";") if not p.upper().startswith(("COUNT=", "UNTIL=")))


def period_of(template: Any, day: dt.date) -> tuple[dt.date, dt.date]:
    """The period the occurrence on ``day`` bills: to the day before the cadence's next date
    (neither the end date nor the rule's own COUNT / UNTIL cut it — proration does, T04)."""
    following = engine.occurrences(
        _open_rule(template.rrule), template.start_date, after=day, limit=1
    )
    return day, following[0] - dt.timedelta(days=1)


def terms_for(template: Any) -> Any:
    term = getattr(template, "terms", None)
    if term is not None:
        return due_dates.Terms(
            term.terms_type, term.days, term, term.discount_pct, term.discount_days
        )
    return due_dates.document_terms(due_dates.SALES, template.contact, template.organisation)


def due_for(template: Any, day: dt.date) -> dt.date:
    terms = terms_for(template)
    return due_dates.due_date(day, terms.terms_type, terms.days)


# ---- generation (D-04-T05) ---------------------------------------------------------------------

JOB = "numo9.sales.recurring_invoices"


def locale_of(template: Any) -> str:
    """The language placeholders are written in: the customer's documents language."""
    return str(getattr(template.contact, "language", "") or "en-ca").lower()


def _prorated_discount(share: Any, discount_type: str, value: Any) -> Any:
    """An amount discount shrinks with the period it applies to; a percentage stays."""
    from numo9.documents.models import DiscountType

    if discount_type != DiscountType.AMOUNT or share.full:
        return value
    return share.amount(Decimal("1"), Decimal(value))


def build_invoice(template: Any, day: dt.date) -> Any:
    """The draft invoice of the occurrence on ``day``: the template's header and lines as they
    are now (template changes apply to future occurrences only), dated ``day``, due by the
    template's rule (T02); placeholders resolved for the period the occurrence bills in the
    customer's language (T03); a first or last partial period prorated per line (T04). The
    figures are the server's (``recalculate``); the number comes at approval."""
    from .models import Invoice, InvoiceLine
    from .placeholders import render
    from .posting import recalculate
    from .proration import for_template

    start, end = period_of(template, day)
    share = for_template(template, start, end)
    locale = locale_of(template)

    def text(value: str) -> str:
        return render(value, start, end, locale)

    invoice = Invoice(
        organisation=template.organisation,
        contact=template.contact,
        date=day,
        due_date=due_for(template, day),
        terms=template.terms,
        reference=text(template.reference)[:255],
        currency=template.currency,
        tax_mode=template.tax_mode,
        ship_to_country=template.ship_to_country,
        ship_to_province=template.ship_to_province,
        discount_type=template.discount_type,
        discount_value=_prorated_discount(share, template.discount_type, template.discount_value),
        notes=text(template.notes),
        created_by=template.created_by,
    )
    invoice.save()
    for position, line in enumerate(template.lines.order_by("position", "pk")):
        quantity, price = share.line(Decimal(line.quantity), Decimal(line.unit_price))
        InvoiceLine(
            organisation=template.organisation,
            document=invoice,
            position=position,
            item=line.item,
            description=text(line.description),
            quantity=quantity,
            unit_price=price,
            discount_type=line.discount_type,
            discount_value=_prorated_discount(share, line.discount_type, line.discount_value),
            account=line.account,
            tax_code=line.tax_code,
            tax_overridden=line.tax_overridden,
            tracking=dict(line.tracking or {}),
        ).save()
    return recalculate(invoice)


class RecurringInvoiceGenerator(RecurringGenerator):
    """Recurring invoices on the shared generator (``numo9.documents.recurring``).

    Modes: **draft** — the invoice waits in Drafts; **approve** — approved and posted (numbered)
    as the template's author would from the editor (``submit_or_approve``: above the
    organisation's threshold or the author's limit it goes to Awaiting approval instead —
    ``sales.recurring.awaiting_approval``); **approve and send** — then emailed to the customer's
    people "included in emails" with the PDF (D-03a-T12). A refused approval keeps the draft, a
    refused send keeps the approved invoice; either is recorded on the run and the owner told."""

    template_model = RecurringInvoiceTemplate
    run_model = RecurringInvoiceRun
    job = JOB
    lock_module = LockModule.AR
    event_prefix = "sales.recurring_invoice"

    def build(self, template: Any, day: dt.date) -> Any:
        return build_invoice(template, day)

    def finish(self, template: Any, document: Any) -> Outcome:
        from .approvals import submit_or_approve
        from .email import send_invoice
        from .models import InvoiceStatus

        if template.mode == RecurringInvoiceMode.DRAFT:
            return Outcome(document)
        actor = template.created_by
        try:
            with transaction.atomic():
                invoice = submit_or_approve(document, actor)
        except REFUSALS as error:
            code, message = reason(error)
            return Outcome(document, code, message, notify=True)
        if invoice.status == InvoiceStatus.AWAITING_APPROVAL:
            return Outcome(
                invoice,
                "sales.recurring.awaiting_approval",
                _("The invoice needs approval before it is posted."),
            )
        if template.mode == RecurringInvoiceMode.APPROVE_SEND:
            try:
                with transaction.atomic():
                    send_invoice(invoice, actor)
            except REFUSALS as error:
                code, message = reason(error)
                return Outcome(invoice, code, message, notify=True)
        return Outcome(invoice)

    def link(self, template: Any) -> str:
        return f"/o/{template.organisation.public_id}/sales/recurring-invoices/{template.public_id}"


GENERATOR = RecurringInvoiceGenerator()


def generate_due(organisation: Any, today: dt.date) -> list[Any]:
    return GENERATOR.generate_due(organisation, today)


def generate_all(now: dt.datetime | None = None) -> dict[str, int]:
    return GENERATOR.generate_all(now)
