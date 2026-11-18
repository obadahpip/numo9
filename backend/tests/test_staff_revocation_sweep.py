"""V-05-T10 — revocation sweep after a practice member is removed (or suspended).

Acceptance: 404 everywhere. A staff member reaching one client **directly** (assigned to the
organisation) and another **through a practice group** is swept over every organisation-scoped
endpoint of the real URLconf (the A-01 router sweep's enumeration, rows made by its factories),
for both organisations. While a member, most endpoints answer them; after the V-05-T05 service
removes them from the practice — or suspends them — every verb of every endpoint of both
organisations answers 404 (405 for a verb the view lacks) on the very next request, with the
same browser session, and the practice's own API (directory, staff) refuses them too. A
reinstated member gets the access back.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.staff import members
from numo9.tenancy.middleware import ORG_PATH_RE
from numo9.tenancy.models import PracticeRole
from numo9.tenancy.sweep import (
    SAFE_STATUSES,
    VERBS,
    _values,
    build_path,
    iter_endpoints,
    make_row,
    view_model,
)
from numo9.workspace.groups import add_organisation, assign_staff, create_group
from numo9.workspace.summary import rebuild_all
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = [pytest.mark.django_db, pytest.mark.tenant_isolation]


def _scoped_paths(org: Any) -> list[str]:
    paths = []
    for endpoint in iter_endpoints():
        probe = build_path(endpoint, _values(endpoint, org, None))
        if probe is None or ORG_PATH_RE.match(probe) is None:
            continue
        model = view_model(endpoint)
        row = make_row(model, org) if model else None
        path = build_path(endpoint, _values(endpoint, org, row))
        if path is not None:
            paths.append(path)
    return paths


def _world() -> dict[str, Any]:
    firm = practice("Abuodeh CPA")
    ada = user("ada@cpa.ca", name="Ada Admin")
    member(firm, ada, role=PracticeRole.PRACTICE_ADMIN)
    person = user("sam@cpa.ca", name="Sam Patel")
    sam = member(firm, person)
    direct = client_org(firm, "Maple Leaf Supply Ltd.", staff=[sam])
    grouped = client_org(firm, "Birch Holdings Inc.")
    toronto = create_group(firm, "Toronto office")
    add_organisation(toronto, grouped)
    assign_staff(toronto, sam)
    rebuild_all()
    browser = Client(raise_request_exception=False)
    browser.force_login(person)
    return {"firm": firm, "sam": sam, "direct": direct, "grouped": grouped, "browser": browser}


def _reached(browser: Client, paths: list[str]) -> int:
    return sum(1 for path in paths if browser.get(path).status_code != 404)


def _leaks(browser: Client, paths: list[str]) -> list[str]:
    return [
        f"{verb.upper()} {path} → {status}"
        for path in paths
        for verb in VERBS
        if (status := getattr(browser, verb)(path).status_code) not in SAFE_STATUSES
    ]


def _practice_api(world: dict[str, Any]) -> list[int]:
    browser: Client = world["browser"]
    firm = world["firm"].public_id
    return [
        browser.get(f"/api/v1/practice/orgs?practice={firm}").status_code,
        browser.get(f"/api/v1/practice/staff?practice={firm}").status_code,
    ]


@pytest.mark.parametrize("revocation", ["removed", "suspended"])
def test_removed_or_suspended_member_gets_404_on_every_organisation_endpoint(
    revocation: str,
) -> None:
    world = _world()
    browser: Client = world["browser"]
    paths = {key: _scoped_paths(world[key]) for key in ("direct", "grouped")}
    for key, scoped in paths.items():
        assert len(scoped) > 20, key  # the sweep reaches the organisation's endpoints
        assert _reached(browser, scoped) > len(scoped) // 2, key  # access while a member
    assert all(code == 200 for code in _practice_api(world))

    if revocation == "removed":
        members.remove(world["sam"])
    else:
        members.suspend(world["sam"])

    for key, scoped in paths.items():
        assert _leaks(browser, scoped) == [], key
    assert all(code in (403, 404) for code in _practice_api(world))


def test_reinstated_member_gets_access_back() -> None:
    world = _world()
    browser: Client = world["browser"]
    scoped = _scoped_paths(world["direct"])
    members.suspend(world["sam"])
    assert _leaks(browser, scoped) == []
    members.reinstate(world["sam"])
    assert _reached(browser, scoped) > len(scoped) // 2
