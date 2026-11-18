"""V-02-T12 — Isolation sweep extension: group revocation → 404 on every organisation record.

Acceptance: the sweep passes. A staff member who reaches a client **only through a practice
group** (assigned to "Toronto office", the client filed in its sub-group "Retail clients") is
swept over every organisation-scoped endpoint of the real URLconf (the A-01 router sweep's
enumeration, rows made by its factories): while assigned, the endpoints answer them (not 404
for at least one verb on most endpoints); after each kind of revocation — unassigned from the
group, client taken out of the group, sub-group moved out of the assigned group, group deleted —
every verb of every endpoint answers 404 (405 for a verb the view lacks), on the very next
request.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

from numo9.tenancy.middleware import ORG_PATH_RE
from numo9.tenancy.sweep import (
    SAFE_STATUSES,
    VERBS,
    _values,
    build_path,
    iter_endpoints,
    make_row,
    view_model,
)
from numo9.workspace.groups import (
    add_organisation,
    assign_staff,
    create_group,
    move_group,
    remove_organisation,
    unassign_staff,
)
from numo9.workspace.models import OrgGroup
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


REVOCATIONS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "unassigned": lambda w: unassign_staff(w["toronto"], w["staff"]),
    "removed from group": lambda w: remove_organisation(w["retail"], w["org"]),
    "sub-group moved out": lambda w: move_group(w["retail"], None),
    "group deleted": lambda w: OrgGroup.objects.get(pk=w["toronto"].pk).delete(),
}


@pytest.mark.parametrize("revocation", list(REVOCATIONS))
def test_group_revocation_is_404_on_every_organisation_endpoint(revocation: str) -> None:
    firm = practice("Abuodeh CPA", user("admin@cpa.ca"))
    person = user("sam@cpa.ca", "Sam Patel")
    staff = member(firm, person)
    org = client_org(firm, "Maple Leaf Supply Ltd.")
    toronto = create_group(firm, "Toronto office")
    retail = create_group(firm, "Retail clients", toronto)
    add_organisation(retail, org)
    assign_staff(toronto, staff)
    browser = Client(raise_request_exception=False)
    browser.force_login(person)
    paths = _scoped_paths(org)
    assert len(paths) > 20  # the sweep reaches the organisation's endpoints

    reached = sum(
        1 for path in paths if any(getattr(browser, v)(path).status_code != 404 for v in ("get",))
    )
    assert reached > len(paths) // 2  # while assigned, the group gives access

    REVOCATIONS[revocation]({"toronto": toronto, "retail": retail, "org": org, "staff": staff})

    leaks = [
        f"{verb.upper()} {path} → {status}"
        for path in paths
        for verb in VERBS
        if (status := getattr(browser, verb)(path).status_code) not in SAFE_STATUSES
    ]
    assert leaks == []
