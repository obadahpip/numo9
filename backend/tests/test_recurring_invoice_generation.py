"""D-04-T05 — the recurring-invoice generator: one invoice per occurrence, idempotent.

Acceptance: exactly one invoice per tick after a restart — two workers (threads, each its own
connection) and a worker that dies mid-run (its transaction rolls back; the rerun creates the
invoice once) leave one invoice per occurrence (the unique (template, date) run row). Modes:
draft → a draft; approve → approved and posted (numbered at approval), above the threshold
Awaiting approval; approve and send → emailed. A refused approval keeps the draft and a refused
send keeps the approved invoice, both recorded on the run (the owner is told). Placeholders,
due dates and proration are those of T02–T04; next/last run move; the hourly job runs each
organisation on its own date.
"""

from __future__ import annotations

import datetime as dt
import threading
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from django.conf import settings as django_settings
from django.db import connection
from freezegun import freeze_time

from numo9.audit.models import AuditEvent
from numo9.contacts.models import ContactPerson
from numo9.documents.recurring import GenerationFailed
from numo9.notifications.models import Notification
from numo9.orgsettings.service import get_settings
from numo9.sales import recurring_invoices
from numo9.sales.models import (
    Invoice,
    InvoiceStatus,
    RecurringInvoiceLine,
    RecurringInvoiceRun,
    RecurringInvoiceTemplate,
)
from numo9.sales.recurring_invoices import GENERATOR, JOB, generate_all, generate_due
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people
from tests.sales_helpers import sales_books

D = dt.date


def make_template(books: dict[str, Any], **fields: Any) -> RecurringInvoiceTemplate:
    org = books["org"]
    values: dict[str, Any] = {
        "organisation": org,
        "name": "Monthly retainer",
        "contact": books["customers"]["ON"],
        "reference": "Retainer {{month}} {{year}}",
        "notes": "Service {{period_start}} – {{period_end}}",
        "rrule": "FREQ=MONTHLY",
        "start_date": D(2026, 1, 31),
        "created_by": books.get("owner"),
    }
    values.update(fields)
    with org_context(org):
        template = RecurringInvoiceTemplate(**values)
        template.full_clean()
        template.save()
        RecurringInvoiceLine(
            organisation=org,
            document=template,
            position=0,
            description="Bookkeeping, {{month}}",
            quantity=Decimal("1"),
            unit_price=Decimal("310.00"),
            account=books["revenue"],
            tax_code=code_for("sales.ON.standard", "sales", D(2026, 1, 31), org),
        ).save()
        return template


def invoices(org: Organisation) -> list[Invoice]:
    with org_context(org):
        return list(Invoice.objects.filter(recurring_run__isnull=False).order_by("date", "pk"))


@pytest.fixture
def books(db: Any) -> dict[str, Any]:
    books = sales_books()
    books["owner"] = people(books["org"])["owner"]
    return books


@pytest.mark.django_db
def test_draft_mode_one_invoice_per_occurrence_and_a_rerun_adds_nothing(
    books: dict[str, Any],
) -> None:
    org = books["org"]
    template = make_template(books)
    runs = generate_due(org, D(2026, 3, 31))
    assert [(r.occurrence_date, r.status) for r in runs] == [
        (D(2026, 1, 31), "created"),
        (D(2026, 2, 28), "created"),
        (D(2026, 3, 31), "created"),
    ]
    made = invoices(org)
    assert [(i.date, i.status, i.number) for i in made] == [
        (D(2026, 1, 31), InvoiceStatus.DRAFT, ""),
        (D(2026, 2, 28), InvoiceStatus.DRAFT, ""),
        (D(2026, 3, 31), InvoiceStatus.DRAFT, ""),
    ]
    first = made[0]
    assert first.reference == "Retainer January 2026"
    assert first.notes == "Service 31 Jan 2026 – 27 Feb 2026"
    assert first.due_date is not None and first.due_date >= first.date
    with org_context(org):
        (line,) = first.lines.all()
        assert line.description == "Bookkeeping, January"
        assert (line.net, first.total) == (Decimal("310.00"), Decimal("350.30"))
        assert first.created_by == books["owner"]
    assert generate_due(org, D(2026, 3, 31)) == []  # the job again: nothing more
    assert len(invoices(org)) == 3
    with org_context(org):
        template.refresh_from_db()
        assert (template.next_run, template.last_run) == (D(2026, 4, 30), D(2026, 3, 31))
        assert {r.template_version for r in RecurringInvoiceRun.objects.all()} == {1}
        assert (
            AuditEvent.objects.filter(action="sales.recurringinvoicetemplate.generated").count()
            == 3
        )


@pytest.mark.django_db
def test_french_customer_gets_french_placeholders(books: dict[str, Any]) -> None:
    org = books["org"]
    customer = books["customers"]["QC"]
    with org_context(org):
        customer.language = "fr-ca"
        customer.save()
    make_template(books, contact=customer, start_date=D(2026, 10, 1))
    generate_due(org, D(2026, 10, 1))
    (invoice,) = invoices(org)
    assert invoice.reference == "Retainer octobre 2026"


@pytest.mark.django_db
def test_approve_mode_posts_and_numbers_each_invoice(books: dict[str, Any]) -> None:
    org = books["org"]
    make_template(books, mode="approve")
    generate_due(org, D(2026, 2, 28))
    made = invoices(org)
    assert [(i.status, i.number) for i in made] == [
        (InvoiceStatus.APPROVED, "INV-0001"),
        (InvoiceStatus.APPROVED, "INV-0002"),
    ]
    assert all(i.journal_entry_id for i in made)


@pytest.mark.django_db
def test_above_the_threshold_the_invoice_waits_for_approval(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        settings = get_settings(org)
        settings.invoice_approval_threshold = Decimal("100.00")
        settings.save()
    make_template(books, mode="approve")
    (run,) = generate_due(org, D(2026, 1, 31))
    assert (run.status, run.code) == ("created", "sales.recurring.awaiting_approval")
    (invoice,) = invoices(org)
    assert (invoice.status, invoice.number) == (InvoiceStatus.AWAITING_APPROVAL, "")


@pytest.mark.django_db
def test_a_refused_approval_keeps_the_draft_and_tells_the_owner(
    books: dict[str, Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    template = make_template(books, mode="approve")
    with org_context(org):
        template.lines.update(account=None)  # "every line needs an account" at approval
    with django_capture_on_commit_callbacks(execute=True):
        (run,) = generate_due(org, D(2026, 1, 31))
    assert (run.status, run.code) == ("created", "sales.invoice.incomplete")
    (invoice,) = invoices(org)
    assert invoice.status == InvoiceStatus.DRAFT
    with org_context(org):
        (note,) = Notification.objects.filter(recipient=books["owner"])
        assert note.title_key == "notifications.sales.recurring.failed"
        assert note.link.endswith(f"/sales/recurring-invoices/{template.public_id}")


@pytest.mark.django_db
def test_approve_and_send_emails_the_invoice(books: dict[str, Any], s3: str) -> None:
    org = books["org"]
    customer = books["customers"]["ON"]
    with org_context(org):
        ContactPerson.objects.create(
            organisation=org,
            contact=customer,
            first_name="Ana",
            email="ap@oncustomer.ca",
            include_in_emails=True,
            is_primary=True,
        )
    make_template(books, mode="approve_send")
    (run,) = generate_due(org, D(2026, 1, 31))
    assert (run.status, run.code) == ("created", "")
    (invoice,) = invoices(org)
    assert invoice.status == InvoiceStatus.SENT and invoice.number == "INV-0001"
    with org_context(org):
        assert invoice.emails.get().recipients == ["ap@oncustomer.ca"]


@pytest.mark.django_db
def test_a_refused_send_keeps_the_approved_invoice(books: dict[str, Any], s3: str) -> None:
    org = books["org"]
    make_template(books, mode="approve_send")  # nobody "included in emails"
    (run,) = generate_due(org, D(2026, 1, 31))
    assert (run.status, run.code) == ("created", "sales.invoice.no_recipient")
    (invoice,) = invoices(org)
    assert invoice.status == InvoiceStatus.APPROVED


@pytest.mark.django_db
def test_first_partial_period_is_prorated(books: dict[str, Any]) -> None:
    org = books["org"]
    make_template(books, start_date=D(2026, 10, 1), prorate=True, service_start=D(2026, 10, 17))
    generate_due(org, D(2026, 11, 1))
    october, november = invoices(org)
    with org_context(org):
        assert october.lines.get().net == Decimal("150.00")  # 15 of 31 days of 310.00
        assert november.lines.get().net == Decimal("310.00")


@pytest.mark.django_db
def test_a_worker_that_dies_mid_run_leaves_nothing_and_the_rerun_creates_one(
    books: dict[str, Any],
) -> None:
    org = books["org"]
    make_template(books)
    real = GENERATOR.finish

    def dies(template: Any, document: Any) -> Any:
        raise SystemExit("worker killed")

    with mock.patch.object(GENERATOR, "finish", dies), pytest.raises(SystemExit):
        generate_due(org, D(2026, 1, 31))
    assert invoices(org) == []
    with org_context(org):
        assert RecurringInvoiceRun.objects.count() == 0
        assert Invoice.objects.count() == 0  # the half-built invoice rolled back too
    assert GENERATOR.finish == real
    generate_due(org, D(2026, 1, 31))
    generate_due(org, D(2026, 1, 31))
    assert [i.date for i in invoices(org)] == [D(2026, 1, 31)]


@pytest.mark.django_db
def test_the_hourly_job_uses_each_organisations_date(books: dict[str, Any]) -> None:
    make_template(books)
    assert django_settings.CELERY_BEAT_SCHEDULE[JOB]["task"] == JOB
    with freeze_time("2026-02-01 03:00:00"):  # 22:00 on 31 January in Toronto
        assert generate_all() == {"created": 1, "skipped": 0, "failed": 0}
    with freeze_time("2026-02-28 04:00:00"):  # 23:00 on 27 February in Toronto: not yet
        assert generate_all()["created"] == 0
    with freeze_time("2026-02-28 06:00:00"):
        assert generate_all()["created"] == 1


@pytest.mark.django_db
def test_one_failing_template_does_not_stop_the_others(books: dict[str, Any]) -> None:
    first = make_template(books, name="A")
    make_template(books, name="B")
    real = recurring_invoices.build_invoice

    def flaky(template: Any, day: dt.date) -> Any:
        if template.pk == first.pk:
            raise RuntimeError("bug")
        return real(template, day)

    with (
        mock.patch.object(recurring_invoices, "build_invoice", flaky),
        freeze_time("2026-02-01 12:00:00"),
        pytest.raises(GenerationFailed, match="1 recurring template"),
    ):
        generate_all()
    assert len(invoices(books["org"])) == 1
    with freeze_time("2026-02-01 13:00:00"):  # fixed: the next tick catches up, once
        assert generate_all()["created"] == 1
    assert len(invoices(books["org"])) == 2


@pytest.mark.django_db(transaction=True)
def test_two_workers_create_exactly_one_invoice_per_occurrence() -> None:
    books = sales_books("Race Ltd.")
    org = books["org"]
    make_template(books)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait(timeout=10)
            generate_due(org, D(2026, 6, 30))
        except BaseException as error:  # noqa: BLE001 — reported below
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert errors == []
    assert [i.date for i in invoices(org)] == [
        D(2026, 1, 31),
        D(2026, 2, 28),
        D(2026, 3, 31),
        D(2026, 4, 30),
        D(2026, 5, 31),
        D(2026, 6, 30),
    ]
    with org_context(org):
        assert RecurringInvoiceRun.objects.count() == 6
        assert Invoice.objects.count() == 6
