"""V-04-T07 — drill-down: each widget returns directory filter params.

Acceptance: the drill list count = the widget count — for every count widget, the directory
called with the widget's filters lists exactly as many organisations, for the whole practice and
for "my organisations", for an admin and for an accountant; the new directory filters
(trial_ending, bn_missing, lock_missing, mine) are offered as facets and refuse bad values.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from tests.dashboard_helpers import Firm, build_firm

pytestmark = pytest.mark.django_db
DASHBOARD = "/api/v1/practice/dashboard"
DIRECTORY = "/api/v1/practice/orgs"


@pytest.fixture
def firm() -> Firm:
    return build_firm()


def browser(person: Any) -> Client:
    client = Client()
    client.force_login(person)
    return client


@pytest.mark.parametrize(("who", "scope"), [("admin", "all"), ("admin", "mine"), ("sam", "mine")])
def test_drill_list_count_equals_widget_count(firm: Firm, who: str, scope: str) -> None:
    person = firm.admin if who == "admin" else firm.sam.user
    client = browser(person)
    practice = str(firm.practice.public_id)
    body = client.get(DASHBOARD, {"practice": practice, "scope": scope}).json()
    drilled = [w for w in body["widgets"] if w["kind"] == "count" and w["filters"] is not None]
    assert {w["key"] for w in drilled} == {
        "trials_ending",
        "missing_bn",
        "missing_lock_date",
        "read_only",
    }
    for widget in drilled:
        listing = client.get(DIRECTORY, {"practice": practice, **widget["filters"]})
        assert listing.status_code == 200, listing.content
        assert listing.json()["count"] == widget["count"], widget["key"]


def test_new_filters_are_facets_and_validated(firm: Firm) -> None:
    client = browser(firm.admin)
    practice = str(firm.practice.public_id)
    facets = client.get(DIRECTORY, {"practice": practice}).json()["facets"]
    assert {f["value"]: f["count"] for f in facets["bn_missing"]} == {"yes": 2, "no": 3}
    assert {f["value"]: f["count"] for f in facets["lock_missing"]} == {"yes": 2, "no": 3}
    assert {f["value"]: f["count"] for f in facets["trial_ending"]} == {"yes": 1, "no": 4}
    bad = client.get(DIRECTORY, {"practice": practice, "trial_ending": "soon"})
    assert bad.status_code == 400 and bad.json()["field"] == "trial_ending"
