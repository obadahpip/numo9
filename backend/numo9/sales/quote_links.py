"""Public quote links (D-02-T06): ``/api/v1/q/<token>`` opens a quote without signing in.

- ``issue_link(quote, user)`` — a ``QuoteLink`` row and its URL token: ``signing.dumps`` of the
  quote's and the link's public ids (salted; the signature is the credential, a tampered token
  is unknown). ``revoke_link(link)`` — the link answers **410 Gone** from then on.
- ``open_link(token)`` — the quote of a valid link: counts the view (``views``,
  ``last_viewed_at``) and moves a sent quote to **Viewed** (D-02-T04 ``mark_viewed``); ``None``
  for an unknown or tampered token, ``LinkRevoked`` for a revoked one.
- ``public_quote(quote)`` — what the public page shows: the organisation, the customer, the
  lines (optional ones and alternatives with their selection), the totals, the status and
  whether it can be accepted now (``can_accept``, ``reason``: expired, declined, accepted,
  invoiced, superseded by a revision).
"""

from __future__ import annotations

from typing import Any

from django.core import signing
from django.utils import timezone

from .models import Quote, QuoteLink

SALT = "numo9.sales.quote-link"  # noqa: S105 — a signing salt, not a secret


class LinkRevoked(Exception):
    """The link was revoked: 410 Gone."""


def link_token(link: QuoteLink) -> str:
    return signing.dumps({"q": str(link.quote.public_id), "l": str(link.public_id)}, salt=SALT)


def issue_link(quote: Quote, user: Any = None) -> tuple[QuoteLink, str]:
    from numo9.tenancy.context import org_context

    with org_context(quote.organisation):
        link = QuoteLink(
            organisation=quote.organisation,
            quote=quote,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        link.save()
    return link, link_token(link)


def revoke_link(link: QuoteLink) -> QuoteLink:
    QuoteLink._base_manager.filter(pk=link.pk, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    link.refresh_from_db()
    return link


def find_link(token: str) -> QuoteLink | None:
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
    link: QuoteLink | None = (
        QuoteLink._base_manager.select_related("quote", "quote__organisation")
        .filter(public_id=data.get("l"), quote__public_id=data.get("q"))
        .first()
    )
    return link


def open_link(token: str) -> Quote | None:
    from django.db.models import F

    from numo9.tenancy.context import org_context

    from .quotes import mark_viewed

    link = find_link(token)
    if link is None:
        return None
    if link.revoked_at is not None:
        raise LinkRevoked
    QuoteLink._base_manager.filter(pk=link.pk).update(
        views=F("views") + 1, last_viewed_at=timezone.now()
    )
    with org_context(link.quote.organisation):
        return mark_viewed(link.quote)


def public_quote(quote: Quote) -> dict[str, Any]:
    from numo9.tenancy.context import org_context

    from .quotes import counted, is_expired

    with org_context(quote.organisation):
        lines = list(quote.lines.order_by("position", "pk"))
        flags = counted(lines)
        superseded = quote.revisions.exists()
    reason = None
    if superseded:
        reason = "superseded"
    elif quote.status in ("accepted", "declined", "expired", "invoiced"):
        reason = quote.status
    elif quote.status in ("sent", "viewed") and is_expired(quote):
        reason = "expired"
    elif quote.status not in ("sent", "viewed"):
        reason = "not_sent"
    return {
        "number": quote.number,
        "title": quote.title,
        "summary": quote.summary,
        "organisation": quote.organisation.name,
        "customer": quote.contact.display_name,
        "date": quote.date.isoformat(),
        "expiry_date": quote.expiry_date.isoformat(),
        "currency": quote.currency,
        "status": quote.status,
        "lines": [
            {
                "id": str(line.public_id),
                "description": line.description,
                "quantity": f"{line.quantity.normalize():f}",
                "unit_price": f"{line.unit_price:.2f}",
                "amount": f"{line.amount:.2f}",
                "tax": f"{line.tax_amount:.2f}",
                "is_optional": line.is_optional,
                "alternative_group": line.alternative_group,
                "selected": line.selected,
                "counted": take,
            }
            for line, take in zip(lines, flags, strict=True)
        ],
        "subtotal": f"{quote.subtotal:.2f}",
        "tax_total": f"{quote.tax_total:.2f}",
        "total": f"{quote.total:.2f}",
        "can_accept": reason is None,
        "reason": reason,
    }
