"""V-01-T04 — directory search / filter query builder (tsvector + trigram + facets), scoped to the
organisations the user is assigned to.

Acceptance: an unassigned organisation is never returned (unit + security; the API-level sweep is
in tests/test_workspace_isolation.py).
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.tenancy.models import OrganisationStatus
from numo9.workspace.models import OrgDirectorySummary
from numo9.workspace.search import (
    DirectoryParams,
    DirectoryQuery,
    bn_digits,
    directory_scope,
    query_words,
)
from numo9.workspace.summary import rebuild_all
from tests.entitlement_helpers import package, subscribe
from tests.workspace_helpers import client_org, member, practice, user, valid_bn

pytestmark = pytest.mark.django_db

BN_MAPLE = "123456782"  # valid check digit


@pytest.fixture
def world() -> dict[str, Any]:
    """A practice with an admin, an accountant assigned to two clients, five clients in all."""
    admin = user("oa@abuodeh.ca", "Obadah Abuodeh")
    firm = practice("Abuodeh CPA", admin)
    accountant = user("sam@abuodeh.ca", "Sam Patel")
    staff = member(firm, accountant)
    owner = user("dana@erable.ca", "Dana Tremblay")
    maple = client_org(
        firm,
        "Maple Leaf Supply Ltd.",
        staff=[staff],
        settings={"mailing_province": "ON", "mailing_postal_code": "M5V 2T6", "industry": "Retail"},
        bn=BN_MAPLE,
    )
    erable = client_org(
        firm,
        "Érable Bakery Inc.",
        staff=[staff],
        settings={
            "mailing_province": "QC",
            "mailing_postal_code": "H2X 1Y4",
            "fye_month": 3,
            "fye_day": 31,
        },
        owner=owner,
        bn=valid_bn(87451299),
    )
    tile = client_org(
        firm,
        "Toronto Tile Co.",
        settings={
            "mailing_province": "ON",
            "mailing_postal_code": "M4C 1B5",
            "fye_month": 6,
            "fye_day": 30,
        },
        status=OrganisationStatus.TRIAL,
    )
    movers = client_org(firm, "North Shore Movers", status=OrganisationStatus.DEMO)
    closed = client_org(firm, "Closed Corp.", status=OrganisationStatus.CANCELLED)
    other_firm = practice("Other CPA", user("x@other.ca"))
    foreign = client_org(other_firm, "Maple Foreign Ltd.", bn=valid_bn(12345600))
    subscribe(maple, package("books", ["accounting"]))  # the only one without Payroll
    rebuild_all()
    OrgDirectorySummary.objects.filter(organisation=maple).update(overdue_count=3, tags=["Retail"])
    OrgDirectorySummary.objects.filter(organisation=tile).update(
        unfiled_count=1, gst_cycle="monthly"
    )
    return locals()


def names(rows: Any) -> list[str]:
    return [row.name for row in rows]


def run(w: dict[str, Any], who: str = "admin", **params: Any) -> list[str]:
    rows, _count = DirectoryQuery(w[who], w["firm"], DirectoryParams(**params)).page()
    return names(rows)


# ---- scope -------------------------------------------------------------------------------------


def test_admin_sees_every_client_accountant_only_assigned(world: dict[str, Any]) -> None:
    assert sorted(run(world)) == [
        "Maple Leaf Supply Ltd.",
        "North Shore Movers",
        "Toronto Tile Co.",
        "Érable Bakery Inc.",
    ]
    assert sorted(run(world, "accountant")) == ["Maple Leaf Supply Ltd.", "Érable Bakery Inc."]


def test_non_member_inactive_user_and_other_practice_see_nothing(world: dict[str, Any]) -> None:
    stranger = user("nobody@x.ca")
    assert not directory_scope(stranger, world["firm"]).exists()
    assert not directory_scope(None, world["firm"]).exists()
    world["accountant"].is_active = False
    world["accountant"].save()
    assert not directory_scope(world["accountant"], world["firm"]).exists()
    # the other practice's admin never sees this practice's rows, even searching the same name
    other_admin = world["other_firm"].members.get().user
    assert run({**world, "admin": other_admin}, q="maple") == []


def test_switched_off_assignment_and_unassignment_disappear(world: dict[str, Any]) -> None:
    assignment = world["maple"].practice_assignments.get(practice=world["firm"])
    assignment.assigned_staff.remove(world["staff"])
    assert run(world, "accountant") == ["Érable Bakery Inc."]
    # even a stale summary row (refresh not run) of a switched-off assignment is never listed
    world["erable"].practice_assignments.filter(practice=world["firm"]).update(active=False)
    assert run(world, "accountant") == []
    assert "Érable Bakery Inc." not in run(world)


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": "maple"},
        {"q": valid_bn(12345600)},
        {"filters": {"province": ["ON"]}},
        {"include_archived": True},
    ],
)
def test_unassigned_organisation_never_returned_or_counted(
    world: dict[str, Any], params: dict[str, Any]
) -> None:
    for who in ("admin", "accountant"):
        query = DirectoryQuery(world[who], world["firm"], DirectoryParams(**params))
        rows, count = query.page()
        assert "Maple Foreign Ltd." not in names(rows)
        assert count == len(rows)
        facets = query.facets()
        assert sum(item["count"] for item in facets["status"]) == count


# ---- search ------------------------------------------------------------------------------------


def test_query_parsing() -> None:
    assert query_words("Érable  BAKERY, inc.") == ["erable", "bakery", "inc"]
    assert bn_digits("123 456") == "123456"
    assert bn_digits("123-456-782") == "123456782"
    assert bn_digits("12") == ""
    assert bn_digits("maple 123") == ""


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("erable", ["Érable Bakery Inc."]),  # accents ignored
        ("ÉRABLE bak", ["Érable Bakery Inc."]),  # case ignored, prefix
        ("map sup", ["Maple Leaf Supply Ltd."]),  # every word, prefixes
        ("maple movers", []),  # every word must match
        ("123 456", ["Maple Leaf Supply Ltd."]),  # BN typed with spaces
        ("456 782", ["Maple Leaf Supply Ltd."]),  # BN middle/end
        ("123-456-782", ["Maple Leaf Supply Ltd."]),
        ("tremblay", ["Érable Bakery Inc."]),  # owner name
        ("dana@erable.ca", ["Érable Bakery Inc."]),  # owner email
        ("retail", ["Maple Leaf Supply Ltd."]),  # industry and tag
        ("quebec", ["Érable Bakery Inc."]),  # province name
        ("québec", ["Érable Bakery Inc."]),
        ("closed", []),  # archived hidden by default
    ],
)
def test_search(world: dict[str, Any], q: str, expected: list[str]) -> None:
    assert run(world, q=q) == expected


def test_search_finds_archived_when_shown(world: dict[str, Any]) -> None:
    assert run(world, q="closed", include_archived=True) == ["Closed Corp."]


def test_search_ranks_name_matches_first(world: dict[str, Any]) -> None:
    OrgDirectorySummary.objects.filter(organisation=world["tile"]).update(
        owner_name="Ontario Maple"
    )
    rebuild = OrgDirectorySummary.objects.get(organisation=world["tile"])
    from numo9.workspace.summary import _write_vector

    _write_vector(rebuild.pk, "")
    assert run(world, q="maple") == ["Maple Leaf Supply Ltd.", "Toronto Tile Co."]


# ---- filters -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"province": ["ON"]}, ["Maple Leaf Supply Ltd.", "Toronto Tile Co."]),
        (
            {"province": ["ON", "QC"]},
            ["Maple Leaf Supply Ltd.", "Toronto Tile Co.", "Érable Bakery Inc."],
        ),
        ({"province": ["ON"], "status": ["trial"]}, ["Toronto Tile Co."]),
        ({"status": ["demo"]}, ["North Shore Movers"]),
        ({"fye": ["3", "6"]}, ["Toronto Tile Co.", "Érable Bakery Inc."]),
        ({"overdue": ["yes"]}, ["Maple Leaf Supply Ltd."]),
        ({"overdue": ["no"], "province": ["ON"]}, ["Toronto Tile Co."]),
        (
            {"overdue": ["yes", "no"], "province": ["ON"]},
            ["Maple Leaf Supply Ltd.", "Toronto Tile Co."],
        ),
        ({"unfiled": ["yes"]}, ["Toronto Tile Co."]),
        ({"gst_cycle": ["monthly"]}, ["Toronto Tile Co."]),
        ({"payroll": ["no"]}, ["Maple Leaf Supply Ltd."]),  # trials have every product
        ({"payroll": ["yes"], "province": ["ON"]}, ["Toronto Tile Co."]),
        ({"tag": ["Retail"]}, ["Maple Leaf Supply Ltd."]),
        ({"status": ["archived"]}, ["Closed Corp."]),  # naming archived shows it
    ],
)
def test_filters(world: dict[str, Any], filters: dict[str, list[str]], expected: list[str]) -> None:
    assert sorted(run(world, filters=filters)) == sorted(expected)


def test_facet_count_equals_result_count_after_applying(world: dict[str, Any]) -> None:
    """Every offered value of every filter, from several starting states."""
    starts: list[dict[str, Any]] = [
        {},
        {"q": "a"},
        {"filters": {"province": ["ON"]}},
        {"filters": {"status": ["paid", "trial"]}, "include_archived": True},
    ]
    checked = 0
    for start in starts:
        query = DirectoryQuery(world["admin"], world["firm"], DirectoryParams(**start))
        for name, items in query.facets().items():
            if start.get("filters", {}).get(name):
                continue  # adding to an already-filtered dimension widens it (OR)
            for item in items:
                filters = {**start.get("filters", {}), name: [item["value"]]}
                params = DirectoryParams(**{**start, "filters": filters})
                _rows, count = DirectoryQuery(world["admin"], world["firm"], params).page()
                assert count == item["count"], (start, name, item)
                checked += 1
    assert checked > 30


def test_facets_list_every_status_and_keep_selected_values(world: dict[str, Any]) -> None:
    params = DirectoryParams(filters={"province": ["NB"]})
    facets = DirectoryQuery(world["admin"], world["firm"], params).facets()
    assert [i["value"] for i in facets["status"]] == ["trial", "paid", "demo", "read_only"]
    assert {"value": "NB", "count": 0} in facets["province"]
    assert facets["payroll"] == [{"value": "yes", "count": 0}, {"value": "no", "count": 0}]
    assert facets["fye"] == []  # nothing in NB: no months to offer


# ---- sorting and pages -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        (
            ["name"],
            [
                "Maple Leaf Supply Ltd.",
                "North Shore Movers",
                "Toronto Tile Co.",
                "Érable Bakery Inc.",
            ],
        ),
        (
            ["-overdue", "name"],
            [
                "Maple Leaf Supply Ltd.",
                "North Shore Movers",
                "Toronto Tile Co.",
                "Érable Bakery Inc.",
            ],
        ),
        (
            ["fye"],
            [
                "Érable Bakery Inc.",
                "Toronto Tile Co.",
                "Maple Leaf Supply Ltd.",
                "North Shore Movers",
            ],
        ),
        (
            ["-bn"],
            [
                "Érable Bakery Inc.",
                "Maple Leaf Supply Ltd.",
                "North Shore Movers",
                "Toronto Tile Co.",
            ],
        ),
        (
            ["bn"],
            [
                "Maple Leaf Supply Ltd.",
                "Érable Bakery Inc.",
                "North Shore Movers",
                "Toronto Tile Co.",
            ],
        ),
    ],
)
def test_sorting_blank_values_last(
    world: dict[str, Any], sort: list[str], expected: list[str]
) -> None:
    got = run(world, sort=sort)
    if sort == ["name"]:
        assert sorted(got, key=str.casefold) == sorted(expected, key=str.casefold)
        assert got.index("Maple Leaf Supply Ltd.") < got.index("Toronto Tile Co.")
    else:
        assert got == expected


def test_pages(world: dict[str, Any]) -> None:
    params = DirectoryParams(sort=["fye"], page=2, page_size=3)
    rows, count = DirectoryQuery(world["admin"], world["firm"], params).page()
    assert count == 4 and names(rows) == ["North Shore Movers"]
