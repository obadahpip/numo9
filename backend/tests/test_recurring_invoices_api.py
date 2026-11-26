"""D-04-T07 — the recurring invoices API: CRUD (version check, edits apply to future occurrences),
pause / resume, the preview of the next invoice (equal to the invoice the generator then makes),
the history of generated invoices and skipped dates, the schedule panel's dates; a template that
approves needs the approve permission; the routes are in the OpenAPI schema; the tenant sweep
and the permission check pass."""

from __future__ import annotations

import datetime as dt
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client
from freezegun import freeze_time

from numo9.accounts.models import User
from numo9.sales.recurring_invoices import generate_due
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.journal_helpers import people
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db
D = dt.date
TODAY = "2026-06-10 15:00:00"  # 10 June in Toronto


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = sales_books()
    who = people(books["org"])
    owner = Client()
    owner.force_login(who["owner"])
    with org_context(books["org"]):
        code = code_for("sales.ON.standard", "sales", D(2026, 6, 15), books["org"])
    base = f"/api/v1/o/{books['org'].public_id}/recurring-invoices"
    return {**books, **who, "client": owner, "base": base, "code": code}


def body(ctx: dict[str, Any], **over: Any) -> dict[str, Any]:
    return {
        "name": "Monthly bookkeeping",
        "customer": str(ctx["customers"]["ON"].public_id),
        "reference": "Bookkeeping {{month}} {{year}}",
        "notes": "For {{period_start}} to {{period_end}}",
        "rrule": "FREQ=MONTHLY",
        "start_date": "2026-06-15",
        "mode": "draft",
        "lines": [
            {
                "description": "Bookkeeping — {{month}}",
                "quantity": "1",
                "unit_price": "300.00",
                "account": str(ctx["revenue"].public_id),
                "tax_code": str(ctx["code"].public_id),
            }
        ],
        **over,
    }


def post(client: Client, url: str, data: dict[str, Any] | None = None) -> Any:
    return client.post(url, data or {}, content_type="application/json")


def patch(client: Client, url: str, data: dict[str, Any]) -> Any:
    return client.patch(url, data, content_type="application/json")


@freeze_time(TODAY)
def test_create_edit_list_and_delete(ctx: dict[str, Any]) -> None:
    client, base = ctx["client"], ctx["base"]
    made = post(client, base, body(ctx, notes="{{montth}}"))
    assert made.status_code == 201, made.content
    template = made.json()
    assert (template["status"], template["next_run"], template["last_run"]) == (
        "active",
        "2026-06-15",
        None,
    )
    assert template["unknown_placeholders"] == ["montth"]
    assert template["lines"][0]["description"] == "Bookkeeping — {{month}}"
    url = f"{base}/{template['id']}"
    edited = patch(client, url, {**body(ctx, name="Bookkeeping"), "version": template["version"]})
    assert edited.status_code == 200 and edited.json()["version"] == template["version"] + 1
    stale = patch(client, url, {**body(ctx), "version": template["version"]})
    assert (stale.status_code, stale.json()["code"]) == (409, "sales.recurring.stale")

    later = patch(client, url, body(ctx, start_date="2026-01-31"))  # started in the past
    assert later.json()["next_run"] == "2026-06-30"  # from today on, the 31st clamped

    listed = client.get(base, {"q": "Bookkeeping"}).json()
    assert [r["id"] for r in listed["results"]] == [template["id"]]
    assert listed["counts"] == {"active": 1, "paused": 0, "ended": 0}
    assert client.get(base, {"status": "paused"}).json()["count"] == 0

    bad = post(client, base, body(ctx, rrule="FREQ=SOMETIMES"))
    assert bad.status_code == 400 and bad.json()["code"] == "ledger.recurring.rrule_invalid"
    backwards = post(client, base, body(ctx, end_date="2026-01-01"))
    assert backwards.status_code == 400
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


@freeze_time(TODAY)
def test_pause_resume_and_status_tabs(ctx: dict[str, Any]) -> None:
    client, base = ctx["client"], ctx["base"]
    template = post(client, base, body(ctx)).json()
    url = f"{base}/{template['id']}"
    paused = post(client, f"{url}/pause").json()
    assert (paused["status"], paused["paused"]) == ("paused", True)
    assert client.get(base, {"status": "paused"}).json()["count"] == 1
    resumed = post(client, f"{url}/resume").json()
    assert (resumed["status"], resumed["next_run"]) == ("active", "2026-06-15")
    ended = post(client, base, body(ctx, start_date="2026-01-15", end_date="2026-02-15")).json()
    assert ended["status"] == "ended" and ended["next_run"] is None
    assert client.get(base).json()["counts"] == {"active": 1, "paused": 0, "ended": 1}


@freeze_time(TODAY)
def test_preview_equals_the_generated_invoice(ctx: dict[str, Any]) -> None:
    client, base, org = ctx["client"], ctx["base"], ctx["org"]
    template = post(
        client, base, body(ctx, prorate=True, service_start="2026-06-20", mode="draft")
    ).json()
    url = f"{base}/{template['id']}"
    shown = client.get(f"{url}/preview").json()
    invoice = shown["invoice"]
    assert shown["dates"][:3] == ["2026-06-15", "2026-07-15", "2026-08-15"]
    assert invoice["date"] == "2026-06-15"
    assert invoice["reference"] == "Bookkeeping June 2026"
    assert invoice["notes"] == "For 15 Jun 2026 to 14 Jul 2026"
    assert invoice["proration"] == {"covered": 25, "days": 30, "full": False}
    assert invoice["lines"][0]["net"] == "250.00"  # 25 of 30 days of 300.00
    assert invoice["skip"] is None
    with org_context(org):
        from numo9.sales.models import Invoice

        assert Invoice.objects.count() == 0  # the preview kept nothing

    generate_due(org, D(2026, 6, 15))
    history = client.get(f"{url}/history").json()
    assert history["counts"] == {"created": 1, "skipped": 0}
    (run,) = history["results"]
    assert (run["date"], run["status"]) == ("2026-06-15", "created")
    made = client.get(f"/api/v1/o/{org.public_id}/invoices/{run['invoice']['id']}").json()
    for key in ("date", "due_date", "reference", "notes", "subtotal", "tax_total", "total"):
        assert made[key] == invoice[key], key
    assert [{k: v for k, v in line.items() if k != "id"} for line in made["lines"]] == invoice[
        "lines"
    ]

    listed = client.get(base).json()["results"][0]
    assert (listed["generated"], listed["skipped"], listed["last_run"]) == (
        1,
        0,
        "2026-06-15",
    )
    assert listed["next_run"] == "2026-07-15"
    other = client.get(f"{url}/preview", {"date": "2026-08-15"}).json()["invoice"]
    assert other["reference"] == "Bookkeeping August 2026"
    wrong = client.get(f"{url}/preview", {"date": "2026-08-16"})
    assert (wrong.status_code, wrong.json()["code"]) == (400, "sales.recurring.not_an_occurrence")


@freeze_time(TODAY)
def test_schedule_panel_dates(ctx: dict[str, Any]) -> None:
    answer = post(
        ctx["client"],
        f"{ctx['base']}/schedule",
        {"rrule": "FREQ=MONTHLY", "start_date": "2026-01-31", "count": 3},
    )
    assert answer.json() == {"dates": ["2026-06-30", "2026-07-31", "2026-08-31"]}
    bad = post(ctx["client"], f"{ctx['base']}/schedule", {"rrule": "x", "start_date": "2026-01-01"})
    assert bad.status_code == 400


@freeze_time(TODAY)
def test_permissions_schema_and_sweep(ctx: dict[str, Any]) -> None:
    template = post(ctx["client"], ctx["base"], body(ctx)).json()
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=ctx["org"], user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert client.get(ctx["base"]).status_code in (200, 403)
    refused = post(client, ctx["base"], body(ctx, mode="approve_send"))
    assert refused.status_code == 403
    approver = post(ctx["client"], ctx["base"], body(ctx, mode="approve_send"))
    assert approver.status_code == 201, approver.content
    assert ctx["client"].get(f"{ctx['base']}/{template['id']}/history").status_code == 200
    schema = StringIO()
    call_command("spectacular", "--format", "openapi-json", stdout=schema)
    for path in (
        "recurring-invoices",
        "recurring-invoices/{public_id}/preview",
        "recurring-invoices/{public_id}/history",
        "recurring-invoices/{public_id}/pause",
    ):
        assert f"/api/v1/o/{{org}}/{path}" in schema.getvalue(), path
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
