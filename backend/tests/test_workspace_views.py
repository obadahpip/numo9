"""V-01-T08 — ``SavedView`` (user, practice, name, filters JSON, columns, sort, is_default) + API.

Acceptance: a view persists per user and is not visible to others (integration).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from numo9.workspace.models import SavedView
from numo9.workspace.views_api import MAX_VIEWS
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db

LIST = "/api/v1/practice/views"


def detail(view_id: str) -> str:
    return f"{LIST}/{view_id}"


@pytest.fixture
def world() -> dict[str, Any]:
    admin = user("oa@abuodeh.ca", "Obadah Abuodeh")
    firm = practice("Abuodeh CPA", admin)
    sam = user("sam@abuodeh.ca", "Sam Patel")
    member(firm, sam)
    return {"admin": admin, "firm": firm, "sam": sam}


def api(person: Any) -> APIClient:
    client = APIClient()
    client.force_authenticate(person)
    return client


ONTARIO_RETAIL = {
    "name": "Ontario retail",
    "filters": {
        "q": " retail ",
        "province": ["ON", "ON"],
        "status": ["paid"],
        "archived": "include",
    },
    "columns": ["name", "bn", "province", "province", "overdue"],
    "sort": ["-overdue", "name"],
    "density": "compact",
}


def create(person: Any, firm: Any, **body: Any) -> Any:
    return api(person).post(LIST, {"practice": str(firm.public_id), **body}, format="json")


def test_save_list_update_delete(world: dict[str, Any]) -> None:
    created = create(world["sam"], world["firm"], **ONTARIO_RETAIL)
    assert created.status_code == 201
    view = created.json()
    assert view["name"] == "Ontario retail"
    assert view["filters"] == {
        "q": "retail",
        "province": ["ON"],
        "status": ["paid"],
        "archived": "include",
    }
    assert view["columns"] == ["name", "bn", "province", "overdue"]
    assert (view["sort"], view["density"], view["is_default"]) == (
        ["-overdue", "name"],
        "compact",
        False,
    )
    assert view["practice"] == str(world["firm"].public_id)
    listed = api(world["sam"]).get(LIST, {"practice": str(world["firm"].public_id)}).json()
    assert [v["id"] for v in listed] == [view["id"]]

    changed = api(world["sam"]).patch(
        detail(view["id"]),
        {"name": "ON retail", "filters": {"province": ["ON", "QC"]}},
        format="json",
    )
    assert changed.status_code == 200
    assert changed.json()["name"] == "ON retail"
    assert changed.json()["filters"] == {"province": ["ON", "QC"]}
    assert changed.json()["columns"] == ["name", "bn", "province", "overdue"]  # untouched

    assert api(world["sam"]).delete(detail(view["id"])).status_code == 204
    assert not SavedView.objects.exists()


def test_persists_for_the_user_across_sessions(world: dict[str, Any]) -> None:
    """A new client (another browser, after logout/login) gets the same views."""
    create(world["sam"], world["firm"], name="Trials ending", filters={"status": ["trial"]})
    fresh = APIClient()
    fresh.force_login(world["sam"])
    names = [v["name"] for v in fresh.get(LIST).json()]  # the only practice: no parameter
    assert names == ["Trials ending"]


def test_never_visible_to_anyone_else(world: dict[str, Any]) -> None:
    view = create(world["sam"], world["firm"], name="Mine").json()
    # the practice admin of the same practice: not listed, not readable, not changeable
    admin = api(world["admin"])
    assert admin.get(LIST).json() == []
    assert admin.patch(detail(view["id"]), {"name": "Taken"}, format="json").status_code == 404
    assert admin.delete(detail(view["id"])).status_code == 404
    # a stranger, and the anonymous
    stranger = user("x@other.ca")
    practice("Other CPA", stranger)
    assert api(stranger).delete(detail(view["id"])).status_code == 404
    assert APIClient().get(LIST).status_code in (401, 403)
    assert SavedView.objects.get().name == "Mine"


def test_leaving_the_practice_hides_its_views(world: dict[str, Any]) -> None:
    view = create(world["sam"], world["firm"], name="Mine").json()
    world["firm"].members.filter(user=world["sam"]).delete()
    assert (
        api(world["sam"]).get(LIST, {"practice": str(world["firm"].public_id)}).status_code == 404
    )
    assert (
        api(world["sam"]).patch(detail(view["id"]), {"name": "x"}, format="json").status_code == 404
    )


def test_one_default_per_user_and_practice(world: dict[str, Any]) -> None:
    first = create(world["sam"], world["firm"], name="A", is_default=True).json()
    second = create(world["sam"], world["firm"], name="B", is_default=True).json()
    views = api(world["sam"]).get(LIST).json()
    assert [(v["name"], v["is_default"]) for v in views] == [("B", True), ("A", False)]
    api(world["sam"]).patch(detail(first["id"]), {"is_default": True}, format="json")
    views = api(world["sam"]).get(LIST).json()
    assert [(v["name"], v["is_default"]) for v in views] == [("A", True), ("B", False)]
    # someone else's default is their own business
    create(world["admin"], world["firm"], name="A", is_default=True)
    assert SavedView.objects.filter(is_default=True).count() == 2
    assert second["id"]


def test_names_unique_per_user_case_ignored(world: dict[str, Any]) -> None:
    create(world["sam"], world["firm"], name="Ontario retail")
    taken = create(world["sam"], world["firm"], name="ONTARIO RETAIL")
    assert taken.status_code == 400
    assert taken.json()["code"] == "workspace.view_name_taken"
    assert "ONTARIO RETAIL" in taken.json()["detail"]
    assert create(world["admin"], world["firm"], name="Ontario retail").status_code == 201
    with pytest.raises(IntegrityError), transaction.atomic():
        SavedView.objects.create(user=world["sam"], practice=world["firm"], name="ontario Retail")


def test_at_most_fifty_views(world: dict[str, Any]) -> None:
    SavedView.objects.bulk_create(
        SavedView(user=world["sam"], practice=world["firm"], name=f"View {i}")
        for i in range(MAX_VIEWS)
    )
    refused = create(world["sam"], world["firm"], name="One too many")
    assert refused.status_code == 400 and refused.json()["code"] == "workspace.view_limit"


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "x" * 81}, "name"),
        ({"name": "A", "filters": {"province": ["XX"]}}, "filters"),
        ({"name": "A", "filters": {"secret": ["1"]}}, "filters"),
        ({"name": "A", "filters": {"archived": "all"}}, "filters"),
        ({"name": "A", "columns": ["name", "sin"]}, "columns"),
        ({"name": "A", "sort": ["-password"]}, "sort"),
        ({"name": "A", "density": "huge"}, "density"),
    ],
)
def test_invalid_views_are_refused(world: dict[str, Any], body: dict[str, Any], field: str) -> None:
    response = create(world["sam"], world["firm"], **body)
    assert response.status_code == 400
    assert field in response.json()


def test_unknown_practice_and_view(world: dict[str, Any]) -> None:
    other = practice("Not mine")
    assert create(world["sam"], other, name="A").status_code == 404
    missing = "0d7b7b7e-0000-4000-8000-000000000000"
    assert api(world["sam"]).patch(detail(missing), {"name": "x"}, format="json").status_code == 404
