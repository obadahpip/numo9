"""Quotes (D-02): creation with its number (T02), totals of the selected lines (T03), the
lifecycle (T04), expiry (T05). See each function."""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from numo9.ledger.models import LedgerError
from numo9.orgsettings.models import DocType
from numo9.orgsettings.numbering import allocate_number
from numo9.tenancy.context import org_context

from .models import Quote, QuoteStatus


def create_quote(organisation: Any, *, number: str = "", **fields: Any) -> Quote:
    """A draft quote numbered ``QU-0001`` from the organisation's quote sequence (D-02-T02), in
    one transaction with the insert: a quote that fails to save gives its number back, and two
    creates at once wait for each other on the sequence row (unique numbers)."""
    with org_context(organisation), transaction.atomic():
        item = Quote(
            organisation=organisation,
            number=number or allocate_number(DocType.QUOTE, organisation),
            **fields,
        )
        item.save()
        return item


def counted(lines: list[Any]) -> list[bool]:
    """Which lines count in the totals (D-02-T03), in the order given: a plain line always; an
    optional line when the customer selected it; of an alternative group, the **first selected**
    line by position (none selected: the group adds nothing)."""
    chosen: set[str] = set()
    out = []
    for line in sorted(lines, key=lambda item: (item.position, item.pk or 0)):
        if line.alternative_group:
            take = bool(line.selected) and line.alternative_group not in chosen
            if take:
                chosen.add(line.alternative_group)
        elif line.is_optional:
            take = bool(line.selected)
        else:
            take = True
        out.append((line, take))
    order = {id(line): take for line, take in out}
    return [order[id(line)] for line in lines]


def _preview_line(line: Any) -> Any:
    from numo9.documents.posting import PreviewLine

    return PreviewLine(
        account=line.account,
        quantity=line.quantity,
        unit_price=line.unit_price,
        discount_type=line.discount_type,
        discount_value=line.discount_value,
        tax_code=line.tax_code,
        description=line.description,
    )


def recalculate(quote: Quote) -> Quote:
    """The calculator's figures on the quote and its lines (server-authoritative): every line
    gets its own amounts, but the **totals** (and the document discount) cover only the lines
    that count (``counted``) — ticking an optional line or choosing another alternative changes
    the total (D-02-T03)."""
    from numo9.documents.posting import result_for

    with org_context(quote.organisation), transaction.atomic():
        lines = list(quote.lines.select_related("account", "tax_code").order_by("position", "pk"))
        flags = counted(lines)
        included = [line for line, take in zip(lines, flags, strict=True) if take]
        excluded = [line for line, take in zip(lines, flags, strict=True) if not take]
        result = result_for(
            "quote",
            [_preview_line(line) for line in included],
            tax_mode=quote.tax_mode,
            discount_type=quote.discount_type,
            discount_value=quote.discount_value,
        )
        alone = result_for(
            "quote",
            [_preview_line(line) for line in excluded],
            tax_mode=quote.tax_mode,
        )
        figures = list(zip(included, result.lines, strict=True)) + list(
            zip(excluded, alone.lines, strict=True)
        )
        for line, row in figures:
            line.net, line.tax_amount, line.amount = row.exclusive, row.tax, row.net
            line.save(update_fields=["net", "tax_amount", "amount", "updated_at"])
        quote.subtotal = result.subtotal
        quote.discount_total = result.discount_total
        quote.tax_total = result.tax_total
        quote.total = result.total
        quote.save(update_fields=["subtotal", "discount_total", "tax_total", "total", "updated_at"])
        return quote


# ---- lifecycle (T04) ---------------------------------------------------------------------------

#: The transitions: action → (statuses it may start from, status it leads to).
TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "send": (frozenset({"draft", "sent", "viewed"}), "sent"),
    "view": (frozenset({"sent", "viewed"}), "viewed"),
    "accept": (frozenset({"sent", "viewed"}), "accepted"),
    "decline": (frozenset({"sent", "viewed"}), "declined"),
    "expire": (frozenset({"sent", "viewed"}), "expired"),
    "invoice": (frozenset({"accepted"}), "invoiced"),
}


class QuoteRefused(LedgerError):
    """A quote action the rules refuse (``code`` names the rule)."""


def local_today(organisation: Any, now: dt.datetime | None = None) -> dt.date:
    from numo9.contacts.models import organisation_today

    today: dt.date = organisation_today(organisation, now=now or timezone.now())
    return today


def is_expired(quote: Quote, now: dt.datetime | None = None) -> bool:
    """Past its expiry date in the organisation's time zone: accepting at 23:59 local on the
    expiry day is in time, at 00:00 the next day it isn't (D-02-T05)."""
    return local_today(quote.organisation, now) > quote.expiry_date


def _transition(
    quote: Quote,
    action: str,
    *,
    user: Any = None,
    now: dt.datetime | None = None,
    **fields: Any,
) -> Quote:
    from numo9.audit import service as audit

    sources, target = TRANSITIONS[action]
    moment = now or timezone.now()
    with org_context(quote.organisation), transaction.atomic():
        locked = Quote._base_manager.select_for_update().get(pk=quote.pk)
        if action == "accept" and locked.status == "accepted":
            return locked  # accepting twice: the first acceptance stands (idempotent)
        if action == "view" and locked.status not in sources:
            return locked  # opened after a decision: nothing to track
        if locked.status not in sources:
            raise QuoteRefused(
                _("%(quote)s is %(status)s: it can't be %(action)s.")
                % {
                    "quote": locked.number,
                    "status": str(QuoteStatus(locked.status).label).lower(),
                    "action": str(ACTION_LABELS[action]),
                },
                code="sales.quote.transition",
            )
        if action == "accept" and is_expired(locked, moment):
            raise QuoteRefused(
                _("This quote expired on %(date)s: ask for a new quote.")
                % {"date": locked.expiry_date.isoformat()},
                code="sales.quote.expired",
            )
        if action == "send" and not locked.lines.exists():
            raise QuoteRefused(
                _("Add at least one line before sending the quote."), code="sales.quote.empty"
            )
        previous = locked.status
        locked.status = target
        stamp = {
            "send": "sent_at",
            "accept": "accepted_at",
            "decline": "declined_at",
            "expire": "expired_at",
            "invoice": "invoiced_at",
        }.get(action)
        if stamp:
            setattr(locked, stamp, moment)
        if action == "view" and locked.viewed_at is None:
            locked.viewed_at = moment
        for name, value in fields.items():
            setattr(locked, name, value)
        locked.save()
        if previous != target:
            audit.record(
                f"sales.quote.{target}",
                obj=locked,
                changes={"status": [previous, target]},
                meta={"number": locked.number, "total": f"{locked.total:.2f}"},
                actor=user if getattr(user, "is_authenticated", False) else None,
            )
            if target in ("accepted", "declined"):  # one notification per decision (T15)
                from .quote_email import notify_decision

                transaction.on_commit(lambda: notify_decision(locked))
        return locked


ACTION_LABELS = {
    "send": _lazy("sent"),
    "view": _lazy("viewed"),
    "accept": _lazy("accepted"),
    "decline": _lazy("declined"),
    "expire": _lazy("expired"),
    "invoice": _lazy("invoiced"),
}


def send(quote: Quote, user: Any = None, *, now: dt.datetime | None = None) -> Quote:
    return _transition(quote, "send", user=user, now=now)


def mark_viewed(quote: Quote, *, now: dt.datetime | None = None) -> Quote:
    return _transition(quote, "view", now=now)


def accept(quote: Quote, *, now: dt.datetime | None = None, user: Any = None) -> Quote:
    return _transition(quote, "accept", user=user, now=now)


def decline(quote: Quote, reason: str = "", *, now: dt.datetime | None = None) -> Quote:
    return _transition(quote, "decline", now=now, decline_reason=(reason or "").strip()[:2000])


def expire(quote: Quote, *, now: dt.datetime | None = None) -> Quote:
    return _transition(quote, "expire", now=now)


def mark_invoiced(quote: Quote, invoice: Any, user: Any = None) -> Quote:
    return _transition(quote, "invoice", user=user, invoice=invoice)


# ---- expiry job (T05) --------------------------------------------------------------------------


def expire_due(now: dt.datetime | None = None) -> int:
    """Every organisation's sent or viewed quotes past their expiry date **in the
    organisation's time zone** become Expired — a quote expiring today stays acceptable until
    local midnight (the hourly job catches each organisation's midnight). Returns how many."""
    from numo9.tenancy.models import Organisation

    moment = now or timezone.now()
    done = 0
    for organisation in Organisation.objects.order_by("pk").iterator():
        today = local_today(organisation, moment)
        with org_context(organisation):
            due = Quote.objects.filter(
                status__in=("sent", "viewed"), expiry_date__lt=today
            ).order_by("pk")
            for item in due:
                expire(item, now=moment)
                done += 1
    return done
