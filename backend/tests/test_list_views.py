"""D-09-T03 — saved views of an organisation's lists (per user, per list key) + API.

Acceptance: a view persists (API) — saved, listed again on another request, updated, made the
default (the previous default stops being one), deleted; personal (another member and another
organisation get 404); names unique per user and list; unknown lists and malformed filters are
refused; the directory's saved views (V-01) share the same rules (``saved_views.save_view``).
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from numo9.workspace.models import SavedListView
from numo9.workspace.saved_views import LIST_KEYS, MAX_VIEWS, clean_list_filters, register_list
from tests.auth_helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def world() -> dict[str, Any]:
    maple = Organisation.objects.create(name="Maple Fixtures Ltd.")
    pine = Organisation.objects.create(name="Pine Ridge Inc.")
    owner = make_user("dana@maple.ca", name="Dana Roy")
    clerk = make_user("sam@maple.ca", name="Sam Patel")
    OrganisationMember.objects.create(organisation=maple, user=owner, role=OrganisationRole.OWNER)
    OrganisationMember.objects.create(organisation=maple, user=clerk, role=OrganisationRole.SALES)
    OrganisationMember.objects.create(organisation=pine, user=owner, role=OrganisationRole.OWNER)
    return {"maple": maple, "pine": pine, "owner": owner, "clerk": clerk}


def api(person: Any) -> APIClient:
    client = APIClient()
    client.force_authenticate(person)
    return client


def url(org: Organisation, view_id: str | None = None) -> str:
    base = f"/api/v1/o/{org.public_id}/views"
    return f"{base}/{view_id}" if view_id else base


OVERDUE_BIG = {
    "list": "sales.invoices",
    "name": "Overdue over $5,000",
    "filters": {"tab": "overdue", "min_amount": "5000", "status": ["awaiting_payment"] * 2},
    "columns": ["number", "contact", "due_date", "amount_due", "amount_due"],
    "sort": ["-amount_due", "due_date"],
    "density": "compact",
}


def test_view_persists_and_is_listed_per_list(world: dict[str, Any]) -> None:
    client = api(world["clerk"])
    created = client.post(url(world["maple"]), OVERDUE_BIG, format="json")
    assert created.status_code == 201, created.content
    view = created.json()
    assert (view["list"], view["name"], view["density"], view["is_default"]) == (
        "sales.invoices",
        "Overdue over $5,000",
        "compact",
        False,
    )
    assert view["filters"] == {
        "tab": "overdue",
        "min_amount": "5000",
        "status": ["awaiting_payment"],
    }
    assert view["columns"] == ["number", "contact", "due_date", "amount_due"]
    assert view["sort"] == ["-amount_due", "due_date"]

    # A fresh client (another browser / after logging in again) lists it from the server.
    listed = api(world["clerk"]).get(url(world["maple"]), {"list": "sales.invoices"}).json()
    assert [v["id"] for v in listed] == [view["id"]]
    assert api(world["clerk"]).get(url(world["maple"], view["id"])).json()["name"] == view["name"]
    # Views of another list are separate.
    assert api(world["clerk"]).get(url(world["maple"]), {"list": "purchases.bills"}).json() == []


def test_update_default_and_delete(world: dict[str, Any]) -> None:
    client = api(world["clerk"])
    first = client.post(url(world["maple"]), {**OVERDUE_BIG, "is_default": True}, format="json")
    second = client.post(
        url(world["maple"]),
        {"list": "sales.invoices", "name": "Drafts", "filters": {"tab": "draft"}},
        format="json",
    ).json()
    # A same-named view on another list is fine; the default is per list.
    other = client.post(
        url(world["maple"]),
        {"list": "purchases.bills", "name": "Drafts", "is_default": True},
        format="json",
    )
    assert other.status_code == 201

    changed = client.patch(
        url(world["maple"], second["id"]),
        {"is_default": True, "name": "My drafts", "list": "purchases.bills"},
        format="json",
    )
    assert changed.status_code == 200
    assert (changed.json()["name"], changed.json()["list"]) == ("My drafts", "sales.invoices")
    listed = client.get(url(world["maple"]), {"list": "sales.invoices"}).json()
    assert [(v["name"], v["is_default"]) for v in listed] == [
        ("My drafts", True),
        ("Overdue over $5,000", False),
    ]
    bills = client.get(url(world["maple"]), {"list": "purchases.bills"}).json()
    assert [(v["name"], v["is_default"]) for v in bills] == [("Drafts", True)]

    assert client.delete(url(world["maple"], first.json()["id"])).status_code == 204
    assert [
        v["name"] for v in client.get(url(world["maple"]), {"list": "sales.invoices"}).json()
    ] == ["My drafts"]


def test_personal_and_organisation_scoped(world: dict[str, Any]) -> None:
    view = api(world["clerk"]).post(url(world["maple"]), OVERDUE_BIG, format="json").json()
    owner = api(world["owner"])
    # The organisation's owner neither lists nor opens, changes or deletes the clerk's view.
    assert owner.get(url(world["maple"]), {"list": "sales.invoices"}).json() == []
    for method in ("get", "patch", "delete"):
        assert (
            getattr(owner, method)(url(world["maple"], view["id"]), {}, format="json").status_code
            == 404
        )
    # Through another organisation's URL — even one the owner belongs to — it doesn't exist.
    assert owner.get(url(world["pine"], view["id"])).status_code == 404
    # Someone outside the organisation gets 404 for the whole list.
    stranger = make_user("lee@elsewhere.ca", name="Lee")
    assert api(stranger).get(url(world["maple"]), {"list": "sales.invoices"}).status_code == 404
    with org_context(world["maple"]):
        assert SavedListView.objects.filter(public_id=view["id"]).exists()


def test_names_unique_per_user_and_list(world: dict[str, Any]) -> None:
    client = api(world["clerk"])
    assert client.post(url(world["maple"]), OVERDUE_BIG, format="json").status_code == 201
    taken = client.post(
        url(world["maple"]), {**OVERDUE_BIG, "name": "overdue OVER $5,000"}, format="json"
    )
    assert taken.status_code == 400
    assert (taken.json()["code"], taken.json()["field"]) == ("workspace.view_name_taken", "name")
    # Another user may use the same name.
    assert (
        api(world["owner"]).post(url(world["maple"]), OVERDUE_BIG, format="json").status_code == 201
    )
    with org_context(world["maple"]), pytest.raises(IntegrityError), transaction.atomic():
        SavedListView.objects.create(
            organisation=world["maple"],
            user=world["clerk"],
            list_key="sales.invoices",
            name="OVERDUE over $5,000",
        )


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"list": "sales.nothing", "name": "x"}, "list"),
        ({"list": "sales.invoices", "name": "x", "filters": {"tab": {"nested": 1}}}, "filters"),
        ({"list": "sales.invoices", "name": "x", "filters": {"q": "x" * 201}}, "filters"),
        ({"list": "sales.invoices", "name": "x", "columns": ["Number; drop"]}, "columns"),
        ({"list": "sales.invoices", "name": "x", "sort": ["--total"]}, "sort"),
        ({"list": "sales.invoices", "name": ""}, "name"),
    ],
)
def test_refuses_bad_input(world: dict[str, Any], body: dict[str, Any], field: str) -> None:
    response = api(world["clerk"]).post(url(world["maple"]), body, format="json")
    assert response.status_code == 400
    assert field in response.json()


def test_list_query_must_name_a_known_list(world: dict[str, Any]) -> None:
    response = api(world["clerk"]).get(url(world["maple"]), {"list": "nope"})
    assert response.status_code == 400
    assert (response.json()["code"], response.json()["field"]) == ("workspace.unknown_list", "list")
    assert api(world["clerk"]).get(url(world["maple"])).status_code == 400


def test_limit_per_user_and_list(world: dict[str, Any]) -> None:
    with org_context(world["maple"]):
        SavedListView.objects.bulk_create(
            SavedListView(
                organisation=world["maple"],
                user=world["clerk"],
                list_key="purchases.bills",
                name=f"View {i}",
            )
            for i in range(MAX_VIEWS)
        )
    refused = api(world["clerk"]).post(
        url(world["maple"]), {"list": "purchases.bills", "name": "One more"}, format="json"
    )
    assert (refused.status_code, refused.json()["code"]) == (400, "workspace.view_limit")


def test_registered_list_keys_and_filter_cleaning() -> None:
    assert {"sales.invoices", "purchases.bills", "contacts"} <= set(LIST_KEYS)
    register_list("tests.widgets", LIST_KEYS["contacts"])
    try:
        assert "tests.widgets" in LIST_KEYS
    finally:
        LIST_KEYS.pop("tests.widgets")
    assert clean_list_filters(
        {"q": " maple ", "voided": True, "empty": "", "s": ["a", "a", " "]}
    ) == {
        "q": "maple",
        "voided": "true",
        "s": ["a"],
    }
    with pytest.raises(ValueError):
        clean_list_filters({"n": 1})


def test_sweep() -> None:
    call_command("tenant_sweep", stdout=StringIO())
