"""U-08-T02 — allocate_founding_slot(org): atomic UPDATE … WHERE allocated < cap RETURNING.

Acceptance: returns the slot, or None (offer complete, demo organisation, released slot); the
same organisation never takes two numbers; numbers run 1, 2, 3 … with no gaps.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from numo9.founding.models import FoundingCounter, FoundingSlot
from numo9.founding.services import allocate_founding_slot, founding_slot_of
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def _org(name: str, **extra: object) -> Organisation:
    return Organisation.objects.create(name=name, **extra)


def test_allocates_consecutive_numbers_and_counts_them() -> None:
    slots = [allocate_founding_slot(_org(f"Org {n}"), payment_ref=f"in_{n}") for n in range(3)]
    assert [s.slot_no for s in slots if s] == [1, 2, 3]
    assert slots[0] is not None and slots[0].payment_ref == "in_0"
    assert FoundingCounter.current().allocated == 3


def test_same_organisation_keeps_its_slot() -> None:
    maple = _org("Maple Bakery Inc.")
    first = allocate_founding_slot(maple)
    again = allocate_founding_slot(maple)
    assert first is not None and again is not None and again.pk == first.pk
    assert FoundingCounter.current().allocated == 1
    assert founding_slot_of(maple) == first


def test_returns_none_when_the_offer_is_complete() -> None:
    FoundingCounter.objects.filter(pk=1).update(cap=2)
    assert allocate_founding_slot(_org("A")) is not None
    assert allocate_founding_slot(_org("B")) is not None
    assert allocate_founding_slot(_org("C")) is None
    counter = FoundingCounter.current()
    assert (counter.allocated, counter.remaining) == (2, 0)
    assert FoundingSlot.objects.count() == 2


def test_demo_organisations_are_never_allocated() -> None:
    demo = _org("Demo Co", is_demo=True, demo_seed_version=1)
    assert allocate_founding_slot(demo) is None
    assert FoundingCounter.current().allocated == 0


def test_released_slot_is_not_replaced_by_a_new_number() -> None:
    birch = _org("Birch Ltd.")
    slot = allocate_founding_slot(birch)
    assert slot is not None
    FoundingSlot.objects.filter(pk=slot.pk).update(released_at=timezone.now(), release_reason="x")
    assert allocate_founding_slot(birch) is None
    assert founding_slot_of(birch) is None
    assert FoundingCounter.current().allocated == 1
