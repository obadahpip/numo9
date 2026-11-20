"""V-04-T06 — ``GET /api/v1/practice/dashboard`` with per-widget status (ok/error).

Acceptance: one failing provider doesn't fail the response (its widget answers error, the others
ok); scope all for practice-wide roles (default), mine for everyone else whatever they ask; an
unknown scope is a 400; a non-member gets 404, a member without the directory 403.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.workspace.dashboard import DashboardContext, WidgetAnswer
from tests.dashboard_helpers import Firm, build_firm
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
URL = "/api/v1/practice/dashboard"


@pytest.fixture
def firm() -> Firm:
    return build_firm()


def browser(person: Any) -> Client:
    client = Client()
    client.force_login(person)
    return client


def get(client: Client, firm: Firm, **query: str) -> Any:
    return client.get(URL, {"practice": str(firm.practice.public_id), **query})


def by_key(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {w["key"]: w for w in body["widgets"]}


def test_admin_sees_the_whole_practice_by_default(firm: Firm) -> None:
    response = get(browser(firm.admin), firm)
    assert response.status_code == 200, response.content
    body = response.json()
    assert (body["scope"], body["scopes"]) == ("all", ["mine", "all"])
    widgets_ = by_key(body)
    assert list(widgets_) == [
        "trials_ending",
        "missing_bn",
        "missing_lock_date",
        "read_only",
        "dormant_staff",
        "deadlines",
        "workload",
    ]
    assert all(w["status"] == "ok" for w in body["widgets"])
    assert widgets_["read_only"]["count"] == 2
    assert widgets_["dormant_staff"]["href"] == f"/p/{firm.practice.public_id}/staff"


def test_staff_always_get_their_own_organisations(firm: Firm) -> None:
    body = get(browser(firm.sam.user), firm, scope="all").json()
    assert (body["scope"], body["scopes"]) == ("mine", ["mine"])
    assert by_key(body)["read_only"]["count"] == 1  # Cedar only
    assert "dormant_staff" not in by_key(body)


def test_one_failing_provider_does_not_fail_the_response(
    firm: Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(ctx: DashboardContext) -> WidgetAnswer:
        raise RuntimeError("summary table locked")

    from numo9.workspace import dashboard

    original = dashboard._widgets["workload"]
    monkeypatch.setitem(
        dashboard._widgets,
        "workload",
        dashboard.Widget(**{**original.__dict__, "provider": broken}),
    )
    response = get(browser(firm.admin), firm)
    assert response.status_code == 200
    widgets_ = by_key(response.json())
    assert widgets_["workload"]["status"] == "error"
    assert widgets_["workload"]["count"] is None
    assert widgets_["read_only"]["status"] == "ok"


def test_bad_scope_and_access(firm: Firm) -> None:
    assert get(browser(firm.admin), firm, scope="everything").status_code == 400
    outsider = browser(user("x@other.ca"))
    assert get(outsider, firm).status_code == 404
    assert Client().get(URL, {"practice": str(firm.practice.public_id)}).status_code in (401, 403)
