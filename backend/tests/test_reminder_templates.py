"""D-07-T13 — the EN/FR invoice reminder templates are seeded: each renders in both languages
(snapshots ``tests/snapshots/email/invoice_reminder_*.<lang>.*``) with every value filled; the
default schedule is seeded once with them."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.notifications.templating import render_email, template_exists
from numo9.sales.models import ReminderSchedule
from numo9.sales.reminder_templates import (
    CONTEXT,
    DEFAULT_STEPS,
    TEMPLATES,
    ensure_default_schedule,
    reminder_context,
    template_for,
)
from numo9.tenancy.context import org_context
from tests.email_snapshots import assert_snapshot
from tests.reminder_helpers import invoice, reminder_books

SAMPLE: dict[str, Any] = {
    "contact": "Maple Leaf Supply Ltd.",
    "number": "INV-0042",
    "amount_due": "$1,130.00 CAD",
    "due_date": "1 Jul 2026",
    "days": 7,
    "link": "https://app.numo9.ca/api/v1/invoice-view/tok-abc",
    "organisation": "Refined Interiors Inc.",
}


@pytest.mark.parametrize("language", ["en-ca", "fr-ca"])
@pytest.mark.parametrize("name", TEMPLATES)
def test_every_template_renders_in_both_languages(name: str, language: str) -> None:
    assert template_exists(name)
    email = render_email(name, SAMPLE, language=language)
    assert email.language == language and not email.fallback
    for part in (email.subject, email.text):
        assert "INV-0042" in part
    assert "$1,130.00 CAD" in email.text and SAMPLE["link"] in email.text
    assert "{{" not in email.text + email.html + email.subject
    assert_snapshot(f"{name}.{language}.subject.txt", email.subject + "\n")
    assert_snapshot(f"{name}.{language}.txt", email.text)
    assert_snapshot(f"{name}.{language}.html", email.html)


def test_french_reads_french() -> None:
    email = render_email("invoice_reminder_overdue", SAMPLE, language="fr-ca")
    assert email.subject == "La facture INV-0042 est en retard de 7 jours"
    assert "Montant dû" in email.text and "courriel" in email.text


def test_template_for_offset() -> None:
    assert [template_for(d) for d in (-7, 0, 14)] == [
        "invoice_reminder_before_due",
        "invoice_reminder_due",
        "invoice_reminder_overdue",
    ]


@pytest.mark.django_db
def test_default_schedule_seeded_once() -> None:
    books: dict[str, Any] = reminder_books()
    org = books["org"]
    first = ensure_default_schedule(org)
    again = ensure_default_schedule(org)
    assert first.pk == again.pk
    with org_context(org):
        assert ReminderSchedule.objects.count() == 1
        steps = list(first.steps.order_by("offset_days"))
    assert [(s.offset_days, s.template, s.escalation) for s in steps] == [
        (offset, template, list(escalation)) for offset, template, escalation in DEFAULT_STEPS
    ]
    assert all(s.template in TEMPLATES for s in steps)


@pytest.mark.django_db
def test_context_from_an_invoice() -> None:
    books: dict[str, Any] = reminder_books()
    inv = invoice(books, due=dt.date(2026, 7, 1))
    with org_context(books["org"]):
        context = reminder_context(
            inv, -7, amount_due=Decimal("113.00"), link="https://x/i", language="fr-ca"
        )
    assert set(context) == set(CONTEXT)
    assert context["days"] == 7 and context["number"] == inv.number
    assert context["amount_due"].endswith("CAD")
    email = render_email("invoice_reminder_before_due", context, language="fr-ca")
    assert inv.number in email.subject
