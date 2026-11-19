"""Contact activity timeline: the emitter modules call and the reader (B-02-T02).

``emit(contact, type, title, ref=…, amount=…, occurred_at=…, actor=…)`` records one event;
``timeline(contact, types=…, start=…, end=…)`` returns them newest first. Phase 0 emits
statements sent (``statement_sent`` signal, B-02-T06) and notes; Phase 1 documents and payments
call ``emit`` from their posting code. A merged contact's events move to the survivor.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from .models import ActivityEvent, ActivityType, Contact


def _actor_label(actor: Any) -> str:
    if actor is None or not getattr(actor, "is_authenticated", False):
        return ""
    name = getattr(actor, "name", "") or ""
    return f"{name} ({actor.email})" if name else str(getattr(actor, "email", ""))


def emit(
    contact: Contact,
    type: str,  # noqa: A002 — the event's type, as the model names it
    title: str,
    *,
    ref: Any = None,
    ref_type: str = "",
    ref_id: str = "",
    amount: Decimal | None = None,
    currency: str = "",
    occurred_at: dt.datetime | None = None,
    actor: Any = None,
    meta: dict[str, Any] | None = None,
) -> ActivityEvent:
    if type not in ActivityType.values:
        raise ValueError(f"Unknown activity type {type!r}.")
    if ref is not None:
        ref_type = ref_type or ref._meta.label
        ref_id = ref_id or str(getattr(ref, "public_id", ref.pk))
    event = ActivityEvent(
        organisation_id=contact.organisation_id,
        contact=contact,
        type=type,
        title=title[:300],
        ref_type=ref_type,
        ref_id=ref_id,
        amount=amount,
        currency=currency or (contact.currency if amount is not None else ""),
        occurred_at=occurred_at or timezone.now(),
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_label=_actor_label(actor),
        meta=meta or {},
    )
    event.save()
    return event


def timeline(
    contact: Contact,
    *,
    types: Iterable[str] | None = None,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> QuerySet[ActivityEvent]:
    events = ActivityEvent.objects.filter(contact=contact, deleted_at__isnull=True)
    if types:
        events = events.filter(type__in=list(types))
    if start:
        events = events.filter(occurred_at__date__gte=start)
    if end:
        events = events.filter(occurred_at__date__lte=end)
    return events.order_by("-occurred_at", "-id")


def _statement_sent(sender: Any, send: Any, **kwargs: Any) -> None:
    from django.utils.translation import gettext as _

    kind = _("Activity statement") if send.kind == "activity" else _("Statement")
    emit(
        send.contact,
        ActivityType.STATEMENT,
        _("%(kind)s as at %(date)s sent to %(to)s")
        % {"kind": kind, "date": send.as_at.isoformat(), "to": ", ".join(send.recipients)},
        ref=send,
        amount=send.amount_due,
        currency=send.currency,
        actor=send.sent_by,
    )


def connect() -> None:
    from .statements import statement_sent

    statement_sent.connect(_statement_sent, dispatch_uid="contacts_activity_statement_sent")
