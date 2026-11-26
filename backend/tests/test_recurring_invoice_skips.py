"""D-04-T06 — skip rules: paused, ended, locked period, archived contact.

Acceptance: skips logged, owner notified — a skipped occurrence is a ``skipped`` run with its
reason code and an audit event, never generated on another date nor retried; the template's
owner (its author, else the organisation's owners and admins) is notified on commit — except for
a pause, which the owner chose. The end of a schedule (its end date, or the service end) is
told once.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.notifications.models import Notification
from numo9.orgsettings.models import LockDate
from numo9.sales.models import Invoice, RecurringInvoiceRun, RecurringInvoiceTemplate
from numo9.sales.recurring_invoices import generate_due
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import sales_books
from tests.test_recurring_invoice_generation import invoices, make_template

pytestmark = pytest.mark.django_db
D = dt.date


@pytest.fixture
def books(db: Any) -> dict[str, Any]:
    books = sales_books()
    books["owner"] = people(books["org"])["owner"]
    return books


def runs(books: dict[str, Any]) -> list[tuple[dt.date, str, str]]:
    with org_context(books["org"]):
        return [
            (r.occurrence_date, r.status, r.code)
            for r in RecurringInvoiceRun.objects.order_by("occurrence_date")
        ]


def notes(books: dict[str, Any], who: Any = None) -> list[str]:
    with org_context(books["org"]):
        return list(
            Notification.objects.filter(recipient=who or books["owner"])
            .order_by("pk")
            .values_list("title_key", flat=True)
        )


def test_paused_occurrences_are_logged_not_billed_nor_notified(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    template = make_template(books, paused=True)
    with django_capture_on_commit_callbacks(execute=True):
        generate_due(books["org"], D(2026, 2, 28))
    assert runs(books) == [
        (D(2026, 1, 31), "skipped", "documents.recurring.paused"),
        (D(2026, 2, 28), "skipped", "documents.recurring.paused"),
    ]
    assert invoices(books["org"]) == [] and notes(books) == []
    with org_context(books["org"]):
        RecurringInvoiceTemplate.objects.filter(pk=template.pk).update(paused=False)
        template.refresh_from_db()
        assert template.next_run == D(2026, 3, 31)  # resuming doesn't bill the paused months
        assert (
            AuditEvent.objects.filter(action="sales.recurringinvoicetemplate.skipped").count() == 2
        )
    generate_due(books["org"], D(2026, 3, 31))
    assert [i.date for i in invoices(books["org"])] == [D(2026, 3, 31)]


def test_locked_period_is_skipped_with_the_reason_and_the_owner_told(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    template = make_template(books)
    with org_context(org):
        LockDate(organisation=org, module="ar", level="everyone", date=D(2026, 2, 28)).save()
    with django_capture_on_commit_callbacks(execute=True):
        generate_due(org, D(2026, 3, 31))
    assert runs(books) == [
        (D(2026, 1, 31), "skipped", "lock.violation"),
        (D(2026, 2, 28), "skipped", "lock.violation"),
        (D(2026, 3, 31), "created", ""),
    ]
    with org_context(org):
        skipped = RecurringInvoiceRun.objects.filter(status="skipped").first()
        assert skipped is not None and "2026-02-28" in skipped.message
        note = Notification.objects.filter(recipient=books["owner"]).first()
        assert note is not None and note.body_params["name"] == template.name
        assert note.link.endswith(f"/sales/recurring-invoices/{template.public_id}")
    assert notes(books) == ["notifications.sales.recurring.skipped"] * 2
    assert [i.date for i in invoices(org)] == [D(2026, 3, 31)]  # never moved to another date
    assert generate_due(org, D(2026, 3, 31)) == []  # a skipped date isn't retried


def test_archived_customer_is_skipped_and_the_owner_told(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    make_template(books)
    with org_context(org):
        books["customers"]["ON"].archive()
    with django_capture_on_commit_callbacks(execute=True):
        generate_due(org, D(2026, 1, 31))
    assert runs(books) == [(D(2026, 1, 31), "skipped", "documents.recurring.contact_archived")]
    assert invoices(org) == []
    assert notes(books) == ["notifications.sales.recurring.skipped"]


def test_the_end_date_ends_the_schedule_and_says_so_once(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    template = make_template(books, end_date=D(2026, 2, 28))
    with django_capture_on_commit_callbacks(execute=True):
        generate_due(org, D(2026, 6, 30))
        generate_due(org, D(2026, 7, 31))
    assert [i.date for i in invoices(org)] == [D(2026, 1, 31), D(2026, 2, 28)]
    with org_context(org):
        template.refresh_from_db()
        assert (template.next_run, template.last_run) == (None, D(2026, 2, 28))
        assert AuditEvent.objects.filter(action="sales.recurringinvoicetemplate.ended").count() == 1
    assert notes(books) == ["notifications.sales.recurring.ended"]


def test_an_end_date_moved_before_the_next_run_ends_it(books: dict[str, Any]) -> None:
    org = books["org"]
    template = make_template(books)
    generate_due(org, D(2026, 1, 31))
    with org_context(org):
        RecurringInvoiceTemplate.objects.filter(pk=template.pk).update(end_date=D(2026, 2, 10))
    assert generate_due(org, D(2026, 3, 31)) == []
    with org_context(org):
        template.refresh_from_db()
        assert template.next_run is None


def test_service_end_prorates_the_last_period_then_ends(books: dict[str, Any]) -> None:
    org = books["org"]
    template = make_template(
        books, start_date=D(2026, 9, 1), prorate=True, service_end=D(2026, 10, 15)
    )
    generate_due(org, D(2026, 12, 31))
    september, october = invoices(org)
    with org_context(org):
        assert september.lines.get().net == Decimal("310.00")
        assert october.lines.get().net == Decimal("150.00")  # 15 of 31 days
        template.refresh_from_db()
        assert template.next_run is None


def test_before_the_service_starts_nothing_is_billed(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    make_template(books, start_date=D(2026, 9, 1), prorate=True, service_start=D(2026, 10, 20))
    with django_capture_on_commit_callbacks(execute=True):
        generate_due(books["org"], D(2026, 10, 1))
    assert runs(books) == [
        (D(2026, 9, 1), "skipped", "sales.recurring.not_started"),
        (D(2026, 10, 1), "created", ""),
    ]
    assert notes(books) == []


def test_without_an_author_the_organisations_owners_are_told(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    make_template(books, created_by=None)
    with org_context(org):
        books["customers"]["ON"].archive()
    with django_capture_on_commit_callbacks(execute=True):
        generate_due(org, D(2026, 1, 31))
    assert notes(books) == ["notifications.sales.recurring.skipped"]
    with org_context(org):
        assert Invoice.objects.count() == 0
