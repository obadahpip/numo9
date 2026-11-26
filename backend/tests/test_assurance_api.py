"""K-09-T20 — assurance API: summary, findings, workflow, fix, run, rules settings, heatmap;
feature key ``accounting.assurance.read``; permissions ``accounting.assurance.view`` /
``accounting.assurance.manage``; OpenAPI; the tenant sweep and the permission check pass.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.assurance.runner import run
from numo9.rbac.system_roles import system_role
from numo9.tenancy.models import OrganisationMember
from tests.assurance_helpers import NOW, at, refined
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = refined()
    with at(NOW):
        run(books["org"], now=NOW)
    staff = people(books["org"])
    clients = {}
    for key, user in (("owner", books["owner"]), ("adviser", staff["adviser"])):
        client = Client()
        client.force_login(user)
        clients[key] = client
    return {**books, "clients": clients, "base": f"/api/v1/o/{books['org'].public_id}/assurance/"}


def send(client: Client, url: str, body: dict[str, Any] | None = None, method: str = "post") -> Any:
    return getattr(client, method)(url, body or {}, content_type="application/json")


def test_summary_and_grouped_findings(ctx: dict[str, Any]) -> None:
    owner = ctx["clients"]["owner"]
    found = owner.get(ctx["base"])
    assert found.status_code == 200, found.content
    assert found.json()["score"] < 50 and found.json()["open"]["critical"] >= 3
    listing = owner.get(f"{ctx['base']}findings").json()
    rules = {f["rule"] for f in listing["findings"]}
    assert len(rules) >= 7  # the teardown shows at least seven rule groups
    assert listing["findings"][0]["severity"] == "critical"
    neg = next(f for f in listing["findings"] if f["rule"] == "NEG_CASH")
    assert neg["amount"] == "-994.17" and neg["has_fix"] is True
    assert neg["explanation"].startswith("Petty Cash went below zero")
    assert neg["source"]["kind"] == "account"
    only = owner.get(f"{ctx['base']}findings?severity=info").json()["findings"]
    assert {f["severity"] for f in only} <= {"info"}
    by_text = owner.get(f"{ctx['base']}findings?q=Petty").json()["findings"]
    assert {f["rule"] for f in by_text} == {"NEG_CASH"}


def test_workflow_fix_and_detail(ctx: dict[str, Any]) -> None:
    adviser, base = ctx["clients"]["adviser"], ctx["base"]
    findings = adviser.get(f"{base}findings").json()["findings"]
    neg = next(f for f in findings if f["rule"] == "NEG_CASH")
    backdated = next(f for f in findings if f["rule"] == "BACKDATED")
    proposal = adviser.get(f"{base}findings/{neg['id']}/fix").json()["fix"]
    assert [(x["code"], x["debit"]) for x in proposal["lines"]] == [
        ("1000", "994.17"),
        ("2900", "0.00"),
    ]
    made = send(adviser, f"{base}findings/{neg['id']}/fix")
    assert made.status_code == 201, made.content
    assert made.json()["draft"]["status"] == "draft"
    assert made.json()["finding"]["fix_entry"] == made.json()["draft"]["id"]
    assert adviser.get(f"{base}findings/{backdated['id']}/fix").json()["fix"] is None
    refused = send(adviser, f"{base}findings/{backdated['id']}/fix")
    assert refused.status_code == 400 and refused.json()["code"] == "assurance.fix.none"

    ack = send(adviser, f"{base}findings/{backdated['id']}/acknowledge", {"reason": "Imported"})
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    no_reason = send(adviser, f"{base}findings/{backdated['id']}/false-positive")
    assert no_reason.json()["code"] == "assurance.finding.reason_required"
    fp = send(
        adviser, f"{base}findings/{backdated['id']}/false-positive", {"reason": "Xero import"}
    )
    assert fp.json()["status"] == "false_positive"
    back = send(adviser, f"{base}findings/{backdated['id']}/reopen")
    assert back.json()["status"] == "open"
    detail = adviser.get(f"{base}findings/{backdated['id']}").json()
    # (the run was at the fixture's fixed clock, the clicks at the real one: compare as a set)
    assert {h["action"] for h in detail["history"]} == {
        "opened",
        "acknowledged",
        "false_positive",
        "reopened",
    }
    assert adviser.get(f"{base}findings/00000000-0000-4000-8000-000000000000").status_code == 404


def test_rules_settings_validated_and_used(ctx: dict[str, Any]) -> None:
    adviser, base = ctx["clients"]["adviser"], ctx["base"]
    rules = adviser.get(f"{base}rules").json()["rules"]
    backdated = next(r for r in rules if r["code"] == "BACKDATED")
    assert backdated["values"] == {"days": 7} and backdated["enabled"] is True
    bad = send(adviser, f"{base}rules/BACKDATED", {"params": {"days": 0}}, "patch")
    assert bad.status_code == 400 and bad.json()["param"] == "days"
    unknown = send(adviser, f"{base}rules/BACKDATED", {"params": {"weeks": 1}}, "patch")
    assert unknown.status_code == 400
    ok = send(
        adviser, f"{base}rules/BACKDATED", {"params": {"days": 30}, "severity": "info"}, "patch"
    )
    assert ok.status_code == 200 and ok.json()["values"] == {"days": 30}
    assert ok.json()["severity"] == "info"
    assert send(adviser, f"{base}rules/NOPE", {"enabled": False}, "patch").status_code == 404
    with at(NOW):
        run(ctx["org"], now=NOW)  # the next run uses the new N: journal 1 is 12 days late
    statuses = {
        f["rule"]: f["status"]
        for f in adviser.get(f"{base}findings?status=resolved").json()["findings"]
    }
    assert statuses.get("BACKDATED") == "resolved"


def test_run_heatmap_and_runs(ctx: dict[str, Any], sent: list[dict[str, Any]]) -> None:
    adviser, base = ctx["clients"]["adviser"], ctx["base"]
    started = send(adviser, f"{base}run")
    assert started.status_code == 202 and started.json()["job"]
    assert [m["task"] for m in sent] == ["numo9.assurance.run"]
    assert adviser.get(f"{base}runs").json()["runs"][0]["trigger"] == "manual"
    heat = adviser.get(f"{base}heatmap?days=30")
    assert heat.status_code == 200 and heat.json()["time_zone"] == "America/Toronto"
    assert adviser.get(f"{base}heatmap?user=nobody").json()["total"] == 0


def test_permissions_roles_and_sweep(ctx: dict[str, Any]) -> None:
    base = ctx["base"]
    for role in ("employee", "sales"):
        person = User.objects.create_user(f"{role}+{ctx['org'].pk}@refined.ca", name=role)
        OrganisationMember.objects.create(organisation=ctx["org"], user=person, role=role)
        client = Client()
        client.force_login(person)
        assert client.get(base).status_code == 403
        assert send(client, f"{base}run").status_code == 403
    reviewer = system_role("practice", "reviewer").permission_keys()
    assert "accounting.assurance.view" in reviewer
    assert "accounting.assurance.manage" not in reviewer
    for key in ("accountant", "practice_admin"):
        assert "accounting.assurance.manage" in system_role("practice", key).permission_keys()
    assert "accounting.assurance.manage" in system_role("organisation", "owner").permission_keys()
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())


def test_openapi_lists_the_routes() -> None:
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)  # type: ignore[no-untyped-call]
    paths = schema["paths"]
    for route in (
        "",
        "findings",
        "findings/{public_id}",
        "findings/{public_id}/acknowledge",
        "findings/{public_id}/false-positive",
        "findings/{public_id}/reopen",
        "findings/{public_id}/fix",
        "run",
        "runs",
        "rules",
        "rules/{code}",
        "heatmap",
    ):
        assert f"/api/v1/o/{{org}}/assurance/{route}" in paths, route
