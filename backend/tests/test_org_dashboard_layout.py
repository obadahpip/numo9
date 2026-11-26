"""K-05-T02 — ``DashboardLayout`` per person (widgets, order, settings) with role defaults.

Acceptance: a new person gets their role's default (owner, accountant, sales, purchasing differ;
Bank & cash is on the owner's and accountant's — gap-04 — and the library has no advertising
widget); the layout persists per person and organisation; changes are validated (known widgets,
once each, settings); reset gives the role's default again.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from numo9.dashboard.layouts import (
    LayoutError,
    dashboard_role,
    layout_for,
    reset_layout,
    save_layout,
    visible_widgets,
)
from numo9.dashboard.models import DashboardLayout
from numo9.dashboard.widgets import LIBRARY, ROLE_DEFAULTS, default_widgets
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.auth_helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def world() -> dict[str, Any]:
    maple = Organisation.objects.create(name="Maple Fixtures Ltd.")
    pine = Organisation.objects.create(name="Pine Ridge Inc.")
    people: dict[str, Any] = {"maple": maple, "pine": pine}
    for role in ("owner", "admin", "accountant_delegate", "sales", "purchasing", "payroll"):
        person = make_user(f"{role}@maple.ca", name=role.title())
        OrganisationMember.objects.create(organisation=maple, user=person, role=role)
        people[role] = person
    OrganisationMember.objects.create(organisation=pine, user=people["owner"], role="sales")
    return people


def keys(layout: DashboardLayout) -> list[str]:
    return [w["key"] for w in layout.widgets]


@pytest.mark.parametrize(
    ("member", "role"),
    [
        ("owner", "owner"),
        ("admin", "owner"),
        ("accountant_delegate", "accountant"),
        ("sales", "sales"),
        ("purchasing", "purchasing"),
        ("payroll", "basic"),
    ],
)
def test_new_person_gets_role_default(world: dict[str, Any], member: str, role: str) -> None:
    layout = layout_for(world[member], world["maple"])
    assert layout.role == role
    assert keys(layout) == list(ROLE_DEFAULTS[role])
    assert layout.customised is False
    with org_context(world["maple"]):
        assert DashboardLayout.objects.filter(user=world[member]).count() == 1


def test_role_defaults_differ_and_show_bank_balances() -> None:
    layouts = {role: ROLE_DEFAULTS[role] for role in ("owner", "accountant", "sales", "purchasing")}
    assert len({tuple(v) for v in layouts.values()}) == 4
    assert layouts["owner"][0] == "bank_cash" and layouts["accountant"][0] == "bank_cash"
    assert "bills_to_pay" not in layouts["sales"] and "invoices_owed" not in layouts["purchasing"]
    # gap-04: nothing in the library advertises (no ad, app store or upgrade widget).
    assert set(LIBRARY) == {
        "bank_cash",
        "cash_in_out",
        "invoices_owed",
        "bills_to_pay",
        "deadlines",
        "pnl_snapshot",
        "account_watchlist",
        "exceptions",
        "approvals",
    }
    assert all(key in LIBRARY for keys_ in ROLE_DEFAULTS.values() for key in keys_)
    assert default_widgets("owner")[1] == {"key": "cash_in_out", "settings": {"months": 6}}


def test_person_reached_through_a_practice_is_an_accountant(world: dict[str, Any]) -> None:
    outsider = make_user("cpa@abuodeh.ca", name="Practice accountant")
    assert dashboard_role(outsider, world["maple"]) == "accountant"


def test_layout_persists_per_person_and_organisation(world: dict[str, Any]) -> None:
    owner = world["owner"]
    first = layout_for(owner, world["maple"])
    saved = save_layout(
        owner,
        world["maple"],
        [{"key": "deadlines"}, {"key": "cash_in_out", "settings": {"months": 12}}, "bank_cash"],
    )
    assert saved.pk == first.pk and saved.customised is True
    again = layout_for(owner, world["maple"])
    assert again.widgets == [
        {"key": "deadlines", "settings": {}},
        {"key": "cash_in_out", "settings": {"months": 12}},
        {"key": "bank_cash", "settings": {}},
    ]
    # The same person in another organisation has that organisation's own layout and role.
    other = layout_for(owner, world["pine"])
    assert (other.role, keys(other)) == ("sales", list(ROLE_DEFAULTS["sales"]))
    # Another person here still has their own default.
    assert keys(layout_for(world["admin"], world["maple"])) == list(ROLE_DEFAULTS["owner"])


def test_settings_defaults_and_watchlist(world: dict[str, Any]) -> None:
    accounts = [str(uuid.uuid4()), str(uuid.uuid4())]
    layout = save_layout(
        world["owner"],
        world["maple"],
        [
            {"key": "pnl_snapshot"},
            {"key": "account_watchlist", "settings": {"accounts": [*accounts, accounts[0]]}},
        ],
    )
    assert layout.widgets == [
        {"key": "pnl_snapshot", "settings": {"period": "mtd"}},
        {"key": "account_watchlist", "settings": {"accounts": accounts}},
    ]


@pytest.mark.parametrize(
    ("widgets", "code", "key", "setting"),
    [
        ([{"key": "ads"}], "unknown_widget", "ads", ""),
        (["bank_cash", "bank_cash"], "duplicate_widget", "bank_cash", ""),
        (
            [{"key": "cash_in_out", "settings": {"months": 7}}],
            "bad_setting",
            "cash_in_out",
            "months",
        ),
        (
            [{"key": "pnl_snapshot", "settings": {"colour": "red"}}],
            "bad_setting",
            "pnl_snapshot",
            "colour",
        ),
        (
            [{"key": "account_watchlist", "settings": {"accounts": ["x"]}}],
            "bad_setting",
            "account_watchlist",
            "accounts",
        ),
        (
            [{"key": "account_watchlist", "settings": {"accounts": []}}],
            "bad_setting",
            "account_watchlist",
            "accounts",
        ),
        ("bank_cash", "bad_layout", "", ""),
        ([42], "bad_layout", "", ""),
    ],
)
def test_refuses_invalid_layouts(
    world: dict[str, Any], widgets: Any, code: str, key: str, setting: str
) -> None:
    with pytest.raises(LayoutError) as refused:
        save_layout(world["owner"], world["maple"], widgets)
    assert (refused.value.code, refused.value.key, refused.value.setting) == (code, key, setting)
    assert keys(layout_for(world["owner"], world["maple"])) == list(ROLE_DEFAULTS["owner"])


def test_empty_layout_is_allowed(world: dict[str, Any]) -> None:
    assert save_layout(world["sales"], world["maple"], []).widgets == []


def test_reset_gives_the_current_roles_default(world: dict[str, Any]) -> None:
    person = world["sales"]
    save_layout(person, world["maple"], ["deadlines"])
    OrganisationMember.objects.filter(user=person, organisation=world["maple"]).update(
        role="purchasing"
    )
    layout = reset_layout(person, world["maple"])
    assert (layout.role, keys(layout), layout.customised) == (
        "purchasing",
        list(ROLE_DEFAULTS["purchasing"]),
        False,
    )


def test_unknown_stored_widgets_are_not_shown(world: dict[str, Any]) -> None:
    layout = layout_for(world["owner"], world["maple"])
    with org_context(world["maple"]):
        DashboardLayout.objects.filter(pk=layout.pk).update(
            widgets=[
                {"key": "retired_widget", "settings": {}},
                {"key": "approvals", "settings": {}},
            ]
        )
    assert [w["key"] for w in visible_widgets(layout_for(world["owner"], world["maple"]))] == [
        "approvals"
    ]
