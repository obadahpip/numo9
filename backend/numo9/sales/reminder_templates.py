"""Invoice reminders — the seeded templates and the default schedule (D-07-T13).

Four email templates, each in English and French (``notifications/templates/email/<name>/``:
subject, text and HTML — A-07 templating, rendered in the customer's language):

- ``invoice_reminder_before_due`` — steps before the due date: due on the date, in N days;
- ``invoice_reminder_due`` — the step on the due date: due today;
- ``invoice_reminder_overdue`` — steps after it: N days overdue, the amount still owing;
- ``invoice_reminder_final`` — the last step: final reminder, pay or arrange payment.

Each reads ``contact`` (the customer's name), ``number``, ``amount_due`` (what is still owing,
with its currency), ``due_date``, ``days`` (before or after the due date, always positive),
``link`` (the invoice's view link) and ``organisation`` — ``reminder_context()`` builds them.

``ensure_default_schedule(organisation)`` seeds the organisation's default schedule the first time
it is needed: −7 (before due), 0 (due), +7 and +14 (overdue), +30 (final, notifying the owner),
by email, from $1.00 owing.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.utils import translation

from numo9.documents.formatting import format_date, format_money
from numo9.tenancy.context import org_context

from .models import ReminderEscalation, ReminderSchedule, ReminderStep

BEFORE_DUE = "invoice_reminder_before_due"
DUE = "invoice_reminder_due"
OVERDUE = "invoice_reminder_overdue"
FINAL = "invoice_reminder_final"
TEMPLATES = (BEFORE_DUE, DUE, OVERDUE, FINAL)
CONTEXT = ("contact", "number", "amount_due", "due_date", "days", "link", "organisation")

#: (offset days, template, escalation) of the default schedule.
DEFAULT_STEPS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (-7, BEFORE_DUE, ()),
    (0, DUE, ()),
    (7, OVERDUE, ()),
    (14, OVERDUE, ()),
    (30, FINAL, (ReminderEscalation.NOTIFY_OWNER.value,)),
)
DEFAULT_MIN_AMOUNT = Decimal("1.00")


def template_for(offset_days: int) -> str:
    """The template a step at ``offset_days`` uses by default."""
    if offset_days < 0:
        return BEFORE_DUE
    return DUE if offset_days == 0 else OVERDUE


def ensure_default_schedule(organisation: Any) -> ReminderSchedule:
    """The organisation's default schedule, seeded with ``DEFAULT_STEPS`` when it has none."""
    with org_context(organisation):
        existing: ReminderSchedule | None = ReminderSchedule.objects.filter(is_default=True).first()
        if existing is not None:
            return existing
        with translation.override(organisation.locale or "en-ca"):
            name = str(translation.gettext("Standard reminders"))
        schedule = ReminderSchedule(organisation=organisation, name=name, is_default=True)
        schedule.save()
        ReminderStep.objects.bulk_create(
            [
                ReminderStep(
                    organisation=organisation,
                    schedule=schedule,
                    offset_days=offset,
                    template=template,
                    min_amount=DEFAULT_MIN_AMOUNT,
                    escalation=list(escalation),
                )
                for offset, template, escalation in DEFAULT_STEPS
            ]
        )
        return schedule


def reminder_context(
    invoice: Any, offset_days: int, *, amount_due: Decimal, link: str, language: str
) -> dict[str, Any]:
    """The values the reminder templates read, formatted for ``language``."""
    due: dt.date = invoice.due_date
    with translation.override(language):
        return {
            "contact": invoice.contact.display_name,
            "number": invoice.number,
            "amount_due": f"{format_money(amount_due, language)} {invoice.currency}",
            "due_date": format_date(due, language),
            "days": abs(offset_days),
            "link": link,
            "organisation": invoice.organisation.name,
        }
