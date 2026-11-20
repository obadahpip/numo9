"""V-04-T09 (API part) — customise the dashboard: reorder and hide, persisted per user.

Acceptance: the layout persists per user (and practice): saved once, the next dashboard (another
browser) answers the widgets in that order with the hidden ones marked; another user's dashboard
is unchanged; unknown keys are dropped; widgets the user can't see can't be stored.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from tests.dashboard_helpers import Firm, build_firm

pytestmark = pytest.mark.django_db
URL = "/api/v1/practice/dashboard"


def browser(person: Any) -> Client:
    client = Client()
    client.force_login(person)
    return client


def save(client: Client, firm: Firm, body: dict[str, Any]) -> Any:
    return client.put(
        f"{URL}/layout?practice={firm.practice.public_id}",
        json.dumps(body),
        content_type="application/json",
    )


def keys(client: Client, firm: Firm) -> list[tuple[str, bool]]:
    body = client.get(URL, {"practice": str(firm.practice.public_id)}).json()
    return [(w["key"], w["hidden"]) for w in body["widgets"]]


def test_order_and_hidden_persist_per_user() -> None:
    firm = build_firm()
    response = save(
        browser(firm.admin),
        firm,
        {"order": ["workload", "read_only", "nonsense"], "hidden": ["deadlines", "nonsense"]},
    )
    assert response.status_code == 200, response.content
    assert response.json() == {"order": ["workload", "read_only"], "hidden": ["deadlines"]}
    assert keys(browser(firm.admin), firm) == [  # a new browser: same layout
        ("workload", False),
        ("read_only", False),
        ("trials_ending", False),
        ("missing_bn", False),
        ("missing_lock_date", False),
        ("dormant_staff", False),
        ("deadlines", True),
    ]
    sam = keys(browser(firm.sam.user), firm)
    assert sam[0] == ("trials_ending", False)  # Sam's dashboard is his own
    assert not any(hidden for _k, hidden in sam)


def test_a_widget_the_user_cannot_see_is_not_stored() -> None:
    firm = build_firm()
    response = save(browser(firm.sam.user), firm, {"order": ["dormant_staff"], "hidden": []})
    assert response.json() == {"order": [], "hidden": []}
