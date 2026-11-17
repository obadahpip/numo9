"""B-02-T06 — Statement send via A-07 + history record.

Acceptance: the sent statement is stored in the history and the timeline — ``send_statement``
emails the PDF (A-07 message log, one email per recipient, the PDF attached when the worker
sends), records a ``StatementSend`` row (kind, dates, amount due, currency, recipients,
language, the stored PDF, the email messages, who), audits it and announces it with
``statement_sent`` (the activity timeline's hook, B-02-T02). The email is in the contact's
language; a contact without anyone to email is refused; an attachment of another organisation
is never sent.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from django.core import mail

from numo9.audit.context import audit_context
from numo9.audit.models import AuditEvent
from numo9.contacts.models import ContactPerson, StatementSend
from numo9.contacts.statements import (
    StatementError,
    StatementKind,
    sample_statement,
    send_statement,
    statement_sent,
)
from numo9.files.storage import open_object
from numo9.notifications import mail as outgoing
from numo9.notifications.models import EmailMessage, EmailStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def captured() -> Any:
    sent: list[Any] = []
    with mock.patch.object(
        outgoing.send_email, "apply_async", lambda args=None, **kw: sent.append(args)
    ):
        yield sent


def _customer(org: Organisation, **fields: Any) -> Any:
    with org_context(org):
        cedar = contact(org, "Cedar Roofing Co.", **fields)
        ContactPerson.objects.create(
            organisation=org,
            contact=cedar,
            first_name="Ana",
            email="ap@cedar.ca",
            include_in_emails=True,
            is_primary=True,
        )
        ContactPerson.objects.create(
            organisation=org,
            contact=cedar,
            first_name="Bo",
            email="bo@cedar.ca",
            include_in_emails=True,
        )
        ContactPerson.objects.create(
            organisation=org,
            contact=cedar,
            first_name="Cy",
            email="cy@cedar.ca",
            include_in_emails=False,
        )
    return cedar


def test_send_emails_the_pdf_and_keeps_history(
    org: Organisation, s3: str, captured: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    cedar = _customer(org)
    clerk = user("sam@mapleleaf.ca", "Sam Patel")
    heard: list[Any] = []
    statement_sent.connect(lambda sender, send, **kw: heard.append(send), weak=False)
    document = sample_statement(StatementKind.OUTSTANDING)
    with (
        org_context(org),
        audit_context(user=clerk),
        django_capture_on_commit_callbacks(execute=True),
    ):
        row = send_statement(cedar, document, user=clerk)
    assert isinstance(row, StatementSend)
    assert row.recipients == ["ap@cedar.ca", "bo@cedar.ca"]  # included people, primary first
    assert (row.kind, str(row.amount_due), row.currency, row.language) == (
        "outstanding",
        "3729.00",
        "CAD",
        "en-ca",
    )
    assert row.sent_by == clerk and len(row.email_messages) == 2
    assert heard == [row]  # the activity timeline's hook
    with org_context(org):
        assert list(StatementSend.objects.filter(contact=cedar)) == [row]  # the history
    stored = open_object(row.file_key).read()
    assert stored.startswith(b"%PDF")
    messages = list(EmailMessage.platform_messages.filter(kind="contacts.statement"))
    assert {m.to_email for m in messages} == {"ap@cedar.ca", "bo@cedar.ca"}
    assert messages[0].subject == "Statement from Maple Leaf Supply Ltd. — 30 Nov 2026"
    assert "Amount due: $3,729.00 CAD" in messages[0].text_body
    assert len(captured) == 2  # queued to the worker after commit
    outgoing.send_email.apply(args=[messages[0].pk])
    [email] = mail.outbox
    [(name, content, mime)] = email.attachments
    assert (name, mime) == (row.file_name, "application/pdf") and content == stored
    assert EmailMessage.platform_messages.get(pk=messages[0].pk).status == EmailStatus.SENT
    event = AuditEvent.platform_events.get(action="contacts.statement.sent")
    assert event.organisation_id == org.pk and event.actor_user_id == clerk.pk


def test_email_in_the_contacts_language(org: Organisation, s3: str, captured: list[Any]) -> None:
    cedar = _customer(org, language="fr-ca")
    with org_context(org):
        row = send_statement(cedar, sample_statement(StatementKind.ACTIVITY), to=["ap@cedar.ca"])
    message = EmailMessage.platform_messages.get(public_id=row.email_messages[0])
    assert row.language == "fr-ca" and message.language == "fr-ca"
    assert message.subject == "Relevé de Maple Leaf Supply Ltd. — 30 nov. 2026"
    assert "relevé des opérations du 1 nov. 2026 au 30 nov. 2026" in message.text_body


def test_nobody_to_email_is_refused(org: Organisation, s3: str) -> None:
    with org_context(org):
        lonely = contact(org, "Lonely Pines Inc.")
        with pytest.raises(StatementError):
            send_statement(lonely, sample_statement())
        assert not StatementSend.objects.exists()


def test_foreign_attachment_is_never_sent(org: Organisation, captured: list[Any]) -> None:
    other = Organisation.objects.create(name="Other Inc.")
    message = outgoing.queue_email(
        "x@cedar.ca",
        "s",
        "t",
        organisation=org,
        attachments=[{"key": f"org/{other.public_id}/2026/11/x/a.pdf", "filename": "a.pdf"}],
    )
    outgoing.send_email.apply(args=[message.pk])
    assert mail.outbox == []
    assert EmailMessage.platform_messages.get(pk=message.pk).status == EmailStatus.FAILED
