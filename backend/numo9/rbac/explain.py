"""'Why can't I?' (A-03-T14): what a permission refusal tells the person refused.

Every ``403 permission.denied`` from ``RequiresPermission`` carries an ``explain`` payload so
the screen can show the ExplainPanel (A-10-T12) instead of a bare error:

- ``rule`` — what refused: ``permission`` (later also ``entitlement`` U-03, ``lock`` A-05);
- ``permission`` — the required permission: key, label, module (+ label), risk (+ label);
- ``holders`` — people in this organisation who have it (name, public id, the roles that give
  it), so the person knows who could do it for them;
- ``managers`` — people who could give it to them: they may give roles
  (``roles.assignment.manage``) **and** hold the permission themselves (nobody can give what
  they don't have, A-03-T09);
- ``can_request`` — whether "Request access" can reach anyone (at least one manager).

Names only, never emails, and only inside the organisation the person already belongs to.
Lists are capped (``MAX_PEOPLE``) with a total count. Practice and platform permissions get
the permission part only (no organisation to look in).
"""

from __future__ import annotations

from typing import Any

from numo9.tenancy.models import Organisation

from .catalogue import MODULE_LABELS, RISK_LABELS, Scope, catalogue
from .resolver import organisation_permissions, organisation_roles
from .services import people, role_name

ASSIGN = "roles.assignment.manage"
MAX_PEOPLE = 5


def permission_info(key: str) -> dict[str, Any]:
    p = catalogue.get(key)
    return {
        "key": p.key,
        "label": str(p.label),
        "module": p.module,
        "module_label": str(MODULE_LABELS[p.module]),
        "risk": p.risk.value,
        "risk_label": str(RISK_LABELS[p.risk.value]),
    }


def _roles_giving(user: Any, organisation: Organisation, key: str) -> list[str]:
    roles = organisation_roles(user, organisation).filter(grants__permission=key).distinct()
    return sorted({role_name(r) for r in roles})


def explain(user: Any, key: str, organisation: Organisation | None) -> dict[str, Any]:
    """The payload for a refusal of ``key`` to ``user`` (in ``organisation`` when given)."""
    payload: dict[str, Any] = {
        "rule": "permission",
        "permission": permission_info(key),
        "holders": [],
        "holders_total": 0,
        "managers": [],
        "can_request": False,
    }
    if organisation is None or catalogue.get(key).scope != Scope.ORGANISATION:
        return payload
    holders: list[dict[str, Any]] = []
    managers: list[dict[str, Any]] = []
    for person in people(organisation):
        if person.user.pk == getattr(user, "pk", None):
            continue
        granted = organisation_permissions(person.user, organisation)
        if key not in granted:
            continue
        ref = {"id": str(person.user.public_id), "name": person.user.name}
        holders.append({**ref, "roles": _roles_giving(person.user, organisation, key)})
        if ASSIGN in granted:
            managers.append(ref)
    payload.update(
        holders=holders[:MAX_PEOPLE],
        holders_total=len(holders),
        managers=managers[:MAX_PEOPLE],
        can_request=bool(managers),
    )
    return payload


def managers_for(organisation: Organisation, key: str, exclude: Any = None) -> list[Any]:
    """Users who could give ``key`` in the organisation (request-access recipients)."""
    found = []
    for person in people(organisation):
        if exclude is not None and person.user.pk == exclude.pk:
            continue
        granted = organisation_permissions(person.user, organisation)
        if ASSIGN in granted and key in granted:
            found.append(person.user)
    return found
