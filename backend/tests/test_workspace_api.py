"""V-01-T05 — ``GET /api/v1/practice/orgs`` (q, filters, sort, page, columns) + facet counts.

Acceptance: the contract follows the OpenAPI schema (every response here is validated against the
generated schema).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import jsonschema  # type: ignore[import-untyped]  # installed with drf-spectacular
import pytest
import yaml
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from numo9.tenancy.models import OrganisationStatus
from numo9.workspace.models import OrgDirectorySummary
from numo9.workspace.summary import rebuild_all
from tests.entitlement_helpers import package, subscribe
from tests.workspace_helpers import client_org, member, practice, user

pytestmark = pytest.mark.django_db

URL = "/api/v1/practice/orgs"
BN = "123456782"


@pytest.fixture(scope="module")
def schema(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    out: Path = tmp_path_factory.mktemp("schema") / "schema.yaml"
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(out))
    return yaml.safe_load(out.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _json_schema(node: Any) -> Any:
    """OpenAPI 3.0 → JSON Schema: ``nullable: true`` becomes a ``null`` type."""
    if isinstance(node, list):
        return [_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: _json_schema(value) for key, value in node.items() if key != "nullable"}
    if node.get("nullable") and "type" in out:
        out["type"] = [out["type"], "null"]
    return out


def conforms(schema: dict[str, Any], body: Any, component: str = "DirectoryPage") -> None:
    """Validate a response body against a component of the OpenAPI schema (all fields of the
    component are checked; unknown fields are refused too)."""
    components = _json_schema(schema["components"])
    for item in components["schemas"].values():
        if item.get("type") == "object" and "properties" in item:
            item["additionalProperties"] = False
    document = {"$ref": f"#/components/schemas/{component}", "components": components}
    jsonschema.validate(body, document)


@pytest.fixture
def world() -> dict[str, Any]:
    admin = user("oa@abuodeh.ca", "Obadah Abuodeh")
    firm = practice("Abuodeh CPA", admin)
    accountant = user("sam@abuodeh.ca", "Sam Patel")
    staff = member(firm, accountant)
    maple = client_org(
        firm,
        "Maple Leaf Supply Ltd.",
        staff=[staff],
        settings={"mailing_province": "ON", "mailing_postal_code": "M5V 2T6"},
        bn=BN,
    )
    subscribe(maple, package("growth", ["accounting", "payroll"], name="Growth"))
    trial = client_org(firm, "Érable Bakery Inc.", status=OrganisationStatus.TRIAL)
    client_org(firm, "Closed Corp.", status=OrganisationStatus.CANCELLED)
    rebuild_all()
    OrgDirectorySummary.objects.filter(organisation=trial).update(
        trial_ends_at=timezone.now() + timedelta(days=11, hours=3)
    )
    return locals()


def api(person: Any) -> APIClient:
    client = APIClient()
    client.force_authenticate(person)
    return client


def get(person: Any, **params: Any) -> Any:
    return api(person).get(URL, params)


def test_requires_sign_in() -> None:
    assert APIClient().get(URL).status_code in (401, 403)


def test_lists_the_practice_directory(world: dict[str, Any], schema: dict[str, Any]) -> None:
    response = get(world["admin"], practice=str(world["firm"].public_id))
    assert response.status_code == 200
    body = response.json()
    conforms(schema, body)
    assert body["practice"] == {"id": str(world["firm"].public_id), "name": "Abuodeh CPA"}
    assert (body["count"], body["total"], body["page"], body["pages"]) == (2, 2, 1, 1)
    maple = next(row for row in body["results"] if row["name"] == "Maple Leaf Supply Ltd.")
    assert maple["id"] == str(world["maple"].public_id)
    assert (maple["bn"], maple["province"], maple["package"], maple["package_name"]) == (
        BN,
        "ON",
        "growth",
        "Growth",
    )
    assert (maple["status"], maple["payroll_enabled"], maple["trial_days_left"]) == (
        "paid",
        True,
        None,
    )
    trial = next(row for row in body["results"] if row["status"] == "trial")
    assert trial["trial_days_left"] == 12  # 11 days 3 hours left: "Trial 12 d"
    assert set(body["facets"]) == {
        "package",
        "status",
        "province",
        "fye",
        "gst_cycle",
        "payroll",
        "overdue",
        "unfiled",
        "bn_missing",  # V-04-T07 dashboard drill-downs
        "lock_missing",
        "trial_ending",
        "mine",
        "tag",
        "group",  # V-02-T08
    }
    assert {"value": "ON", "label": "Ontario", "count": 1} in body["facets"]["province"]
    assert {"value": "growth", "label": "Growth", "count": 1} in body["facets"]["package"]
    assert {"value": "12", "label": "December", "count": 2} in body["facets"]["fye"]
    assert body["facets"]["payroll"][0] == {"value": "yes", "label": "Yes", "count": 2}


def test_practice_defaults_to_the_only_one(world: dict[str, Any]) -> None:
    assert get(world["accountant"]).json()["count"] == 1  # the one assigned organisation


def test_practice_header_is_accepted(world: dict[str, Any]) -> None:
    response = api(world["admin"]).get(URL, HTTP_X_NUMO9_PRACTICE=str(world["firm"].public_id))
    assert response.json()["count"] == 2


def test_several_practices_must_choose(world: dict[str, Any]) -> None:
    member(practice("Second CPA"), world["accountant"])
    response = get(world["accountant"])
    assert response.status_code == 400
    assert response.json()["code"] == "workspace.practice_required"
    chosen = get(world["accountant"], practice=str(world["firm"].public_id))
    assert chosen.json()["count"] == 1


@pytest.mark.parametrize("value", ["0d7b7b7e-0000-4000-8000-000000000000", "not-a-uuid"])
def test_unknown_practice_is_404(world: dict[str, Any], value: str) -> None:
    assert get(world["admin"], practice=value).status_code == 404


def test_someone_elses_practice_is_404(world: dict[str, Any]) -> None:
    outsider = user("x@other.ca")
    practice("Other CPA", outsider)
    assert get(outsider, practice=str(world["firm"].public_id)).status_code == 404
    assert get(user("nobody@x.ca")).status_code == 404  # no practice at all


def test_permission_is_checked(world: dict[str, Any]) -> None:
    with mock.patch("numo9.workspace.api.has_practice_perm", return_value=False):
        response = get(world["admin"])
    assert response.status_code == 403
    assert response.json()["code"] == "permission.denied"


def test_search_filters_sort_page_and_columns(
    world: dict[str, Any], schema: dict[str, Any]
) -> None:
    body = get(world["admin"], q="123 456").json()
    assert [row["name"] for row in body["results"]] == ["Maple Leaf Supply Ltd."]
    body = get(world["admin"], status=["trial", "paid"], sort="status,name").json()
    assert [row["status"] for row in body["results"]] == ["paid", "trial"]
    body = get(world["admin"], archived="include", province="ON").json()
    assert body["count"] == 1 and body["total"] == 3
    body = get(
        world["admin"], sort="name", page=2, page_size=1, columns="bn,status", facets="0"
    ).json()
    conforms(schema, body)
    assert "facets" not in body
    assert body["columns"] == ["bn", "status"]
    assert (body["page"], body["pages"], body["count"]) == (2, 2, 2)
    (row,) = body["results"]
    assert set(row) == {"id", "name", "bn", "status", "trial_ends_at", "trial_days_left"}


@pytest.mark.parametrize(
    ("params", "field", "code"),
    [
        ({"status": "active"}, "status", "workspace.bad_filter"),
        ({"province": "XX"}, "province", "workspace.bad_filter"),
        ({"fye": "13"}, "fye", "workspace.bad_filter"),
        ({"payroll": "maybe"}, "payroll", "workspace.bad_filter"),
        ({"archived": "all"}, "archived", "workspace.bad_filter"),
        ({"sort": "-secret"}, "sort", "workspace.bad_sort"),
        ({"columns": "name,sin"}, "columns", "workspace.bad_column"),
        ({"page_size": "2001"}, "page_size", "workspace.bad_page"),
        ({"page": "0"}, "page", "workspace.bad_page"),
        ({"page": "x"}, "page", "workspace.bad_page"),
    ],
)
def test_invalid_parameters_are_refused(
    world: dict[str, Any], params: dict[str, str], field: str, code: str
) -> None:
    response = get(world["admin"], **params)
    assert response.status_code == 400
    body = response.json()
    assert (body["field"], body["code"]) == (field, code)
    assert body["detail"]


def test_documented_in_openapi(schema: dict[str, Any]) -> None:
    operation = schema["paths"][URL]["get"]
    assert operation["operationId"] == "practice_orgs_list"
    names = {p["name"] for p in operation["parameters"]}
    assert {"practice", "q", "province", "fye", "sort", "page", "page_size", "columns"} <= names
    assert set(schema["paths"]["/api/v1/practice/views"]) == {"get", "post"}  # V-01-T08
    assert set(schema["paths"]["/api/v1/practice/views/{view_id}"]) == {"patch", "delete"}
    assert schema["components"]["schemas"]["DirectoryStatusEnum"]["enum"] == [
        "trial",
        "paid",
        "demo",
        "read_only",
        "archived",
    ]


def test_french_labels(world: dict[str, Any]) -> None:
    body = api(world["admin"]).get(URL, HTTP_ACCEPT_LANGUAGE="fr-CA").json()
    labels = {item["value"]: item["label"] for item in body["facets"]["status"]}
    months = {item["value"]: item["label"] for item in body["facets"]["fye"]}
    assert months["12"].lower() == "décembre"
    assert labels["paid"]  # translated in the catalogue (fr-CA placeholder until Phase 6)
