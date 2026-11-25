"""C-06-T07 — period close API: timeline (modules × months with status), checklist, close,
year-end, reopen (adviser); permissions ``accounting.period_close.*`` (an employee gets 403);
the tenant sweep passes."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.tenancy.models import OrganisationMember
from tests.period_close_helpers import close_books, post

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    import datetime as dt

    books = close_books()
    post(books, dt.date(2026, 3, 10), "bank", "revenue", "40000")
    clients = {}
    for key in ("owner", "adviser"):
        client = Client()
        client.force_login(books[key])
        clients[key] = client
    return {
        **books,
        **{f"{k}_client": v for k, v in clients.items()},
        "base": f"/api/v1/o/{books['org'].public_id}/period-close/",
    }


def send(client: Client, url: str, body: dict[str, Any]) -> Any:
    return client.post(url, body, content_type="application/json")


def test_close_timeline_checklist_year_end_reopen(ctx: dict[str, Any]) -> None:
    base, owner, adviser = ctx["base"], ctx["owner_client"], ctx["adviser_client"]
    made = send(owner, f"{base}close", {"module": "gl", "period_end": "2026-06-30"})
    assert made.status_code == 201, made.content
    assert made.json()["closed_by"]["name"] == "Dana Lee"
    bad = send(owner, f"{base}close", {"module": "gl", "period_end": "2026-05-31"})
    assert bad.status_code == 400 and bad.json()["code"] == "ledger.close.out_of_order"
    line = owner.get(base, {"year": "2026"}).json()
    gl = next(m for m in line["modules"] if m["module"] == "gl")
    assert [m["status"] for m in gl["months"]][:7] == ["closed"] * 6 + ["open"]
    assert line["fiscal_year"] == {"start": "2026-01-01", "end": "2026-12-31"}
    assert line["is_adviser"] is False
    checklist = owner.get(f"{base}checklist", {"period_end": "2026-06-30"}).json()
    assert {i["key"] for i in checklist["items"]} == {
        "drafts",
        "awaiting_approval",
        "unfiled_tax",
        "exceptions",
    }
    year = send(owner, f"{base}year-end", {"fiscal_year_end": "2026-12-31"})
    assert year.status_code == 201, year.content
    assert {e["book"] for e in year.json()["entries"]} == {"accounting", "tax"}
    refused = send(owner, f"{base}{year.json()['id']}/reopen", {"reason": "x"})
    assert refused.status_code == 400 and refused.json()["code"] == "ledger.close.adviser_only"
    done = send(adviser, f"{base}{year.json()['id']}/reopen", {"reason": "Audit adjustment"})
    assert done.status_code == 200 and done.json()["reason"] == "Audit adjustment"
    assert adviser.get(base, {"year": "2026"}).json()["is_adviser"] is True


def test_permissions_and_sweep(ctx: dict[str, Any]) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=ctx["org"], user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert client.get(ctx["base"]).status_code == 403
    assert (
        send(
            client, f"{ctx['base']}close", {"module": "gl", "period_end": "2026-06-30"}
        ).status_code
        == 403
    )
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
