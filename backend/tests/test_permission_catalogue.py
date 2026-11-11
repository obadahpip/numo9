"""Permission catalogue and registry (A-03-T01). Acceptance: ``permcat_export`` lists all."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.utils.functional import Promise

from numo9.rbac.catalogue import (
    KEY,
    MODULES,
    CatalogueError,
    Permission,
    PermissionRegistry,
    Risk,
    Scope,
    UnknownPermission,
    catalogue,
)

# Declared by the apps that exist today (tenancy, rbac); later apps add theirs.
EXPECTED = {
    "organisation.profile.view",
    "organisation.settings.manage",
    "organisation.close",
    "organisation.members.view",
    "organisation.members.invite",
    "organisation.members.manage",
    "organisation.accountant.invite",
    "practice.profile.view",
    "practice.settings.manage",
    "practice.staff.view",
    "practice.staff.invite",
    "practice.staff.manage",
    "practice.clients.create",
    "practice.clients.assign",
    "practice.clients.invite_owner",
    "practice.roles.manage",
    "roles.role.view",
    "roles.role.manage",
    "roles.assignment.manage",
    "roles.limit.view",
    "roles.limit.manage",
    "platform.console.view",
    "platform.catalogue.manage",
    "platform.impersonate",
    "platform.jobs.view",
    "platform.jobs.manage",
    "platform.flags.manage",
}


def test_apps_permissions_modules_are_discovered() -> None:
    assert catalogue.keys() >= EXPECTED


def test_every_permission_is_well_formed() -> None:
    for permission in catalogue:
        assert KEY.match(permission.key), permission.key
        assert permission.module in MODULES
        assert isinstance(permission.label, Promise), f"{permission.key}: label must be gettext"
        assert str(permission.label)[0].isupper()
        assert isinstance(permission.risk, Risk)
        assert isinstance(permission.scope, Scope)


def test_scopes_follow_the_key_prefix() -> None:
    for permission in catalogue:
        if permission.key.startswith("platform."):
            assert permission.scope == Scope.PLATFORM, permission.key
        elif permission.key.startswith("practice."):
            assert permission.scope == Scope.PRACTICE, permission.key
        else:
            assert permission.scope == Scope.ORGANISATION, permission.key


def test_lookup() -> None:
    assert catalogue.get("roles.limit.manage").risk == Risk.CRITICAL
    assert catalogue.get("organisation.members.view").read_only
    assert catalogue.get("organisation.members.view").action == "view"
    assert not catalogue.get("organisation.members.invite").read_only
    assert "roles.limit.manage" in catalogue
    with pytest.raises(UnknownPermission):
        catalogue.get("roles.limits.manage")


@pytest.mark.parametrize(
    "permission, message",
    [
        (Permission("Contacts.view", "x", "contacts", Risk.LOW), "dotted lower-case"),
        (Permission("contacts", "x", "contacts", Risk.LOW), "dotted lower-case"),
        (Permission("a.b.c.d.e", "x", "contacts", Risk.LOW), "dotted lower-case"),
        (Permission("contacts.view", "x", "crm", Risk.LOW), "unknown module"),
        (Permission("contacts.view", "x", "contacts", "low"), "Risk/Scope"),  # type: ignore[arg-type]
    ],
)
def test_registry_refuses_bad_declarations(permission: Permission, message: str) -> None:
    with pytest.raises(CatalogueError, match=message):
        PermissionRegistry().register(permission)


def test_registry_refuses_a_key_declared_twice() -> None:
    registry = PermissionRegistry()
    registry.register(Permission("contacts.contact.view", "View", "contacts", Risk.LOW))
    with pytest.raises(CatalogueError, match="declared twice"):
        registry.register(Permission("contacts.contact.view", "Again", "contacts", Risk.LOW))


def test_iteration_is_grouped_by_module_in_navigation_order() -> None:
    order = [MODULES.index(p.module) for p in catalogue]
    assert order == sorted(order)


# ---- permcat_export ---------------------------------------------------------------------------


def test_permcat_export_json_lists_all() -> None:
    out = io.StringIO()
    call_command("permcat_export", stdout=out)
    data = json.loads(out.getvalue())
    assert data["count"] == len(catalogue)
    assert {row["key"] for row in data["permissions"]} == catalogue.keys()
    close = next(row for row in data["permissions"] if row["key"] == "organisation.close")
    assert close == {
        "key": "organisation.close",
        "label": "Close the organisation",
        "module": "settings",
        "risk": "critical",
        "scope": "organisation",
        "owner_only": True,
    }


def test_permcat_export_csv_and_markdown(tmp_path: Path) -> None:
    target = tmp_path / "permissions.csv"
    call_command("permcat_export", "--format", "csv", "--output", str(target), stderr=io.StringIO())
    rows = list(csv.DictReader(target.open(encoding="utf-8")))
    assert len(rows) == len(catalogue)
    assert set(rows[0]) == {"key", "label", "module", "risk", "scope", "owner_only"}

    out = io.StringIO()
    call_command("permcat_export", "--format", "markdown", stdout=out)
    text = out.getvalue()
    assert text.startswith(f"{len(catalogue)} permissions.")
    for key in sorted(catalogue.keys()):
        assert f"`{key}`" in text


def test_permcat_export_labels_in_french() -> None:
    out = io.StringIO()
    call_command("permcat_export", "--locale", "fr-ca", stdout=out)
    labels = {row["key"]: row["label"] for row in json.loads(out.getvalue())["permissions"]}
    assert labels["organisation.close"] == "Fermer l’organisation"
