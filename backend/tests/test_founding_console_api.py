"""U-08-T11 (API part) — the founding admin panel: list slots, export, release with reason.

Acceptance: the export's row count = allocated; the list shows every slot with its state; release
needs a reason and ``platform.catalogue.manage`` (support may look, not release); a released slot
is audited with the reason and its number not reused; anyone else gets 404.
"""

from __future__ import annotations

import csv
import io

import pytest
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.founding.models import FoundingCounter, FoundingSlot
from numo9.founding.services import allocate_founding_slot
from numo9.tenancy.models import Organisation
from tests.test_platform_lists import staff
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
URL = "/api/v1/platform/founding"


@pytest.fixture
def slots() -> list[FoundingSlot]:
    made = []
    for name in ("Maple Bakery Inc.", "Birch Ltd.", "Pine Co."):
        slot = allocate_founding_slot(Organisation.objects.create(name=name), payment_ref="in_x")
        assert slot is not None
        made.append(slot)
    return made


def test_list_shows_counter_rules_and_every_slot(slots: list[FoundingSlot]) -> None:
    body = staff().get(URL).json()
    assert (body["cap"], body["allocated"], body["remaining"], body["active"]) == (1000, 3, 997, 3)
    assert body["churn_rule"] == "keep_if_returns_within_days"
    assert [s["slot_no"] for s in body["slots"]] == [1, 2, 3]
    assert body["slots"][0]["organisation_name"] == "Maple Bakery Inc."
    assert body["slots"][0]["state"] == "active"


def test_export_row_count_equals_allocated(slots: list[FoundingSlot]) -> None:
    owner = staff("platform_owner")
    owner.post(f"{URL}/slots/2/release", {"reason": "Duplicate account"}, "application/json")
    response = staff().get(f"{URL}/export")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.content.decode())))
    assert len(rows) == FoundingCounter.current().allocated == 3
    assert [r["state"] for r in rows] == ["active", "released", "active"]


def test_release_with_reason(slots: list[FoundingSlot]) -> None:
    owner = staff("platform_owner")
    bad = owner.post(f"{URL}/slots/1/release", {"reason": " no "}, "application/json")
    assert bad.status_code == 400
    response = owner.post(
        f"{URL}/slots/1/release", {"reason": "Fraudulent sign-up"}, "application/json"
    )
    assert response.status_code == 200
    assert response.json()["state"] == "released"
    event = AuditEvent._base_manager.get(action="founding.slot.released")
    assert event.meta == {"slot_no": 1, "reason": "admin", "note": "Fraudulent sign-up"}
    again = owner.post(f"{URL}/slots/1/release", {"reason": "Again please"}, "application/json")
    assert again.status_code == 400
    missing = owner.post(f"{URL}/slots/99/release", {"reason": "Nobody here"}, "application/json")
    assert missing.status_code == 404
    other = allocate_founding_slot(Organisation.objects.create(name="Late Ltd."))
    assert other is not None and other.slot_no == 4  # number 1 is never reused


def test_support_may_look_but_not_release(slots: list[FoundingSlot]) -> None:
    response = staff().post(f"{URL}/slots/1/release", {"reason": "Not allowed"}, "application/json")
    assert response.status_code == 403
    assert FoundingSlot.objects.get(slot_no=1).released_at is None


def test_nobody_else_sees_the_panel(slots: list[FoundingSlot]) -> None:
    browser = Client()
    browser.force_login(user("dana@maple.ca"))
    assert browser.get(URL).status_code in (403, 404)
    assert Client().get(URL).status_code in (401, 403)
