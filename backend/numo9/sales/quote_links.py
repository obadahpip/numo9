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

from decimal import Decimal
from typing import Any

from django.core import signing
from django.utils import timezone

from .models import Quote, QuoteAcceptance, QuoteLink

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

    from .quote_invoicing import deposit_due
    from .quotes import counted, is_expired

    with org_context(quote.organisation):
        lines = list(quote.lines.order_by("position", "pk"))
        flags = counted(lines)
        superseded = quote.revisions.filter(deleted_at__isnull=True).exists()
        evidence = QuoteAcceptance.objects.filter(quote=quote).first()
    accepted_by = evidence.typed_name if evidence is not None else None
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
        "discount_total": f"{quote.discount_total:.2f}",
        "tax_total": f"{quote.tax_total:.2f}",
        "total": f"{quote.total:.2f}",
        "deposit_type": quote.deposit_type,
        "deposit_value": f"{Decimal(quote.deposit_value).normalize():f}",
        "deposit": f"{deposit_due(quote):.2f}",
        "accepted_by": accepted_by,
        "can_accept": reason is None,
        "reason": reason,
    }


# ---- acceptance with evidence (D-02-T07) -------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n"
MAX_SIGNATURE = 512 * 1024


class AcceptanceRefused(Exception):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def accept_with_evidence(
    quote: Quote,
    *,
    typed_name: str,
    signature_png: bytes | None = None,
    selections: dict[str, bool] | None = None,
    ip: str | None = None,
    user_agent: str = "",
    now: Any = None,
) -> Any:
    """Accept ``quote`` as the customer, keeping the evidence (module docstring): the options
    chosen (``selections``: line id → selected, for optional and alternative lines) are applied
    and the totals recalculated, the PDF of the quote **as accepted** is rendered and stored
    with its SHA-256, the signature PNG stored, then the quote moves to Accepted (refused once
    expired). Accepting twice returns the first acceptance (idempotent)."""
    import hashlib

    from django.db import transaction
    from django.utils.translation import gettext as _

    from numo9.files.storage import new_key, put_bytes
    from numo9.tenancy.context import org_context

    from .pdf import render_quote_pdf
    from .quotes import accept, recalculate

    name = (typed_name or "").strip()
    if not name:
        raise AcceptanceRefused(
            _("Type your name to accept the quote."), "sales.quote.name_required"
        )
    if signature_png is not None and (
        not signature_png.startswith(PNG) or len(signature_png) > MAX_SIGNATURE
    ):
        raise AcceptanceRefused(
            _("The signature must be a PNG image."), "sales.quote.signature_invalid"
        )
    organisation = quote.organisation
    with org_context(organisation), transaction.atomic():
        locked = Quote._base_manager.select_for_update().get(pk=quote.pk)
        existing = QuoteAcceptance.objects.filter(quote=locked).first()
        if existing is not None:
            return existing
        chosen = {}
        for line in locked.lines.all():
            key = str(line.public_id)
            if selections and key in selections and (line.is_optional or line.alternative_group):
                line.selected = bool(selections[key])
                line.save(update_fields=["selected", "updated_at"])
            chosen[key] = line.selected
        recalculate(locked)
        accepted = accept(locked, now=now)  # the expiry and transition rules
        pdf = render_quote_pdf(accepted)
        pdf_key = new_key(organisation, f"{accepted.number}-accepted.pdf")
        put_bytes(pdf_key, pdf, "application/pdf")
        signature_key = ""
        if signature_png:
            signature_key = new_key(organisation, f"{accepted.number}-signature.png")
            put_bytes(signature_key, signature_png, "image/png")
        evidence = QuoteAcceptance(
            organisation=organisation,
            quote=accepted,
            typed_name=name[:200],
            signature_key=signature_key,
            ip=ip or None,
            user_agent=(user_agent or "")[:512],
            selections=chosen,
            pdf_key=pdf_key,
            pdf_sha256=hashlib.sha256(pdf).hexdigest(),
            accepted_at=accepted.accepted_at or timezone.now(),
        )
        evidence.save()
        return evidence
