"""V-01-T04/T05 — isolation sweep of the organisation directory (``/api/v1/practice/orgs``).

The directory is not organisation-scoped (no ``/o/<org>/`` in its URL), so the router sweep
(A-01-T09) lists it as exempt; this sweep proves the same promise for it: across a random graph of
practices, staff and assignments, every user sees **exactly** the organisations they may open in
that practice — never an unassigned one, by listing, searching its name or BN, filtering or
counting — and nothing at all in a practice they don't belong to.
"""

from __future__ import annotations

import random
from typing import Any

import pytest
from rest_framework.test import APIClient

from numo9.tenancy.access import PRACTICE_WIDE_ROLES, can_access
from numo9.tenancy.models import PracticeAssignment, PracticeMember, PracticeRole
from numo9.workspace.summary import rebuild_all
from tests.workspace_helpers import client_org, member, practice, user, valid_bn

pytestmark = [pytest.mark.django_db, pytest.mark.tenant_isolation]

URL = "/api/v1/practice/orgs"


def expected(person: Any, firm: Any) -> set[str]:
    """Independent statement of the rule: active assignment of this practice, and the user is
    practice-wide there or assigned staff — and can open the organisation."""
    membership = PracticeMember.objects.filter(practice=firm, user=person).first()
    if membership is None:
        return set()
    names = set()
    for assignment in PracticeAssignment.objects.filter(practice=firm, active=True):
        staff = assignment.assigned_staff.filter(pk=membership.pk).exists()
        visible = assignment.organisation.status != "cancelled"
        allowed = membership.role in PRACTICE_WIDE_ROLES or staff
        if visible and allowed and can_access(person, assignment.organisation):
            names.add(assignment.organisation.name)
    return names


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_user_sees_exactly_their_organisations(seed: int) -> None:
    rng = random.Random(seed)  # noqa: S311 (test data, not security)
    firms = [practice(f"Practice {i}") for i in range(3)]
    people = [user(f"u{i}@example.ca", f"User {i}") for i in range(6)]
    memberships: dict[tuple[int, int], Any] = {}
    roles = [PracticeRole.PRACTICE_ADMIN, PracticeRole.ACCOUNTANT, PracticeRole.READ_ONLY]
    for p, firm in enumerate(firms):
        for u, person in enumerate(people):
            if rng.random() < 0.5:
                memberships[(p, u)] = member(firm, person, rng.choice(roles))
    organisations = []
    for o in range(14):
        organisation = client_org(None, f"Client {o:02d} Ltd.", bn=valid_bn(50000000 + o))
        organisations.append(organisation)
        for p, firm in enumerate(firms):
            if rng.random() < 0.45:
                staff = [m for (pp, _u), m in memberships.items() if pp == p and rng.random() < 0.4]
                assignment = PracticeAssignment.objects.create(
                    practice=firm, organisation=organisation, active=rng.random() < 0.85
                )
                assignment.assigned_staff.add(*staff)
    rebuild_all()

    checked = 0
    for person in people:
        client = APIClient()
        client.force_authenticate(person)
        for firm in firms:
            response = client.get(URL, {"practice": str(firm.public_id), "page_size": "2000"})
            allowed = expected(person, firm)
            if not PracticeMember.objects.filter(practice=firm, user=person).exists():
                assert response.status_code == 404
                continue
            body = response.json()
            got = {row["name"] for row in body["results"]}
            assert got == allowed, (person.email, firm.name)
            assert body["count"] == body["total"] == len(allowed)
            assert sum(i["count"] for i in body["facets"]["status"]) == len(allowed)
            # searching for each organisation the user may NOT see (name, BN with spaces)
            for organisation in organisations:
                if organisation.name in allowed:
                    continue
                bn = valid_bn(50000000 + organisations.index(organisation))
                for q in (organisation.name, f"{bn[:3]} {bn[3:6]} {bn[6:]}"):
                    found = client.get(URL, {"practice": str(firm.public_id), "q": q}).json()
                    assert organisation.name not in {r["name"] for r in found["results"]}
                    checked += 1
    assert checked > 0
