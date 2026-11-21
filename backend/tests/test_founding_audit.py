"""U-08-T10 — Audit entries for each allocation and release.

Acceptance: the audit lists every slot — one ``founding.slot.allocated`` per slot (number and
first payment), none for a replay or a refused allocation; one ``founding.slot.released`` per
release with its reason (and the manual note); in the organisation's own log.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.audit.presenter import action_label
from numo9.founding.models import FoundingCounter
from numo9.founding.services import allocate_founding_slot, on_refund, release_slot
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def events(action: str) -> list[AuditEvent]:
    return list(AuditEvent._base_manager.filter(action=action).order_by("id"))


def test_every_allocation_is_audited_once() -> None:
    orgs = [Organisation.objects.create(name=f"Org {n}") for n in range(3)]
    for n, org in enumerate(orgs):
        allocate_founding_slot(org, payment_ref=f"in_{n}")
    allocate_founding_slot(orgs[0])  # replay: no second entry
    FoundingCounter.objects.filter(pk=1).update(cap=3)
    allocate_founding_slot(Organisation.objects.create(name="Late"))  # refused: none
    rows = events("founding.slot.allocated")
    assert [(r.organisation_id, r.meta["slot_no"]) for r in rows] == [
        (org.pk, n + 1) for n, org in enumerate(orgs)
    ]
    assert rows[0].meta["payment_ref"] == "in_0"
    assert rows[0].object_label == "Founding organisation #0001"
    assert action_label("founding.slot.allocated") == "Founding place given"


def test_every_release_is_audited_with_its_reason() -> None:
    maple = Organisation.objects.create(name="Maple Bakery Inc.")
    slot = allocate_founding_slot(maple, payment_ref="in_1")
    assert slot is not None
    on_refund(maple, "in_1", timezone.now())
    birch = Organisation.objects.create(name="Birch Ltd.")
    other = allocate_founding_slot(birch)
    assert other is not None
    release_slot(other, "admin", note="Duplicate account of Maple")
    release_slot(other, "admin")  # already released: no second entry
    rows = events("founding.slot.released")
    assert [(r.organisation_id, r.meta["reason"]) for r in rows] == [
        (maple.pk, "refunded"),
        (birch.pk, "admin"),
    ]
    assert rows[1].meta["note"] == "Duplicate account of Maple"
    assert action_label("founding.slot.released") == "Founding place released"
