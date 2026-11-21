"""U-08-T08 — Public API remaining counter (cached 30 s).

Acceptance: value = cap − allocated; anyone can read it (no session); cached 30 s on the server
and for browsers; an allocation shows at once on the server; "complete" when nothing is left;
the public pricing carries the same total/remaining.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import Client

from numo9.founding.models import FoundingCounter
from numo9.founding.public import CACHE_KEY
from numo9.founding.services import allocate_founding_slot
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
URL = "/api/v1/public/founding"


@pytest.fixture(autouse=True)
def _clear() -> None:
    cache.delete(CACHE_KEY)


def test_value_is_cap_minus_allocated() -> None:
    FoundingCounter.objects.filter(pk=1).update(allocated=427)
    response = Client().get(URL)
    assert response.status_code == 200
    assert response.json() == {"total": 1000, "allocated": 427, "remaining": 573, "complete": False}
    assert response["Cache-Control"] == "public, max-age=30"


def test_cached_on_the_server_and_cleared_by_an_allocation() -> None:
    assert Client().get(URL).json()["remaining"] == 1000
    FoundingCounter.objects.filter(pk=1).update(allocated=5)  # a change the cache doesn't see
    assert Client().get(URL).json()["remaining"] == 1000
    allocate_founding_slot(Organisation.objects.create(name="Maple Bakery Inc."))
    assert Client().get(URL).json()["remaining"] == 994


def test_offer_complete() -> None:
    FoundingCounter.objects.filter(pk=1).update(allocated=1000)
    assert Client().get(URL).json() == {
        "total": 1000,
        "allocated": 1000,
        "remaining": 0,
        "complete": True,
    }


def test_pricing_carries_the_counter() -> None:
    FoundingCounter.objects.filter(pk=1).update(allocated=10)
    offer = Client().get("/api/v1/public/pricing").json()["founding_offer"]
    assert (offer["total"], offer["remaining"]) == (1000, 990)
