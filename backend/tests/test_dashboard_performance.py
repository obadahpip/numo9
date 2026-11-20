"""V-04-T10 — performance budget: the practice home < 1.5 s on 2,000 organisations.

The seeded practice (``seed_practice --orgs 2000``: 2,000 clients, 5 accountants with assignments
and group-free scopes) answers ``GET /api/v1/practice/dashboard`` for the practice admin (whole
practice) and an accountant (their own organisations) — the slowest of three runs each stays under
the budget, every widget ``ok``. The load test is ``tools/perf/k6/practice-dashboard.js``
(``make perf-dashboard``: p95 < 1.5 s with 20 users).
"""

from __future__ import annotations

import time
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.tenancy.models import Practice, PracticeMember, PracticeRole

pytestmark = pytest.mark.django_db
BUDGET_SECONDS = 1.5


def test_dashboard_under_budget_on_2000_organisations() -> None:
    call_command("seed_practice", "--orgs", "2000", "--force", stdout=StringIO())
    practice = Practice.objects.get(name="Seed Practice")
    admin = User.objects.get(email="seed-admin@numo9.test")
    accountant = (
        PracticeMember.objects.filter(practice=practice, role=PracticeRole.ACCOUNTANT)
        .select_related("user")
        .first()
    )
    assert accountant is not None
    for person, scope in ((admin, "all"), (accountant.user, "mine")):
        client = Client()
        client.force_login(person)
        timings = []
        for _ in range(3):
            started = time.perf_counter()
            response = client.get(
                "/api/v1/practice/dashboard", {"practice": str(practice.public_id), "scope": scope}
            )
            timings.append(time.perf_counter() - started)
            assert response.status_code == 200
            assert all(w["status"] == "ok" for w in response.json()["widgets"])
        assert max(timings) < BUDGET_SECONDS, (scope, timings)
    widgets = {w["key"]: w for w in response.json()["widgets"]}
    assert widgets["workload"]["count"] >= 1
