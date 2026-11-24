"""D-03a-T12 — Email send with the PDF attached and "viewed" tracking.

Acceptance: the send is logged; a bounce flags the contact — ``send_invoice`` emails the PDF
(one email per recipient through the A-07 queue, attached when the worker sends), logs an
``InvoiceEmail`` row and the audit event, marks an approved invoice sent; the "View invoice" link
records the first view; a bounce reported by the provider flags the contact person's address.
Drafts and invoices without a recipient are refused.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from anymail.signals import AnymailTrackingEvent, tracking
from django.core import mail
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.contacts.models import ContactPerson
from numo9.files.storage import open_object
from numo9.notifications import mail as outgoing
from numo9.notifications.models import EmailMessage
from numo9.sales.email import send_invoice, view_token
from numo9.sales.models import InvoiceEmail
from numo9.sales.posting import InvoiceRefused, approve
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books("Maple Leaf Supply Ltd.")
    books["owner"] = people(books["org"])["owner"]
    org, customer = books["org"], books["customers"]["ON"]
    with org_context(org):
        ContactPerson.objects.create(
            organisation=org,
            contact=customer,
            first_name="Ana",
            email="ap@oncustomer.ca",
            include_in_emails=True,
            is_primary=True,
        )
        ContactPerson.objects.create(
            organisation=org,
            contact=customer,
            first_name="Cy",
            email="cy@oncustomer.ca",
            include_in_emails=False,
        )
    return books


@pytest.fixture
def captured() -> Any:
    sent: list[Any] = []
    with mock.patch.object(
        outgoing.send_email, "apply_async", lambda args=None, **kw: sent.append(args)
    ):
        yield sent


def _approved(books: dict[str, Any]) -> Any:
    return approve(draft(books, [("2", "150.00", "sales.ON.standard")]), books["owner"])


def test_send_logs_attaches_pdf_and_marks_sent(
    books: dict[str, Any], s3: str, captured: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    org = books["org"]
    invoice = _approved(books)
    with org_context(org), django_capture_on_commit_callbacks(execute=True):
        row = send_invoice(invoice, books["owner"])
    assert row.recipients == ["ap@oncustomer.ca"]  # included people only
    assert row.subject == "Invoice INV-0001 from Maple Leaf Supply Ltd."
    assert row.sent_by == books["owner"] and len(row.email_messages) == 1
    with org_context(org):
        invoice.refresh_from_db()
        assert invoice.status == "sent" and invoice.sent_at is not None
        assert AuditEvent.objects.filter(action="sales.invoice.sent").count() == 1
    stored = open_object(row.file_key).read()
    assert stored.startswith(b"%PDF")
    [message] = EmailMessage.platform_messages.filter(kind="sales.invoice")
    assert "Amount due: $339.00 CAD" in message.text_body
    assert "/api/v1/invoice-view/" in message.text_body
    assert len(captured) == 1
    outgoing.send_email.apply(args=[message.pk])
    [email] = mail.outbox
    [(name, content, mime)] = email.attachments
    assert (name, mime, content) == ("invoice-INV-0001.pdf", "application/pdf", stored)


def test_second_send_keeps_first_sent_at(books: dict[str, Any], s3: str, captured: Any) -> None:
    invoice = _approved(books)
    with org_context(books["org"]):
        send_invoice(invoice, books["owner"])
        first = invoice.sent_at
        send_invoice(invoice, books["owner"], to=["boss@oncustomer.ca"], subject="Again")
        invoice.refresh_from_db()
        assert invoice.sent_at == first
        assert InvoiceEmail.objects.filter(invoice=invoice).count() == 2


def test_draft_and_no_recipient_are_refused(books: dict[str, Any], s3: str) -> None:
    invoice = draft(books, [("1", "10.00", "sales.ON.standard")])
    with org_context(books["org"]), pytest.raises(InvoiceRefused) as refused:
        send_invoice(invoice, books["owner"])
    assert refused.value.code == "sales.invoice.not_sendable"
    approved = _approved(books)
    with org_context(books["org"]), pytest.raises(InvoiceRefused) as refused:
        send_invoice(approved, books["owner"], to=[])
    assert refused.value.code == "sales.invoice.no_recipient"


def test_view_link_records_first_view(books: dict[str, Any], s3: str, captured: Any) -> None:
    invoice = _approved(books)
    with org_context(books["org"]):
        row = send_invoice(invoice, books["owner"])
    client = Client()
    opened = client.get(f"/api/v1/invoice-view/{view_token(row)}")
    assert opened.status_code == 200 and opened["Content-Type"] == "application/pdf"
    assert opened.content.startswith(b"%PDF")
    with org_context(books["org"]):
        row.refresh_from_db()
        invoice.refresh_from_db()
        first = invoice.viewed_at
        assert row.viewed_at is not None and first is not None
    client.get(f"/api/v1/invoice-view/{view_token(row)}")
    with org_context(books["org"]):
        invoice.refresh_from_db()
        assert invoice.viewed_at == first  # the first view only
        assert AuditEvent.objects.filter(action="sales.invoice.viewed").count() == 1
    assert client.get("/api/v1/invoice-view/not-a-token").status_code == 404


def test_bounce_flags_the_contact(books: dict[str, Any], s3: str, captured: Any) -> None:
    invoice = _approved(books)
    with org_context(books["org"]):
        row = send_invoice(invoice, books["owner"])
    [message] = EmailMessage.platform_messages.filter(kind="sales.invoice")
    event = AnymailTrackingEvent(
        event_type="bounced",
        recipient="ap@oncustomer.ca",
        metadata={"numo9_message": str(message.public_id)},
        description="550 mailbox unavailable",
    )
    tracking.send(sender=object(), event=event, esp_name="test")
    message.refresh_from_db()
    assert message.status == "bounced"
    with org_context(books["org"]):
        person = ContactPerson.objects.get(email="ap@oncustomer.ca")
        assert person.email_status == "bounced"
    assert row.email_messages == [str(message.public_id)]


def test_api_composer_defaults_send_and_pdf(books: dict[str, Any], s3: str, captured: Any) -> None:
    invoice = _approved(books)
    client = Client()
    client.force_login(books["owner"])
    base = f"/api/v1/o/{books['org'].public_id}/invoices/{invoice.public_id}"
    defaults = client.get(f"{base}/email")
    assert defaults.status_code == 200, defaults.json()
    body = defaults.json()
    assert body["to"] == ["ap@oncustomer.ca"] and body["sendable"] is True
    assert body["file_name"] == "invoice-INV-0001.pdf" and body["sends"] == []
    sent = client.post(
        f"{base}/email",
        {"to": ["ap@oncustomer.ca"], "subject": body["subject"], "message": "Hi"},
        content_type="application/json",
    )
    assert sent.status_code == 201, sent.json()
    assert sent.json()["recipients"] == ["ap@oncustomer.ca"]
    assert len(client.get(f"{base}/email").json()["sends"]) == 1
    pdf = client.get(f"{base}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
