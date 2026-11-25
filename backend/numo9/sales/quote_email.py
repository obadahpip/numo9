"""Quote emails (D-02-T15).

- ``send_quote(quote, user, to=…)`` — one email per recipient through the platform mail queue
  (A-07), the quote PDF attached, with the public link to view and accept it (D-02-T06, a new
  link per send); the quote moves to **Sent** (D-02-T04). Recipients default to the customer's
  people marked "include in emails"; the language is the customer's.
- ``notify_decision(quote)`` — once a quote is **accepted** or **declined**, one notification
  (``sales.quote.accepted`` / ``.declined``, in the app and by email per their preferences) to
  whoever sent it, else to the organisation's owners and admins. Called by the lifecycle hooks
  below — once per decision (accepting twice notifies once).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _

from .models import Quote

KIND = "sales.quote"
TEMPLATE = "quote"


def quote_link_url(token: str) -> str:
    return f"{settings.FRONTEND_URL}/q/{token}"


def send_quote(
    quote: Quote,
    user: Any,
    *,
    to: list[str] | None = None,
    message: str = "",
) -> list[Any]:
    from numo9.files.storage import new_key, put_bytes
    from numo9.notifications.mail import queue_email
    from numo9.notifications.templating import render_email
    from numo9.tenancy.context import org_context

    from .email import invoice_recipients
    from .pdf import render_quote_pdf
    from .quote_links import issue_link
    from .quotes import QuoteRefused, send

    contact = quote.contact
    with org_context(quote.organisation):
        defaults = invoice_recipients(quote)  # the customer's people "included in emails"
    recipients = [e.strip() for e in (to if to is not None else defaults) if e and e.strip()]
    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        raise QuoteRefused(
            _("Add at least one email address to send the quote to."),
            code="sales.quote.no_recipient",
        )
    organisation = quote.organisation
    with org_context(organisation):
        sent = send(quote, user)
        _link, token = issue_link(sent, user)
        file_name = f"{sent.number}.pdf"
        key = new_key(organisation, file_name)
        put_bytes(key, render_quote_pdf(sent), "application/pdf")
        language = contact.language or "en-ca"
        context = {
            "number": sent.number,
            "title": sent.title,
            "total": f"${sent.total:,.2f}",
            "expiry_date": sent.expiry_date.isoformat(),
            "message": message,
            "link": quote_link_url(token),
        }
        email = render_email(TEMPLATE, context, language=language, organisation=organisation)
        attachment = {"key": key, "filename": file_name, "content_type": "application/pdf"}
        return [
            queue_email(
                address,
                email.subject,
                email.text,
                html=email.html,
                organisation=organisation,
                kind=KIND,
                language=email.language,
                attachments=[attachment],
                metadata={"quote": str(sent.public_id)},
            )
            for address in recipients
        ]


def _recipients(quote: Quote) -> list[Any]:
    from numo9.audit.models import AuditEvent
    from numo9.tenancy.models import OrganisationMember

    sender = (
        AuditEvent.objects.filter(action="sales.quote.sent", object_id=str(quote.public_id))
        .exclude(actor_user__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if sender is not None and sender.actor_user is not None:
        return [sender.actor_user]
    return [
        m.user
        for m in OrganisationMember.objects.filter(
            organisation=quote.organisation, role__in=("owner", "admin")
        ).select_related("user")
    ]


def notify_decision(quote: Quote) -> None:
    from numo9.notifications.services import notify
    from numo9.tenancy.context import org_context

    event = f"sales.quote.{quote.status}"
    with org_context(quote.organisation):
        recipients = _recipients(quote)
    notify(
        event,
        recipients,
        organisation=quote.organisation,
        params={
            "number": quote.number,
            "customer": quote.contact.display_name,
            "total": f"${quote.total:,.2f}",
            "reason": quote.decline_reason or _("no reason given"),
        },
        link=f"/o/{quote.organisation.public_id}/sales/quotes/{quote.public_id}",
    )
