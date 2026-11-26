"""Recurring bills (E-03-T02, T03) — the purchase side of recurring invoices, on the same shared
generator (``numo9.documents.recurring.RecurringGenerator``, D-04-T05).

**Generation** (T02) — ``RecurringBillGenerator``: one bill per occurrence, the
``RecurringBillRun`` row unique per (template, date) being the idempotency row (two workers, a
restart, a replay create one bill); the shared skip rules (paused, archived supplier, a date in
a locked AP or closed period) with the owner notified. ``build_bill(template, day)`` is the
draft: the template's header and lines as they are now, dated ``day``, due by the template's
terms (else the supplier's default purchase terms, else the organisation's); the reference, the
notes and the line descriptions with the placeholders resolved for the period the occurrence
covers, in the organisation's language. Modes:

- **draft** — the bill waits in Drafts;
- **approve** — approved and posted (``bill_posting.approve``) as the template's author would;
  when a routing rule or the author's approval limit stops it, it goes to Awaiting approval
  instead (``purchases.recurring.awaiting_approval``); any other refusal keeps the draft, recorded
  on the run, and the owner is told.

The hourly job ``numo9.purchases.recurring_bills`` (``tasks.py``) runs each organisation on its
own date.

**Supplier invoice number** (T03) — ``supplier_invoice_number(template, start, end, exclude)``:
the template's pattern with the placeholders resolved (``RENT-{{month}}-{{year}}`` →
``RENT-October-2026``), unique per supplier among bills that aren't void (gap-24): when the
number is taken (a pattern without placeholders, two dates in the same month, a bill entered by
hand), ``-2``, ``-3``… is added until it is free. An empty pattern leaves the number empty; an
unknown placeholder in the pattern is refused when the template is saved
(``validate_pattern``, ``purchases.recurring.pattern_unknown``).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.documents import due_dates
from numo9.documents.placeholders import render
from numo9.documents.recurring import (
    REFUSALS,
    Outcome,
    RecurringGenerator,
    period_of,
    reason,
    register,
)
from numo9.orgsettings.models import LockModule

from .models import (
    Bill,
    BillLine,
    BillStatus,
    RecurringBillMode,
    RecurringBillRun,
    RecurringBillTemplate,
)

JOB = "numo9.purchases.recurring_bills"
#: Refusals of an automatic approval that mean "someone else must approve it": route it.
ROUTED = frozenset(
    {"purchases.bill.not_routed_to_you", "approval.limit_exceeded", "approval.no_limit"}
)
NUMBER_MAX = 100


def locale_of(template: Any) -> str:
    """The language placeholders are written in: the organisation's (a bill is the organisation's
    own record of the supplier's invoice)."""
    return str(getattr(template.organisation, "locale", "") or "en-ca").lower()


def due_for(template: Any, day: dt.date) -> dt.date:
    term = template.terms
    if term is not None:
        return due_dates.due_date(day, term.terms_type, term.days)
    terms = due_dates.document_terms(due_dates.PURCHASE, template.contact, template.organisation)
    return due_dates.due_date(day, terms.terms_type, terms.days)


def unique_number(supplier: Any, wanted: str) -> str:
    """``wanted``, or ``wanted-2``, ``wanted-3``… — the first that no bill of the supplier that
    isn't void has (the editor's check, ``uniqueness.number_conflict``: letter case and extra
    spaces don't make a number new), within the field's 100 characters."""
    from .uniqueness import normalise, number_conflict

    base = normalise(wanted)[:NUMBER_MAX]
    if not base:
        return ""
    candidate, n = base, 1
    while number_conflict(supplier, candidate) is not None:
        n += 1
        suffix = f"-{n}"
        candidate = base[: NUMBER_MAX - len(suffix)] + suffix
    return candidate


def supplier_invoice_number(
    template: Any, start: dt.date, end: dt.date, *, locale: str | None = None
) -> str:
    """T03 — the pattern rendered for the period, made unique for the supplier (docstring)."""
    return unique_number(
        template.contact, render(template.supplier_invoice_no or "", start, end, locale)
    )


def validate_pattern(template: Any) -> None:
    """T03 — ``ValidationError`` (``purchases.recurring.pattern_unknown``) for a placeholder the
    renderer doesn't know in the supplier invoice number pattern (it would stay as typed on every
    bill, so the numbers would only differ by their suffix)."""
    from django.core.exceptions import ValidationError

    from numo9.documents.placeholders import NAMES, unknown

    names = unknown(template.supplier_invoice_no or "")
    if names:
        raise ValidationError(
            {
                "supplier_invoice_no": ValidationError(
                    _("%(names)s isn't a placeholder: use %(known)s."),
                    code="purchases.recurring.pattern_unknown",
                    params={
                        "names": ", ".join(names),
                        "known": ", ".join(f"{{{{{n}}}}}" for n in NAMES),
                    },
                )
            }
        )


def build_bill(template: Any, day: dt.date) -> Bill:
    """The draft bill of the occurrence on ``day`` (module docstring); figures the server's."""
    from .bills import recalculate

    start, end = period_of(template, day)
    locale = locale_of(template)

    def text(value: str) -> str:
        return render(value, start, end, locale)

    bill = Bill(
        organisation=template.organisation,
        contact=template.contact,
        date=day,
        due_date=due_for(template, day),
        terms=template.terms,
        supplier_invoice_no=supplier_invoice_number(template, start, end, locale=locale),
        reference=text(template.reference)[:255],
        currency=template.currency,
        tax_mode=template.tax_mode,
        discount_type=template.discount_type,
        discount_value=template.discount_value,
        notes=text(template.notes),
        department=template.department,
        created_by=template.created_by,
    )
    bill.save()
    for position, line in enumerate(template.lines.order_by("position", "pk")):
        BillLine(
            organisation=template.organisation,
            document=bill,
            position=position,
            item=line.item,
            description=text(line.description),
            quantity=Decimal(line.quantity),
            unit_price=Decimal(line.unit_price),
            discount_type=line.discount_type,
            discount_value=line.discount_value,
            account=line.account,
            tax_code=line.tax_code,
            tax_overridden=line.tax_overridden,
            tracking=dict(line.tracking or {}),
        ).save()
    return recalculate(bill)


class RecurringBillGenerator(RecurringGenerator):
    """Recurring bills on the shared generator (module docstring)."""

    template_model = RecurringBillTemplate
    run_model = RecurringBillRun
    job = JOB
    lock_module = LockModule.AP
    event_prefix = "purchases.recurring_bill"

    def build(self, template: Any, day: dt.date) -> Any:
        return build_bill(template, day)

    def finish(self, template: Any, document: Any) -> Outcome:
        from .bill_posting import approve
        from .routing import submit

        if template.mode == RecurringBillMode.DRAFT:
            return Outcome(document)
        actor = template.created_by
        try:
            with transaction.atomic():
                return Outcome(approve(document, actor))
        except REFUSALS as error:
            code, message = reason(error)
        if code in ROUTED:
            try:
                with transaction.atomic():
                    waiting = submit(document, actor)
            except REFUSALS as error:
                code, message = reason(error)
            else:
                assert waiting.status == BillStatus.AWAITING_APPROVAL  # noqa: S101
                return Outcome(
                    waiting,
                    "purchases.recurring.awaiting_approval",
                    _("The bill needs approval before it is posted: %(why)s") % {"why": message},
                )
        return Outcome(document, code, message, notify=True)

    def link(self, template: Any) -> str:
        return (
            f"/o/{template.organisation.public_id}/purchases/recurring-bills/{template.public_id}"
        )


GENERATOR = register("bills", RecurringBillGenerator())  # manage.py replay_ticks --kind bills


def generate_due(organisation: Any, today: dt.date) -> list[Any]:
    return GENERATOR.generate_due(organisation, today)


def generate_all(now: dt.datetime | None = None) -> dict[str, int]:
    return GENERATOR.generate_all(now)
