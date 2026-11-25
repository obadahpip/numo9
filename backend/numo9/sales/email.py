"""Emailing an invoice (D-03a-T12): the PDF attached, the send logged, the first view tracked.

    row = send_invoice(invoice, user, to=["ap@maple.ca"], subject="…", message="…")

- only a **posted** invoice that isn't void is sent (a draft has no number yet);
- the PDF (D-03a-T09) is rendered in the customer's language, stored in the organisation's
  object storage and attached to **one email per recipient** through the platform mail queue
  (A-07-T03) — so retries, the demo outbox, suppression of bounced addresses and the provider's
  bounce webhook all apply. A bounce flags the contact person's address (A-07-T08,
  ``ContactPerson.email_status``);
- the send is logged: an ``InvoiceEmail`` row (recipients, subject, message, PDF, email log
  rows, who sent it) and the audit event ``sales.invoice.sent``; an approved invoice becomes
  ``sent`` and keeps its first ``sent_at``;
- each email carries a **"View invoice" link** with a signed token (``view_token``); opening it
  (``mark_viewed``) records the first time on the email row and the invoice (``viewed_at``) and
  the audit event ``sales.invoice.viewed``, then shows the PDF. The token names the
  organisation, so the public view finds the invoice without anyone signed in.

``default_email(invoice)`` gives the composer's subject and message in the customer's language.
Everything runs in the caller's transaction: the emails leave only when it commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core import signing
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from numo9.documents.formatting import format_date, format_money

from .models import Invoice, InvoiceEmail, InvoiceStatus
from .posting import InvoiceRefused

KIND = "sales.invoice"
VIEW_SALT = "numo9.sales.invoice-view"  # noqa: S105 — a signing salt, not a secret
#: How long a "View invoice" link works.
TOKEN_MAX_AGE = 60 * 60 * 24 * 365
SENDABLE: frozenset[str] = frozenset(
    {
        InvoiceStatus.APPROVED,
        InvoiceStatus.SENT,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
    }
)


@dataclass(frozen=True)
class DefaultEmail:
    to: list[str]
    subject: str
    message: str
    language: str


def invoice_recipients(invoice: Any) -> list[str]:
    """The customer's people marked "include in emails" that have an address (primary first)."""
    people = invoice.contact.people.filter(include_in_emails=True, deleted_at__isnull=True)
    rows = people.exclude(email="").order_by("-is_primary", "pk").values_list("email", flat=True)
    return list(dict.fromkeys(rows))


def _locale(invoice: Invoice, language: str | None = None) -> str:
    return (language or invoice.contact.language or "en-ca").lower()


def _figures(invoice: Invoice, locale: str) -> dict[str, str]:
    return {
        "number": invoice.number,
        "contact": invoice.contact.legal_name,
        "amount_due": f"{format_money(invoice.amount_due, locale)} {invoice.currency}",
        "due_date": format_date(invoice.due_date, locale) if invoice.due_date else "",
        "organisation": invoice.organisation.name,
    }


def default_email(invoice: Invoice, language: str | None = None) -> DefaultEmail:
    """The composer's starting point: the recipients, a subject and a message."""
    locale = _locale(invoice, language)
    figures = _figures(invoice, locale)
    with translation.override(locale):
        subject = _("Invoice %(number)s from %(organisation)s") % figures
        message = (
            _(
                "Hello,\n\nHere is invoice %(number)s for %(amount_due)s, due %(due_date)s. "
                "The PDF is attached.\n\nThank you for your business."
            )
            % figures
        )
    return DefaultEmail(invoice_recipients(invoice), subject, message, locale)


def view_token(row: InvoiceEmail) -> str:
    return signing.dumps(
        {"o": str(row.organisation.public_id), "e": str(row.public_id)}, salt=VIEW_SALT
    )


def view_link(row: InvoiceEmail) -> str:
    return f"{settings.FRONTEND_URL}/api/v1/invoice-view/{view_token(row)}"


def pdf_file_name(invoice: Invoice) -> str:
    return f"invoice-{invoice.number or 'draft'}.pdf"


def send_invoice(
    invoice: Invoice,
    user: Any,
    *,
    to: list[str] | None = None,
    subject: str | None = None,
    message: str | None = None,
    language: str | None = None,
) -> InvoiceEmail:
    from numo9.audit.service import record
    from numo9.files.storage import new_key, put_bytes
    from numo9.notifications.mail import queue_email
    from numo9.notifications.templating import render_email

    from .pdf import render_invoice_pdf

    if invoice.status not in SENDABLE:
        raise InvoiceRefused(
            _("Only an approved invoice can be sent."),
            code="sales.invoice.not_sendable",
            params={"status": invoice.status},
        )
    defaults = default_email(invoice, language)
    recipients = [e.strip() for e in (to if to is not None else defaults.to) if e and e.strip()]
    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        raise InvoiceRefused(
            _("Add at least one email address to send the invoice to."),
            code="sales.invoice.no_recipient",
        )
    subject = " ".join((subject or defaults.subject).split())
    message = defaults.message if message is None else message.strip()
    organisation = invoice.organisation
    file_name = pdf_file_name(invoice)
    key = new_key(organisation, file_name)
    put_bytes(key, render_invoice_pdf(invoice), "application/pdf")
    user = user if getattr(user, "is_authenticated", False) else None
    row: InvoiceEmail = InvoiceEmail.objects.create(
        organisation=organisation,
        invoice=invoice,
        recipients=recipients,
        subject=subject,
        message=message,
        language=defaults.language,
        file_key=key,
        file_name=file_name,
        sent_by=user,
    )
    context = {**_figures(invoice, defaults.language), "message": message, "link": view_link(row)}
    email = render_email("invoice", context, language=defaults.language, organisation=organisation)
    attachment = {"key": key, "filename": file_name, "content_type": "application/pdf"}
    messages = [
        queue_email(
            address,
            subject,
            email.text,
            html=email.html,
            organisation=organisation,
            kind=KIND,
            language=email.language,
            attachments=[attachment],
            metadata={"invoice": str(invoice.public_id)},
        )
        for address in recipients
    ]
    row.email_messages = [str(m.public_id) for m in messages]
    row.save(update_fields=["email_messages"])
    now = timezone.now()
    fields = []
    if invoice.status == InvoiceStatus.APPROVED:
        invoice.status = InvoiceStatus.SENT
        fields.append("status")
    if invoice.sent_at is None:
        invoice.sent_at = now
        fields.append("sent_at")
    if fields:
        invoice.save(update_fields=[*fields, "updated_at"])
    record(
        "sales.invoice.sent",
        obj=invoice,
        meta={"number": invoice.number, "recipients": recipients, "email": str(row.public_id)},
        actor=user,
    )
    return row


def mark_viewed(token: str) -> InvoiceEmail | None:
    """Record the first view of an invoice from an email link; ``None`` for a bad token."""
    from numo9.audit.service import record
    from numo9.tenancy.context import org_context
    from numo9.tenancy.models import Organisation

    try:
        data = signing.loads(token, salt=VIEW_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    organisation = Organisation.objects.filter(public_id=data.get("o")).first()
    if organisation is None:
        return None
    with org_context(organisation):
        row: InvoiceEmail | None = (
            InvoiceEmail.objects.select_related("invoice", "invoice__contact")
            .filter(public_id=data.get("e"))
            .first()
        )
        if row is None or row.invoice.status == InvoiceStatus.VOID:
            return None
        now = timezone.now()
        if row.viewed_at is None:
            row.viewed_at = now
            row.save(update_fields=["viewed_at"])
        invoice = row.invoice
        if invoice.viewed_at is None:
            invoice.viewed_at = now
            invoice.save(update_fields=["viewed_at", "updated_at"])
            record(
                "sales.invoice.viewed",
                obj=invoice,
                meta={"number": invoice.number, "email": str(row.public_id)},
                actor=None,
            )
    return row
