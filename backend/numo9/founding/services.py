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

from django.db import IntegrityError, connection, transaction

from numo9.tenancy.models import Organisation

from .models import FoundingCounter, FoundingSlot

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
        return existing if existing.released_at is None else None
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
