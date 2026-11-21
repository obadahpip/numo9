"""U-08-T09 (API part) — the organisation profile (settings) carries the founding number.

Acceptance: ``founding_slot`` is the slot number while the organisation holds one, null otherwise
(none, or released); it is read-only.
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.founding.models import FoundingSlot
from numo9.founding.services import allocate_founding_slot
from numo9.tenancy.models import Organisation, OrganisationMember

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def browser(org: Organisation) -> Client:
    user = User.objects.create_user("owner@refined.ca", password="x" * 12, name="Sam")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    client = Client()
    client.force_login(user)
    return client


def test_founding_number_on_the_profile(org: Organisation) -> None:
    client = browser(org)
    url = f"/api/v1/o/{org.public_id}/settings"
    assert client.get(url).json()["founding_slot"] is None
    FoundingSlot.objects.create(organisation=Organisation.objects.create(name="x"), slot_no=426)
    from numo9.founding.models import FoundingCounter

    FoundingCounter.objects.filter(pk=1).update(allocated=426)
    slot = allocate_founding_slot(org)
    assert slot is not None and slot.slot_no == 427
    assert client.get(url).json()["founding_slot"] == 427
    response = client.patch(url, {"founding_slot": 1}, content_type="application/json")
    assert response.status_code == 200 and response.json()["founding_slot"] == 427
    FoundingSlot.objects.filter(pk=slot.pk).update(released_at=timezone.now())
    assert client.get(url).json()["founding_slot"] is None
