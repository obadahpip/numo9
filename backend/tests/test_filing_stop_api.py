"""G-03b-T08, T09 — stop/restart API: the impact preview equals the saved result (and writes
nothing); ``stop`` needs the registration number typed; ``restart``; ``events`` with the person
of each change; ``tax.manage`` to change (an employee gets 403); the tenant sweep passes."""

from __future__ import annotations

import datetime as dt
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.orgsettings.models import TaxRegistration
from numo9.tax.models import FilingPeriod, RegistrationStatusEvent
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
STOP = {
    "action": "stop",
    "date": "2026-06-30",
    "reason_code": "deregistration",
    "reason_text": "Sold",
}


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = sales_books()
    org = books["org"]
    owner = User.objects.create_user("owner@refined.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    with org_context(org):
        reg = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2026, 1, 1),
        )
        reg.save()
    client = Client()
    client.force_login(owner)
    base = f"/api/v1/o/{org.public_id}/tax/registrations/{reg.public_id}/"
    made = client.post(
        f"{base}cycles",
        {"frequency": "quarterly", "effective_from": "2026-01-01"},
        content_type="application/json",
    )
    assert made.status_code == 201, made.content
    return {**books, "reg": reg, "owner": owner, "client": client, "base": base}


def post(
    ctx: dict[str, Any], suffix: str, body: dict[str, Any], client: Client | None = None
) -> Any:
    return (client or ctx["client"]).post(
        ctx["base"] + suffix, body, content_type="application/json"
    )


def bare(result: dict[str, Any]) -> dict[str, Any]:
    def strip(row: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in row.items() if k != "id"}

    return {
        "removed": [strip(r) for r in result["removed"]],
        "added": [strip(r) for r in result["added"]],
        "periods": [strip(r) for r in result["periods"]],
        "documents": result["documents"],
        "out_of_scope_default": result["out_of_scope_default"],
    }


def test_stop_preview_equals_the_result(ctx: dict[str, Any]) -> None:
    late = draft(ctx, [("1", "100", "sales.ON.standard")], date=dt.date(2026, 7, 15))
    with org_context(ctx["org"]):
        count = FilingPeriod.objects.filter(registration=ctx["reg"]).count()
    preview = post(ctx, "preview", STOP)
    assert preview.status_code == 200, preview.content
    shown = preview.json()
    assert [d["id"] for d in shown["documents"]] == [str(late.public_id)]
    assert shown["out_of_scope_default"] is True
    with org_context(ctx["org"]):  # nothing written
        assert FilingPeriod.objects.filter(registration=ctx["reg"]).count() == count
        assert not RegistrationStatusEvent.objects.exists()
    ctx["reg"].refresh_from_db()
    assert ctx["reg"].effective_to is None
    body = {k: v for k, v in STOP.items() if k != "action"}
    wrong = post(ctx, "stop", {**body, "confirm_number": "123456782RT0002"})
    assert wrong.status_code == 422 and wrong.json()["code"] == "tax.filing.confirm_number"
    done = post(ctx, "stop", {**body, "confirm_number": "123456782 RT 0001"})
    assert done.status_code == 201, done.content
    assert bare(done.json()) == bare(shown)
    assert done.json()["stopped"] is True and done.json()["stop_date"] == "2026-06-30"


def test_restart_preview_events_and_refusals(ctx: dict[str, Any]) -> None:
    body = {k: v for k, v in STOP.items() if k != "action"}
    post(ctx, "stop", {**body, "confirm_number": "123456782RT0001"})
    restart = {"date": "2027-01-01", "frequency": "quarterly", "reason_text": "New shop"}
    early = post(ctx, "preview", {"action": "restart", **restart, "date": "2026-06-01"})
    assert early.status_code == 422 and early.json()["code"] == "tax.filing.restart_before_stop"
    shown = post(ctx, "preview", {"action": "restart", **restart}).json()
    done = post(ctx, "restart", restart)
    assert done.status_code == 201, done.content
    assert bare(done.json()) == bare(shown)
    assert done.json()["out_of_scope_default"] is False
    events = ctx["client"].get(ctx["base"] + "events").json()
    assert [(e["action"], e["date"], e["by"]["name"]) for e in events["events"]] == [
        ("stop", "2026-06-30", "Dana Lee"),
        ("restart", "2027-01-01", "Dana Lee"),
    ]
    assert events["events"][0]["reason_label"] == "Registration cancelled"
    assert events["gaps"] == [{"start": "2026-07-01", "end": "2026-12-31"}]
    assert events["stopped"] is False


def test_permissions_and_sweep(ctx: dict[str, Any]) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=ctx["org"], user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    body = {k: v for k, v in STOP.items() if k != "action"}
    assert (
        post(ctx, "stop", {**body, "confirm_number": "123456782RT0001"}, client).status_code == 403
    )
    assert (
        post(ctx, "restart", {"date": "2027-01-01", "frequency": "quarterly"}, client).status_code
        == 403
    )
    assert post(ctx, "preview", STOP, client).status_code == 403
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
