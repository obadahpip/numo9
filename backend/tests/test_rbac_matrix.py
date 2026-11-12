"""Permission matrix: role × endpoint × method (A-03-T10). Acceptance: the matrix passes.

Generated, not hand-written:

- **endpoints** — every method of every Numo9 API view in ``ROOT_URLCONF`` with its declared
  permission (``numo9.rbac.checks.declarations``, the same walk as the CI gate of A-03-T06);
- **roles** — every system role of the catalogue rules (``SYSTEM_ROLES``: organisation roles as
  members, practice roles as assigned practice staff, platform roles as platform assignments), a
  custom organisation role holding exactly the endpoint's permission, and a signed-out visitor;
- **expected** — from the catalogue: allowed exactly when the role's permission set (its rule
  over the catalogue) contains the key; ``PUBLIC`` → everyone, ``AUTHENTICATED`` → every signed-in
  user.

A refusal must be the permission refusal (``403 permission.denied``; ``401``/``403`` for a
signed-out visitor); an allowed request must get past it (anything but that refusal, and never a
server error). New endpoints and new permissions join the matrix by themselves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.rbac.catalogue import Scope, catalogue
from numo9.rbac.checks import Declaration, declarations
from numo9.rbac.drf import AUTHENTICATED, PUBLIC
from numo9.rbac.models import ApprovalLimit, Role, RoleAssignment, RoleScope
from numo9.rbac.system_roles import PROFILE_VIEW, SYSTEM_ROLES, SystemRole
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    AssignmentRole,
    Organisation,
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)
from numo9.tenancy.sweep import Endpoint, build_path, iter_endpoints

ENDPOINTS: list[Declaration] = declarations()
_ROUTES = {e.display or e.route: e for e in iter_endpoints()}


@dataclass(frozen=True)
class Subject:
    kind: str  # "member" | "practice" | "platform" | "custom" | "anonymous"
    key: str = ""

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.key}" if self.key else self.kind

    def permissions(self, endpoint_key: str) -> frozenset[str]:
        if self.kind == "custom":
            base = _system("organisation", "employee").permission_keys()
            return base | {endpoint_key}
        if self.kind in {"member", "practice", "platform"}:
            scope = {"member": "organisation", "practice": "practice", "platform": "platform"}
            return _system(scope[self.kind], self.key).permission_keys()
        return frozenset()


def _system(scope: str, key: str) -> SystemRole:
    return next(r for r in SYSTEM_ROLES if r.scope == scope and r.key == key)


SUBJECTS: list[Subject] = [
    *(Subject("member", r.key) for r in SYSTEM_ROLES if r.scope == Scope.ORGANISATION),
    *(Subject("practice", r.key) for r in SYSTEM_ROLES if r.scope == Scope.PRACTICE),
    *(Subject("platform", r.key) for r in SYSTEM_ROLES if r.scope == Scope.PLATFORM),
    Subject("custom"),
    Subject("anonymous"),
]


def expected_allowed(subject: Subject, permission: str) -> bool:
    if permission == PUBLIC:
        return True
    if subject.kind == "anonymous":
        return False
    if permission == AUTHENTICATED:
        return True
    scope = catalogue.get(permission).scope
    if scope == Scope.ORGANISATION:
        # Platform staff are not in the organisation: no organisation permissions (and 404).
        return subject.kind != "platform" and permission in subject.permissions(permission)
    if scope == Scope.PLATFORM:
        return subject.kind == "platform" and permission in subject.permissions(permission)
    raise AssertionError("practice-scope endpoints: extend the matrix with an acting practice")


CASES = [
    pytest.param(e, s, id=f"{e.method} /{e.route} as {s.label}")
    for e in ENDPOINTS
    for s in SUBJECTS
]


# ---- the world each case runs in -------------------------------------------------------------


@dataclass
class World:
    org: Organisation
    custom_role: Role
    target: User
    limit: ApprovalLimit


def _user(email: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=email.split("@")[0])


def build_world() -> World:
    org = Organisation.objects.create(name="Matrix Org Ltd.")
    owner = _user("owner@matrix.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    target = _user("target@matrix.ca")
    OrganisationMember.objects.create(organisation=org, user=target, role="sales")
    custom = Role.objects.create(scope=RoleScope.ORGANISATION, name="Matrix role", organisation=org)
    RoleAssignment.objects.create(role=custom, user=target, organisation=org)
    with org_context(org):
        limit = ApprovalLimit.objects.create(user=target, doc_type="bill", max_amount=Decimal(10))
    return World(org, custom, target, limit)


def sign_in(subject: Subject, world: World, permission: str) -> Client:
    client = Client(raise_request_exception=False)
    if subject.kind == "anonymous":
        return client
    user = _user(f"{subject.label.replace(':', '-')}@subject.ca")
    if subject.kind == "member":
        OrganisationMember.objects.create(organisation=world.org, user=user, role=subject.key)
    elif subject.kind == "custom":
        OrganisationMember.objects.create(organisation=world.org, user=user, role="employee")
        role = Role.objects.create(
            scope=RoleScope.ORGANISATION, name="Exactly this", organisation=world.org
        )
        if permission not in (PUBLIC, AUTHENTICATED):
            role.grants.create(permission=permission)
        RoleAssignment.objects.create(role=role, user=user, organisation=world.org)
    elif subject.kind == "practice":
        practice = Practice.objects.create(name="Matrix Practice")
        assignment = PracticeAssignment.objects.create(
            practice=practice, organisation=world.org, role=AssignmentRole.FULL_SERVICE
        )
        pm = PracticeMember.objects.create(practice=practice, user=user, role=subject.key)
        assignment.assigned_staff.add(pm)
    elif subject.kind == "platform":
        role = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key=subject.key)
        RoleAssignment.objects.create(role=role, user=user)
    client.force_login(user)
    return client


def path_for(declaration: Declaration, world: World) -> str:
    endpoint: Endpoint = _ROUTES[declaration.route]
    values = {
        "org": str(world.org.public_id),
        "role_id": str(world.custom_role.public_id),
        "user_id": str(world.target.public_id),
        "public_id": str(world.limit.public_id),
        "invitation_id": "00000000-0000-4000-8000-000000000000",
    }
    path = build_path(endpoint, {k: v for k, v in values.items() if k in endpoint.groups})
    assert path is not None, f"cannot build a URL for /{declaration.route}: add its parameter"
    return path


def _code(response: Any) -> str | None:
    # Content type first: a streaming answer (the job event stream, A-08-T06) has no .content.
    if not response.get("Content-Type", "").startswith("application/json") or not response.content:
        return None
    body = response.json()
    return body.get("code") if isinstance(body, dict) else None


# ---- the matrix ------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(("declaration", "subject"), CASES)
def test_matrix(declaration: Declaration, subject: Subject) -> None:
    assert declaration.permission is not None  # the CI gate (A-03-T06) refuses undeclared ones
    world = build_world()
    client = sign_in(subject, world, declaration.permission)
    path = path_for(declaration, world)
    response = getattr(client, declaration.method.lower())(
        path, data={} if declaration.method != "GET" else None, content_type="application/json"
    )
    status = response.status_code
    code = _code(response)
    assert status < 500, f"{status}: {response.content[:300]!r}"
    if expected_allowed(subject, declaration.permission):
        assert code != "permission.denied" and status != 401, (status, code)
        if subject.kind != "anonymous":
            assert not (status == 403 and code in {None, "not_authenticated"}), (status, code)
    elif subject.kind == "anonymous":
        assert status in {401, 403}, status
    else:
        scope = catalogue.get(declaration.permission).scope
        if subject.kind == "platform" and scope == Scope.ORGANISATION:
            assert status == 404  # not in the organisation: it does not exist for them
        else:
            assert (status, code) == (403, "permission.denied")


# ---- the matrix is generated, complete and meaningful ----------------------------------------


def test_every_endpoint_method_is_in_the_matrix() -> None:
    assert ENDPOINTS, "no endpoints found"
    covered = {(d.route, d.method) for d in ENDPOINTS}
    assert len(CASES) == len(covered) * len(SUBJECTS)
    assert ("api/v1/o/<uuid:org>/roles", "POST") in covered


def test_every_system_role_is_a_subject() -> None:
    assert {(s.kind, s.key) for s in SUBJECTS if s.key} == {
        ({"organisation": "member", "practice": "practice", "platform": "platform"}[r.scope], r.key)
        for r in SYSTEM_ROLES
    }


def test_no_practice_scope_endpoint_yet() -> None:
    """The matrix handles organisation and platform keys; practice keys need an acting practice."""
    practice = [
        d
        for d in ENDPOINTS
        if d.permission not in (PUBLIC, AUTHENTICATED, None)
        and catalogue.get(d.permission).scope == Scope.PRACTICE
    ]
    assert practice == [], "a practice-scope endpoint exists: extend expected_allowed/sign_in"


def test_each_organisation_key_splits_the_roles() -> None:
    """Every organisation key on an endpoint is allowed to some roles and refused to others —
    except ``organisation.profile.view``, which every role includes by design (A-03-T03)."""
    keys = {
        d.permission
        for d in ENDPOINTS
        if d.permission not in (PUBLIC, AUTHENTICATED, None)
        and catalogue.get(d.permission).scope == Scope.ORGANISATION
    } - {PROFILE_VIEW}
    assert keys
    members = [s for s in SUBJECTS if s.kind == "member"]
    for key in keys:
        verdicts = {expected_allowed(s, key) for s in members}
        assert verdicts == {True, False}, key


def test_routes_are_found_by_their_written_form() -> None:
    for declaration in ENDPOINTS:
        assert declaration.route in _ROUTES
        assert not re.search(r"\(\?P<", declaration.route)  # path() routes, not raw regexes
