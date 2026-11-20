"""A-09-T10 — performance budget: search p95 < 150 ms.

``seed_search`` fills one organisation's index (here 200,000 documents, to keep the suite fast;
the k6 benchmark ``tools/perf/k6/search.js`` runs the same queries over 1,000,000 —
``make perf-search``) and the owner runs the palette's kinds of query: names and prefixes, accents,
codes (exact and prefix), journal numbers, amounts, typos, words that match a large share of the
index and nothing at all. Every answer is a 200; the 95th percentile of the timed runs stays under
the budget. The typo tier is best effort: past its budget it is dropped, never the request.
"""

from __future__ import annotations

import time
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import OperationalError
from django.test import Client
from django.test.utils import override_settings

from numo9.accounts.models import User
from numo9.search import api
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
BUDGET_MS = 150
QUERIES = [
    "maple",
    "cedar roo",
    "érable",
    "erable renov",
    "MJ-0004242",
    "MJ-00042",
    "5400",
    "54",
    "1,130",
    "$2,500.00",
    "pinecrst",
    "rent",
    "year-end",
    "ma",
    "patel dental",
    "gatineau café",
    "invoice.pdf",
    "nguyen",
    "accrual",
    "zzzz",
]


@override_settings(DEBUG=True)
def test_search_p95_under_budget() -> None:
    call_command("seed_search", "--docs", "200000", stdout=StringIO())
    organisation = Organisation.objects.get(name="Search Seed Bakery Inc.")
    client = Client()
    client.force_login(User.objects.get(email="seed-search@numo9.test"))
    url = f"/api/v1/o/{organisation.public_id}/search"
    timings: list[float] = []
    for run in range(3):
        for query in QUERIES:
            started = time.perf_counter()
            response = client.get(url, {"q": query})
            elapsed = (time.perf_counter() - started) * 1000
            assert response.status_code == 200, query
            if run:  # the first round warms the caches
                timings.append(elapsed)
    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1]
    assert p95 < BUDGET_MS, (p95, timings[-5:])
    body = client.get(url, {"q": "MJ-0004242"}).json()
    assert body["records"][0]["code"] == "MJ-0004242"
    assert client.get(url, {"q": "pinecrst"}).json()["records"]  # typos still found


def test_typo_tier_over_budget_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    organisation = Organisation.objects.create(name="Pinecrest Roofing")

    def slow(queryset: object) -> list[object]:
        raise OperationalError("canceling statement due to statement timeout")

    with org_context(organisation):
        assert [d.title for _, _, d in api.ranked_documents("pinecrst")] == ["Pinecrest Roofing"]
        monkeypatch.setattr(api, "list", slow, raising=False)
        assert api.ranked_documents("pinecrst") == []  # dropped, no error
        assert [d.title for _, _, d in api.ranked_documents("pinecrest")] == ["Pinecrest Roofing"]
