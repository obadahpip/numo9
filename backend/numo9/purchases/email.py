"""Emailing a purchase order to the supplier (E-01-T09): the PDF attached, the send logged.

``send_purchase_order(order, user, to=…, subject=…, message=…)``:

- only an approved PO (it has its number) that isn't cancelled is sent;
- recipients default to the supplier's people marked "include in emails" (primary first);
- the PDF is rendered in the supplier's language, stored in the organisation's object storage and
  attached to one email per recipient through the platform mail queue (A-07-T03: retries, demo
  outbox, suppressed addresses; a bounce flags the contact person, A-07-T08);
- the PO keeps its first ``sent_at``; the send is audited ``purchases.purchaseorder.sent`` with
  the recipients and the email log rows.

``default_email(order)`` gives the subject and message in the supplier's language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils import timezone, translation
from django.utils.translation import gettext as _

from numo9.documents.formatting import format_date, format_money

from .approvals import PurchaseOrderRefused
from .models import NUMBERED_STATUSES, PurchaseOrder

KIND = "purchases.purchase_order"


@dataclass(frozen=True)
class DefaultEmail:
    to: list[str]
    subject: str
    message: str
    language: str


def supplier_recipients(order: PurchaseOrder) -> list[str]:
    people = order.contact.people.filter(include_in_emails=True, deleted_at__isnull=True)
    rows = people.exclude(email="").order_by("-is_primary", "pk").values_list("email", flat=True)
    return list(dict.fromkeys(rows))


def _figures(order: PurchaseOrder, locale: str) -> dict[str, str]:
    return {
        "number": order.number,
        "supplier": order.contact.display_name,
        "total": f"{format_money(order.total, locale)} {order.currency}",
        "delivery_date": format_date(order.delivery_date, locale) if order.delivery_date else "",
        "organisation": order.organisation.name,
    }


def default_email(order: PurchaseOrder) -> DefaultEmail:
    locale = (order.contact.language or "en-ca").lower()
    figures = _figures(order, locale)
    with translation.override(locale):
        subject = _("Purchase order %(number)s from %(organisation)s") % figures
        message = (
            _("Hello,\n\nPlease find purchase order %(number)s attached. Thank you.") % figures
        )
    return DefaultEmail(supplier_recipients(order), subject, message, locale)


def pdf_file_name(order: PurchaseOrder) -> str:
    return f"purchase-order-{order.number or 'draft'}.pdf"


def send_purchase_order(
    order: PurchaseOrder,
    user: Any,
    *,
    to: list[str] | None = None,
    subject: str | None = None,
    message: str | None = None,
) -> list[Any]:
    """Email the PO; returns the email log rows (one per recipient)."""
    from numo9.audit.service import record
    from numo9.files.storage import new_key, put_bytes
    from numo9.notifications.mail import queue_email
    from numo9.notifications.templating import render_email

    from .pdf import render_purchase_order_pdf

    if order.status not in NUMBERED_STATUSES or not order.number:
        raise PurchaseOrderRefused(
            _("Only an approved purchase order can be sent."),
            code="purchases.po.not_sendable",
            params={"status": order.status},
        )
    defaults = default_email(order)
    recipients = [e.strip() for e in (to if to is not None else defaults.to) if e and e.strip()]
    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        raise PurchaseOrderRefused(
            _("Add at least one email address to send the purchase order to."),
            code="purchases.po.no_recipient",
        )
    subject = " ".join((subject or defaults.subject).split())
    message = defaults.message if message is None else message.strip()
    organisation = order.organisation
    file_name = pdf_file_name(order)
    key = new_key(organisation, file_name)
    put_bytes(key, render_purchase_order_pdf(order), "application/pdf")
    context = {**_figures(order, defaults.language), "message": message}
    email = render_email(
        "purchase_order", context, language=defaults.language, organisation=organisation
    )
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
            metadata={"purchase_order": str(order.public_id)},
        )
        for address in recipients
    ]
    if order.sent_at is None:
        order.sent_at = timezone.now()
        order.save(update_fields=["sent_at", "updated_at"])
    person = user if getattr(user, "is_authenticated", False) else None
    record(
        "purchases.purchaseorder.sent",
        obj=order,
        meta={
            "number": order.number,
            "recipients": recipients,
            "emails": [str(m.public_id) for m in messages],
            "file_key": key,
        },
        actor=person,
    )
    return messages
