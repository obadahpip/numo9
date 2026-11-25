"""C-07-T09 — find & recode API: search, preview, execute, batches, undo, report; permission
``accounting.recode`` (owners and the advisers' roles; sales or employees get 403); OpenAPI;
the tenant sweep passes."""

from __future__ import annotations

import csv
import datetime as dt
import io
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.models import RecodeLineChange
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import LockDate
from numo9.rbac.system_roles import system_role
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = recode_books()
    clients = {}
    for key in ("owner", "adviser"):
        client = Client()
        client.force_login(books[key])
        clients[key] = client
    return {**books, "clients": clients, "base": f"/api/v1/o/{books['org'].public_id}/recode/"}


def send(client: Client, url: str, body: dict[str, Any]) -> Any:
    return client.post(url, body, content_type="application/json")


def on(ctx: dict[str, Any], key: str) -> dict[str, Any]:
    return {"conditions": [{"field": "account", "op": "is", "value": str(ctx[key].public_id)}]}


def test_search_preview_execute_undo_report(ctx: dict[str, Any]) -> None:
    base, adviser = ctx["base"], ctx["clients"]["adviser"]
    found = send(adviser, f"{base}search", {"criteria": on(ctx, "expense"), "page_size": 1})
    assert found.status_code == 200, found.content
    body = found.json()
    assert body["count"] == 2 and len(body["lines"]) == 1 and len(body["keys"]) == 2
    assert body["lines"][0]["account"]["label"] == str(ctx["expense"])
    assert body["lines"][0]["fingerprint"] == body["keys"][0]["fingerprint"]

    changes = {"account": str(ctx["expense2"].public_id)}
    shown = send(
        adviser,
        f"{base}preview",
        {"criteria": on(ctx, "expense"), "changes": changes, "selection": body["keys"]},
    )
    assert shown.status_code == 200, shown.content
    preview = shown.json()
    assert preview["summary"]["lines"] == 2 and preview["summary"]["totals_unchanged"] is True
    assert preview["lines"][0]["number"].startswith("JE-")
    assert preview["totals_before"] == preview["totals_after"]

    ran = send(
        adviser,
        f"{base}execute",
        {
            "criteria": on(ctx, "expense"),
            "changes": changes,
            "selection": body["keys"],
            "name": "Supplies to rent",
        },
    )
    assert ran.status_code == 201, ran.content
    batch = ran.json()
    assert batch["status"] == "completed" and batch["line_count"] == 2
    assert batch["undo"] == {"allowed": True, "blocked": []}

    listed = adviser.get(f"{base}batches").json()["batches"]
    assert [b["id"] for b in listed] == [batch["id"]]

    report = adviser.get(f"{base}batches/{batch['id']}/report", {"export": "csv"})
    assert report.status_code == 200 and report["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(report.content.decode("utf-8-sig"))))
    assert len(rows) == 3
    assert adviser.get(f"{base}batches/{batch['id']}/report", {"export": "doc"}).status_code == 400

    undone = send(adviser, f"{base}batches/{batch['id']}/undo", {"reason": "Wrong account"})
    assert undone.status_code == 200, undone.content
    assert undone.json()["status"] == "undone" and undone.json()["undo"]["allowed"] is False
    again = send(adviser, f"{base}batches/{batch['id']}/undo", {})
    assert again.status_code == 400 and again.json()["code"] == "ledger.recode.undo_not_allowed"


def test_refusals_carry_codes(ctx: dict[str, Any]) -> None:
    base, owner = ctx["base"], ctx["clients"]["owner"]
    bad = send(owner, f"{base}search", {"criteria": {"conditions": [{"field": "colour"}]}})
    assert bad.status_code == 400 and bad.json()["code"] == "ledger.recode.condition_invalid"
    bad = send(owner, f"{base}preview", {"criteria": on(ctx, "expense"), "changes": {"x": 1}})
    assert bad.status_code == 400 and bad.json()["code"] == "ledger.recode.changes_invalid"
    tax = send(
        owner,
        f"{base}execute",
        {"criteria": on(ctx, "revenue"), "changes": {"tax_code": "sales.ON.zero"}},
    )
    assert tax.status_code == 400 and tax.json()["code"] == "ledger.recode.confirm_tax"


def test_undo_refused_lists_the_locked_entries(ctx: dict[str, Any]) -> None:
    base, adviser = ctx["base"], ctx["clients"]["adviser"]
    ran = send(
        adviser,
        f"{base}execute",
        {"criteria": on(ctx, "expense"), "changes": {"tracking": {"region": "north"}}},
    ).json()
    with org_context(ctx["org"]):
        LockDate(
            organisation=ctx["org"], module="gl", level="everyone", date=dt.date(2026, 3, 31)
        ).save()
    detail = adviser.get(f"{base}batches/{ran['id']}").json()
    assert detail["undo"]["allowed"] is False
    assert [b["code"] for b in detail["undo"]["blocked"]] == ["locked"]
    refused = send(adviser, f"{base}batches/{ran['id']}/undo", {})
    assert refused.status_code == 400 and refused.json()["code"] == "ledger.recode.undo_refused"
    assert len(refused.json()["blocked"]) == 1


def test_over_200_lines_is_accepted_as_a_job(ctx: dict[str, Any], sent: Any) -> None:
    with org_context(ctx["org"]):
        for n in range(51):
            amounts = [Decimal(f"{n + 1}.{i:02d}") for i in range(4)]
            post_journal(
                JournalSpec(
                    date=dt.date(2026, 5, 1 + n % 28),
                    narration=f"Bulk {n}",
                    lines=[
                        *(LineSpec(ctx["expense2"], debit=a) for a in amounts),
                        LineSpec(ctx["revenue"], credit=sum(amounts, Decimal("0"))),
                    ],
                ),
                user=ctx["adviser"],
            )
    criteria = {
        "conditions": [
            {"field": "account", "op": "is", "value": str(ctx["expense2"].public_id)},
            {"field": "reference", "op": "contains", "value": "Bulk"},
        ]
    }
    ran = send(
        ctx["clients"]["adviser"],
        f"{ctx['base']}execute",
        {"criteria": criteria, "changes": {"account": str(ctx["expense"].public_id)}},
    )
    assert ran.status_code == 202, ran.content
    assert ran.json()["status"] == "running" and ran.json()["job"]
    assert len(sent) == 1
    with org_context(ctx["org"]):
        assert RecodeLineChange.objects.count() == 0


def test_permissions_roles_and_sweep(ctx: dict[str, Any]) -> None:
    for role in ("employee", "sales", "purchasing"):
        person = User.objects.create_user(f"{role}@refined.ca", name=role)
        OrganisationMember.objects.create(organisation=ctx["org"], user=person, role=role)
        client = Client()
        client.force_login(person)
        assert client.get(f"{ctx['base']}batches").status_code == 403
        assert send(
            client, f"{ctx['base']}search", {"criteria": on(ctx, "expense")}
        ).status_code == (403)
    assert "accounting.recode" in system_role("practice", "accountant").permission_keys()
    assert (
        "accounting.recode" in system_role("organisation", "accountant_delegate").permission_keys()
    )
    assert "accounting.recode" not in system_role("practice", "reviewer").permission_keys()
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())


def test_openapi_lists_the_routes() -> None:
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)  # type: ignore[no-untyped-call]
    paths = schema["paths"]
    for route in (
        "search",
        "preview",
        "execute",
        "batches",
        "batches/{public_id}",
        "batches/{public_id}/undo",
        "batches/{public_id}/report",
    ):
        assert f"/api/v1/o/{{org}}/recode/{route}" in paths
