"""V-02-T08 — Directory "group by" + group filter + tag filter (V-01 extension).

Acceptance: group-by headers show counts — ``group_by=group`` answers, per group in tree order,
the matching organisations filed in it and their count (then "no group"), consistent with the
filters. Also: the group filter matches the group and its sub-groups; the group facet counts per
group with the other filters applied; tag names reach the directory rows when tagging (tag filter
and search); rows carry their group badges; staff assigned to a group see its organisations in
the directory; bad group ids are 400.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.workspace.groups import add_organisation, assign_staff, create_group
from numo9.workspace.models import Tag
from numo9.workspace.summary import rebuild_all
from numo9.workspace.tags import rename_tag, tag_organisation
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db
URL = "/api/v1/practice/orgs"


class World:
    def __init__(self) -> None:
        self.admin_user = user("oa@abuodeh.ca", "Obadah Abuodeh")
        self.firm = practice("Abuodeh CPA", self.admin_user)
        self.maple = client_org(
            self.firm, "Maple Leaf Supply Ltd.", settings={"mailing_province": "ON"}
        )
        self.erable = client_org(
            self.firm, "Érable Bakery Inc.", settings={"mailing_province": "QC"}
        )
        self.cedar = client_org(self.firm, "Cedar Roofing Co.", settings={"mailing_province": "ON"})
        self.lone = client_org(self.firm, "Lone Pine Ltd.", settings={"mailing_province": "BC"})
        self.toronto = create_group(self.firm, "Toronto office")
        self.retail = create_group(self.firm, "Retail clients", self.toronto)
        self.ottawa = create_group(self.firm, "Ottawa office")
        add_organisation(self.toronto, self.maple)
        add_organisation(self.retail, self.erable)
        add_organisation(self.ottawa, self.cedar)
        add_organisation(self.ottawa, self.maple)  # in two groups
        rebuild_all()
        self.admin = Client()
        self.admin.force_login(self.admin_user)

    def get(self, browser: Client | None = None, **params: Any) -> Any:
        query = {"practice": str(self.firm.public_id), "page_size": 2000, **params}
        response = (browser or self.admin).get(URL, query)
        assert response.status_code == 200, response.content
        return response.json()


@pytest.fixture
def w() -> World:
    return World()


def _names(body: dict[str, Any]) -> list[str]:
    return sorted(row["name"] for row in body["results"])


def test_group_filter_includes_sub_groups(w: World) -> None:
    body = w.get(group=str(w.toronto.public_id))
    assert _names(body) == ["Maple Leaf Supply Ltd.", "Érable Bakery Inc."]
    assert _names(w.get(group=str(w.retail.public_id))) == ["Érable Bakery Inc."]
    both = w.get(group=[str(w.retail.public_id), str(w.ottawa.public_id)])  # any of them
    assert body["count"] == 2 and both["count"] == 3


def test_group_facet_counts_with_other_filters(w: World) -> None:
    facets = w.get(province="ON")["facets"]["group"]
    assert [(f["label"], f["depth"], f["count"]) for f in facets] == [
        ("Ottawa office", 1, 2),
        ("Toronto office", 1, 1),
        ("Retail clients", 2, 0),
    ]


def test_group_by_headers_show_counts(w: World) -> None:
    body = w.get(group_by="group", columns="name,groups")
    headers = [
        (item["group"]["name"] if item["group"] else None, item["count"])
        for item in body["grouping"]
    ]
    assert headers == [
        ("Ottawa office", 2),
        ("Toronto office", 1),
        ("Retail clients", 1),
        (None, 1),
    ]
    ottawa = body["grouping"][0]
    assert len(ottawa["organisations"]) == ottawa["count"]
    assert ottawa["organisations"] == [str(w.cedar.public_id), str(w.maple.public_id)]  # by name
    filtered = w.get(group_by="group", province="QC")
    assert [item["count"] for item in filtered["grouping"]] == [0, 0, 1, 0]
    maple = next(r for r in body["results"] if r["name"].startswith("Maple"))
    assert sorted(g["name"] for g in maple["groups"]) == ["Ottawa office", "Toronto office"]


@pytest.mark.django_db(transaction=True)  # the directory refreshes when the change commits
def test_tag_names_reach_the_directory() -> None:
    w = World()
    tag = Tag.objects.create(practice=w.firm, name="Year-end soon", colour="amber")
    tag_organisation(tag, w.lone)
    body = w.get(tag="Year-end soon")
    assert _names(body) == ["Lone Pine Ltd."]
    assert {"value": "Year-end soon", "label": "Year-end soon", "count": 1} in body["facets"]["tag"]
    assert _names(w.get(q="year-end")) == ["Lone Pine Ltd."]
    rename_tag(tag, "YE soon")
    assert _names(w.get(tag="YE soon")) == ["Lone Pine Ltd."]
    assert w.get(tag="Year-end soon")["count"] == 0


def test_group_staff_see_their_groups_clients(w: World) -> None:
    sam = user("sam@abuodeh.ca", "Sam Patel")
    assign_staff(w.toronto, member(w.firm, sam))
    browser = Client()
    browser.force_login(sam)
    assert _names(w.get(browser)) == ["Maple Leaf Supply Ltd.", "Érable Bakery Inc."]


def test_bad_group_values_are_400(w: World) -> None:
    response = w.admin.get(URL, {"practice": str(w.firm.public_id), "group": "toronto"})
    assert response.status_code == 400 and response.json()["field"] == "group"
    bad = w.admin.get(URL, {"practice": str(w.firm.public_id), "group_by": "tag"})
    assert bad.status_code == 400 and bad.json()["field"] == "group_by"
    unknown = w.get(group="00000000-0000-4000-8000-000000000000")
    assert unknown["count"] == 0
