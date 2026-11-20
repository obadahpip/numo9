"""Founding offer services (U-08).

``allocate_founding_slot(org)`` (U-08-T02) hands the organisation the next founding slot with one
statement on the single counter row::

    UPDATE founding_foundingcounter SET allocated = allocated + 1, updated_at = now()
     WHERE id = 1 AND allocated < cap RETURNING allocated

Postgres locks the row for the statement and re-checks ``allocated < cap`` after a concurrent
update commits, so two transactions can never take the same number and the counter can never
pass its cap. The returned value is the slot number. The statement and the ``FoundingSlot``
insert run in one savepoint: when the insert fails because the organisation already holds a slot
(a replayed webhook racing the first one), the increment is rolled back with it and the
organisation's existing slot is returned — a number is never consumed without a slot.

The organisation's subscriptions are flagged ``founding`` with the slot (U-08-T05).

Callers run it inside the transaction that records the first payment (U-08-T03), so a payment
rolled back takes its slot with it.
"""

from __future__ import annotations

import datetime as dt

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from numo9.tenancy.models import Organisation

from .models import ChurnRule, FoundingCounter, FoundingSlot

_ALLOCATE_SQL = (
    f"UPDATE {FoundingCounter._meta.db_table} "  # noqa: S608 — table name from the model, no input
    "SET allocated = allocated + 1, updated_at = now() "
    "WHERE id = 1 AND allocated < cap RETURNING allocated"
)


def eligible(organisation: Organisation) -> bool:
    """Demo organisations never hold a founding slot."""
    return not organisation.is_demo


def allocate_founding_slot(
    organisation: Organisation, payment_ref: str = ""
) -> FoundingSlot | None:
    """The organisation's founding slot: the one it holds, a new one, or ``None``.

    ``None`` when the offer is complete (``allocated = cap``), the organisation is a demo, or its
    slot was released (a released organisation does not take a second number; the churn rules,
    U-08-T06, decide whether it gets its own back).
    """
    if not eligible(organisation):
        return None
    existing = FoundingSlot.objects.filter(organisation=organisation).first()
    if existing is not None:
        if existing.released_at is not None:
            return None
        sync_founding_flag(organisation)  # e.g. a returning organisation's new subscription
        return existing
    FoundingCounter.current()  # the migration seeds the row; recreate it if it was ever removed
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(_ALLOCATE_SQL)
                row = cursor.fetchone()
            if row is None:
                return None  # offer complete
            slot = FoundingSlot.objects.create(
                organisation=organisation, slot_no=int(row[0]), payment_ref=payment_ref[:255]
            )
            sync_founding_flag(organisation)
            from .public import clear_cache

            clear_cache()
            return slot
    except IntegrityError:
        # A concurrent transaction gave this organisation its slot first; our increment is undone.
        held = FoundingSlot.objects.filter(organisation=organisation).first()
        return held if held is not None and held.released_at is None else None


def sync_founding_flag(organisation: Organisation) -> bool:
    """Entitlement (U-08-T05): the organisation's subscriptions carry ``founding`` exactly while it
    holds an active slot. The engine gives a founding subscription every active product — those
    that ship later included — whatever its package. Returns the flag."""
    from numo9.entitlements.cache import bump_organisation
    from numo9.entitlements.models import Subscription

    founding = founding_slot_of(organisation) is not None
    changed = (
        Subscription._base_manager.filter(organisation_id=organisation.pk, deleted_at__isnull=True)
        .exclude(founding=founding)
        .update(founding=founding)
    )
    if changed:
        bump_organisation(str(organisation.public_id))
    return founding


def founding_slot_of(organisation: Organisation) -> FoundingSlot | None:
    """The organisation's active (not released) founding slot."""
    return FoundingSlot.objects.filter(organisation=organisation, released_at__isnull=True).first()


# ---- churn rules (U-08-T06) --------------------------------------------------------------------


class ReleaseReason:
    CANCELLED = "cancelled"
    NOT_RETURNED_IN_TIME = "not_returned_in_time"
    REFUNDED = "refunded"
    ADMIN = "admin"


def release_slot(slot: FoundingSlot, reason: str, at: dt.datetime | None = None) -> FoundingSlot:
    """Release the slot (its number is never handed out again) and drop the founding flag."""
    if slot.released_at is not None:
        return slot
    slot.released_at = at or timezone.now()
    slot.release_reason = reason[:64]
    slot.save(update_fields=["released_at", "release_reason"])
    sync_founding_flag(slot.organisation)
    return slot


def on_cancel(organisation: Organisation, at: dt.datetime) -> FoundingSlot | None:
    """The organisation's subscription was cancelled: apply the configured churn rule."""
    slot = founding_slot_of(organisation)
    if slot is None:
        return None
    rule = FoundingCounter.current().churn_rule
    if rule == ChurnRule.LOSE_ON_CANCEL:
        return release_slot(slot, ReleaseReason.CANCELLED, at)
    if slot.lapsed_at is None:
        slot.lapsed_at = at
        slot.save(update_fields=["lapsed_at"])
    return slot


def on_return(organisation: Organisation, at: dt.datetime) -> FoundingSlot | None:
    """A cancelled organisation is active again: keep its slot, or release it when it came back
    after the return window (``keep_if_returns_within_days``)."""
    slot = founding_slot_of(organisation)
    if slot is None:
        return None
    if slot.lapsed_at is not None:
        counter = FoundingCounter.current()
        late = at - slot.lapsed_at > dt.timedelta(days=counter.return_window_days)
        if counter.churn_rule == ChurnRule.KEEP_IF_RETURNS_WITHIN_DAYS and late:
            return release_slot(slot, ReleaseReason.NOT_RETURNED_IN_TIME, at)
        slot.lapsed_at = None
        slot.save(update_fields=["lapsed_at"])
    sync_founding_flag(organisation)  # a new subscription row gets the flag too
    return slot


def on_refund(organisation: Organisation, payment_ref: str, at: dt.datetime) -> FoundingSlot | None:
    """The first payment was refunded: release the slot when within the release window."""
    slot = founding_slot_of(organisation)
    hours = FoundingCounter.current().refund_release_hours
    if slot is None or not hours or not payment_ref or slot.payment_ref != payment_ref:
        return slot
    if at - slot.allocated_at <= dt.timedelta(hours=hours):
        return release_slot(slot, ReleaseReason.REFUNDED, at)
    return slot
