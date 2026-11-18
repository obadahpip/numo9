"""V-02-T07 — APIs: groups CRUD/move, tags CRUD, assign orgs, assign staff.

Acceptance: Practice Admin only for structure changes — an accountant of the practice reads the
groups and tags but every change answers 403; a user of another practice gets 404 for the
practice, its groups and its tags. Also: the rules come back as 400 with the service's code and
the field (depth > 5, name taken, move into itself, unknown colour); moves, filing, staff and
tag assignments; the delete impact counts; the OpenAPI schema documents every endpoint.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from django.test import Client

from numo9.tenancy.models import PracticeRole
from numo9.workspace.groups import add_organisation, assign_staff, create_group
from numo9.workspace.models import GroupStaffAssignment, OrgGroup, OrgGroupMembership, OrgTag, Tag
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db

API = "/api/v1/practice"


def _browser(person: Any) -> Client:
    browser = Client()
    browser.force_login(person)
    return browser


class World:
    def __init__(self) -> None:
        self.admin_user = user("oa@abuodeh.ca", "Obadah Abuodeh")
        self.firm = practice("Abuodeh CPA", self.admin_user)
        self.sam = user("sam@abuodeh.ca", "Sam Patel")
        self.sam_member = member(self.firm, self.sam)
        self.maple = client_org(self.firm, "Maple Leaf Supply Ltd.")
        self.erable = client_org(self.firm, "Érable Bakery Inc.")
        self.admin = _browser(self.admin_user)
        self.accountant = _browser(self.sam)
        rival_admin = user("boss@rival.ca")
        self.rival = practice("Rival LLP", rival_admin)
        self.rival_org = client_org(self.rival, "Rival Client Inc.")
        self.outsider = _browser(rival_admin)
        self.p = str(self.firm.public_id)

    def post(self, browser: Client, path: str, body: dict[str, Any]) -> Any:
        return browser.post(f"{API}/{path}", body, content_type="application/json")

    def patch(self, browser: Client, path: str, body: dict[str, Any]) -> Any:
        return browser.patch(f"{API}/{path}", body, content_type="application/json")

    def put(self, browser: Client, path: str, body: dict[str, Any]) -> Any:
        return browser.put(f"{API}/{path}", body, content_type="application/json")


@pytest.fixture
def w() -> World:
    return World()


def test_openapi_documents_every_endpoint(w: World) -> None:
    paths = yaml.safe_load(w.admin.get("/api/schema/").content)["paths"]
    expected = {
        "/api/v1/practice/groups": {"get", "post"},
        "/api/v1/practice/groups/{group_id}": {"get", "patch", "delete"},
        "/api/v1/practice/groups/{group_id}/impact": {"get"},
        "/api/v1/practice/groups/{group_id}/organisations": {"post"},
        "/api/v1/practice/groups/{group_id}/organisations/{org_id}": {"delete"},
        "/api/v1/practice/groups/{group_id}/staff/{user_id}": {"put", "delete"},
        "/api/v1/practice/tags": {"get", "post"},
        "/api/v1/practice/tags/{tag_id}": {"patch", "delete"},
        "/api/v1/practice/tags/{tag_id}/organisations": {"post"},
        "/api/v1/practice/tags/{tag_id}/organisations/{org_id}": {"delete"},
    }
    for path, methods in expected.items():
        assert set(paths[path]) >= methods, path


def test_admin_builds_a_tree_and_files_organisations(w: World) -> None:
    toronto = w.post(w.admin, "groups", {"practice": w.p, "name": "Toronto office"})
    assert toronto.status_code == 201, toronto.json()
    tid = toronto.json()["id"]
    retail = w.post(w.admin, "groups", {"practice": w.p, "name": "Retail clients", "parent": tid})
    assert retail.status_code == 201
    assert retail.json()["parent"] == tid and retail.json()["depth"] == 2
    rid = retail.json()["id"]
    filed = w.post(
        w.admin,
        f"groups/{rid}/organisations",
        {"organisations": [str(w.maple.public_id), str(w.erable.public_id)]},
    )
    assert filed.status_code == 200 and filed.json() == {"count": 2}
    again = w.post(
        w.admin, f"groups/{rid}/organisations", {"organisations": [str(w.maple.public_id)]}
    )
    assert again.json() == {"count": 0}  # filing twice changes nothing
    listing = w.admin.get(f"{API}/groups", {"practice": w.p}).json()
    by_name = {g["name"]: g for g in listing["groups"]}
    assert [g["name"] for g in listing["groups"]] == ["Toronto office", "Retail clients"]
    assert by_name["Toronto office"]["subtree_organisation_count"] == 2
    assert by_name["Toronto office"]["organisation_count"] == 0
    assert by_name["Retail clients"]["organisation_count"] == 2
    removed = w.admin.delete(f"{API}/groups/{rid}/organisations/{w.erable.public_id}")
    assert removed.status_code == 204
    assert OrgGroupMembership.objects.filter(group__public_id=rid).count() == 1
    assert (
        w.admin.delete(f"{API}/groups/{rid}/organisations/{w.erable.public_id}").status_code == 404
    )


def test_rename_and_move(w: World) -> None:
    a = create_group(w.firm, "Toronto office")
    b = create_group(w.firm, "Ottawa office")
    child = create_group(w.firm, "Retail", a)
    moved = w.patch(
        w.admin, f"groups/{child.public_id}", {"parent": str(b.public_id), "name": "Shops"}
    )
    assert moved.status_code == 200, moved.json()
    assert moved.json()["parent"] == str(b.public_id) and moved.json()["name"] == "Shops"
    top = w.patch(w.admin, f"groups/{child.public_id}", {"parent": None})
    assert top.json()["parent"] is None and top.json()["depth"] == 1
    into_itself = w.patch(w.admin, f"groups/{b.public_id}", {"parent": str(b.public_id)})
    assert into_itself.status_code == 400
    assert into_itself.json()["code"] == "workspace.group.into_itself"
    assert into_itself.json()["field"] == "parent"


def test_rules_are_400_with_code_and_field(w: World) -> None:
    parent = None
    for level in range(5):
        parent = create_group(w.firm, f"Level {level + 1}", parent)
    assert parent is not None
    too_deep = w.post(
        w.admin, "groups", {"practice": w.p, "name": "Six", "parent": str(parent.public_id)}
    )
    assert too_deep.status_code == 400
    assert too_deep.json() | {"detail": ""} == {
        "detail": "",
        "code": "workspace.group.too_deep",
        "field": "name",
    }
    taken = w.post(w.admin, "groups", {"practice": w.p, "name": "level 1"})
    assert taken.json()["code"] == "workspace.group.name_taken"
    blank = w.post(w.admin, "tags", {"practice": w.p, "name": "  "})
    assert blank.json()["code"] == "workspace.tag.name_required"
    colour = w.post(w.admin, "tags", {"practice": w.p, "name": "VIP", "colour": "chartreuse"})
    assert colour.json()["code"] == "workspace.tag.colour"


def test_staff_assignment_and_detail(w: World) -> None:
    toronto = create_group(w.firm, "Toronto office")
    retail = create_group(w.firm, "Retail", toronto)
    add_organisation(retail, w.maple)
    put = w.put(
        w.admin, f"groups/{toronto.public_id}/staff/{w.sam.public_id}", {"role": "reviewer"}
    )
    assert put.status_code == 200 and put.json()["role"] == "reviewer"
    assert GroupStaffAssignment.objects.get(group=toronto).role == "reviewer"
    detail = w.admin.get(f"{API}/groups/{retail.public_id}").json()
    assert detail["organisations"] == [
        {"id": str(w.maple.public_id), "name": "Maple Leaf Supply Ltd."}
    ]
    assert detail["staff"][0]["inherited_from"] == {
        "id": str(toronto.public_id),
        "name": "Toronto office",
    }
    stranger = user("x@elsewhere.ca")
    assert (
        w.put(
            w.admin,
            f"groups/{toronto.public_id}/staff/{stranger.public_id}",
            {"role": "accountant"},
        ).status_code
        == 404
    )
    bad_role = w.put(
        w.admin, f"groups/{toronto.public_id}/staff/{w.sam.public_id}", {"role": "practice_admin"}
    )
    assert bad_role.status_code == 400
    assert (
        w.admin.delete(f"{API}/groups/{toronto.public_id}/staff/{w.sam.public_id}").status_code
        == 204
    )
    assert (
        w.admin.delete(f"{API}/groups/{toronto.public_id}/staff/{w.sam.public_id}").status_code
        == 404
    )


def test_delete_impact_and_delete(w: World) -> None:
    toronto = create_group(w.firm, "Toronto office")
    retail = create_group(w.firm, "Retail", toronto)
    add_organisation(retail, w.maple)
    add_organisation(toronto, w.erable)
    assign_staff(retail, w.sam_member)
    lee = member(w.firm, user("lee@abuodeh.ca", "Lee Wong"))
    assign_staff(toronto, lee)
    ottawa = create_group(w.firm, "Ottawa office")
    add_organisation(ottawa, w.maple)
    add_organisation(ottawa, w.erable)
    assign_staff(ottawa, lee)  # Lee keeps both clients through Ottawa
    impact = w.admin.get(f"{API}/groups/{toronto.public_id}/impact").json()
    assert impact == {
        "groups": 2,
        "organisations": 2,
        "staff_assignments": 2,
        "staff": 2,
        "staff_losing_access": 1,  # Sam only
    }
    assert w.admin.delete(f"{API}/groups/{toronto.public_id}").status_code == 204
    assert not OrgGroup.objects.filter(pk__in=[toronto.pk, retail.pk]).exists()
    assert GroupStaffAssignment.objects.filter(practice_member=lee).count() == 1


def test_tags_crud_and_tagging(w: World) -> None:
    created = w.post(w.admin, "tags", {"practice": w.p, "name": "Year-end soon", "colour": "amber"})
    assert created.status_code == 201
    body = created.json()
    assert body["colour_label"] == "Amber" and body["organisation_count"] == 0
    tid = body["id"]
    tagged = w.post(
        w.admin, f"tags/{tid}/organisations", {"organisations": [str(w.maple.public_id)]}
    )
    assert tagged.json() == {"count": 1}
    renamed = w.patch(w.admin, f"tags/{tid}", {"name": "YE soon", "colour": "red"})
    assert renamed.json()["name"] == "YE soon" and renamed.json()["organisation_count"] == 1
    listing = w.accountant.get(f"{API}/tags", {"practice": w.p}).json()
    assert [t["name"] for t in listing["tags"]] == ["YE soon"]
    assert w.admin.delete(f"{API}/tags/{tid}/organisations/{w.maple.public_id}").status_code == 204
    assert w.admin.delete(f"{API}/tags/{tid}").status_code == 204
    assert not Tag.objects.exists() and not OrgTag.objects.exists()


def test_structure_changes_are_practice_admin_only(w: World) -> None:
    group = create_group(w.firm, "Toronto office")
    tag = Tag.objects.create(practice=w.firm, name="VIP")
    org = str(w.maple.public_id)
    assert w.accountant.get(f"{API}/groups", {"practice": w.p}).status_code == 200
    assert w.accountant.get(f"{API}/groups/{group.public_id}").status_code == 200
    assert w.accountant.get(f"{API}/tags", {"practice": w.p}).status_code == 200
    refused = [
        w.post(w.accountant, "groups", {"practice": w.p, "name": "Mine"}),
        w.patch(w.accountant, f"groups/{group.public_id}", {"name": "Renamed"}),
        w.accountant.delete(f"{API}/groups/{group.public_id}"),
        w.accountant.get(f"{API}/groups/{group.public_id}/impact"),
        w.post(w.accountant, f"groups/{group.public_id}/organisations", {"organisations": [org]}),
        w.accountant.delete(f"{API}/groups/{group.public_id}/organisations/{org}"),
        w.put(
            w.accountant,
            f"groups/{group.public_id}/staff/{w.sam.public_id}",
            {"role": "accountant"},
        ),
        w.accountant.delete(f"{API}/groups/{group.public_id}/staff/{w.sam.public_id}"),
        w.post(w.accountant, "tags", {"practice": w.p, "name": "Mine"}),
        w.patch(w.accountant, f"tags/{tag.public_id}", {"name": "Renamed"}),
        w.accountant.delete(f"{API}/tags/{tag.public_id}"),
        w.post(w.accountant, f"tags/{tag.public_id}/organisations", {"organisations": [org]}),
        w.accountant.delete(f"{API}/tags/{tag.public_id}/organisations/{org}"),
    ]
    assert [r.status_code for r in refused] == [403] * len(refused)
    assert all(r.json()["code"] == "permission.denied" for r in refused)
    assert OrgGroup.objects.count() == 1 and Tag.objects.get().name == "VIP"
    w.sam_member.role = PracticeRole.PRACTICE_ADMIN
    w.sam_member.save()
    assert w.post(w.accountant, "groups", {"practice": w.p, "name": "Mine"}).status_code == 201


def test_another_practice_gets_404(w: World) -> None:
    group = create_group(w.firm, "Toronto office")
    tag = Tag.objects.create(practice=w.firm, name="VIP")
    assert w.outsider.get(f"{API}/groups", {"practice": w.p}).status_code == 404
    assert w.outsider.get(f"{API}/groups/{group.public_id}").status_code == 404
    assert w.outsider.delete(f"{API}/groups/{group.public_id}").status_code == 404
    assert w.patch(w.outsider, f"tags/{tag.public_id}", {"name": "x"}).status_code == 404
    # the admin can't file another practice's client, nor use another practice's group as parent
    rival_group = create_group(w.rival, "Rival group")
    filed = w.post(
        w.admin,
        f"groups/{group.public_id}/organisations",
        {"organisations": [str(w.rival_org.public_id)]},
    )
    assert filed.status_code == 404
    parent = w.post(
        w.admin, "groups", {"practice": w.p, "name": "X", "parent": str(rival_group.public_id)}
    )
    assert parent.status_code == 404
