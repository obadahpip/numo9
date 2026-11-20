"""U-08-T01 — FoundingCounter (single row, cap, allocated) and FoundingSlot.

Acceptance: unique constraints on organisation and slot_no; the counter is one row (id 1) with
cap 1,000 and allocated 0 after migration, never past its cap; slot numbers start at 1.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.founding.models import FoundingCounter, FoundingSlot
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def test_counter_is_one_row_seeded_by_the_migration() -> None:
    counter = FoundingCounter.current()
    assert (counter.pk, counter.cap, counter.allocated, counter.remaining) == (1, 1000, 0, 1000)
    assert str(counter) == "0 of 1000"
    with pytest.raises(IntegrityError), transaction.atomic():
        FoundingCounter.objects.create(id=2)


def test_counter_never_past_its_cap() -> None:
    FoundingCounter.objects.filter(pk=1).update(cap=2, allocated=2)
    with pytest.raises(IntegrityError), transaction.atomic():
        FoundingCounter.objects.filter(pk=1).update(allocated=3)


def test_one_slot_per_organisation_and_each_number_once() -> None:
    maple = Organisation.objects.create(name="Maple Bakery Inc.")
    birch = Organisation.objects.create(name="Birch Ltd.")
    slot = FoundingSlot.objects.create(organisation=maple, slot_no=427)
    assert str(slot) == "Founding organisation #0427"
    with pytest.raises(IntegrityError), transaction.atomic():
        FoundingSlot.objects.create(organisation=maple, slot_no=428)  # replayed webhook
    with pytest.raises(IntegrityError), transaction.atomic():
        FoundingSlot.objects.create(organisation=birch, slot_no=427)
    with pytest.raises(IntegrityError), transaction.atomic():
        FoundingSlot.objects.create(organisation=birch, slot_no=0)
