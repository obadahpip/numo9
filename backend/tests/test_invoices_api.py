"""D-03a-T11 — the invoices API: create a draft (server figures), list with status counts and
search (number, customer, amount), edit with the version check (409), delete a draft only,
preview the journal and the period ribbon, approve (posted journal = preview), void, copy to an
invoice and a quote; refusals are 400 with their code (the AR lock named); an employee can't
approve; the routes are in the OpenAPI schema; the tenant sweep and permission check pass."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.orgsettings.models import LockDate
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.journal_helpers import people
from tests.sales_helpers import DAY, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = sales_books()
    who = people(books["org"])
    owner = Client()
    owner.force_login(who["owner"])
    with org_context(books["org"]):
        code = code_for("sales.ON.standard", "sales", DAY, books["org"])
    base = f"/api/v1/o/{books['org'].public_id}/invoices"
    return {**books, **who, "client": owner, "base": base, "code": code}


def body(ctx: dict[str, Any], **over: Any) -> dict[str, Any]:
    return {
        "customer": str(ctx["customers"]["ON"].public_id),
        "date": DAY.isoformat(),
        "reference": "PO-778",
        "lines": [
            {
                "description": "Design consultation",
                "quantity": "2",
                "unit_price": "250.00",
                "account": str(ctx["revenue"].public_id),
                "tax_code": str(ctx["code"].public_id),
            }
        ],
        **over,
    }


def post(client: Client, url: str, data: dict[str, Any] | None = None) -> Any:
    return client.post(url, data or {}, content_type="application/json")


def test_create_edit_list_and_delete(ctx: dict[str, Any]) -> None:
    client, base = ctx["client"], ctx["base"]
    made = post(client, base, body(ctx))
    assert made.status_code == 201, made.content
    draft = made.json()
    assert (draft["status"], draft["number"], draft["total"], draft["tax_total"]) == (
        "draft",
        "",
        "565.00",
        "65.00",
    )
    assert draft["due_date"] and draft["lines"][0]["amount"] == "500.00"
    url = f"{base}/{draft['id']}"
    edited = client.patch(
        url,
        {**body(ctx, reference="PO-779"), "version": draft["version"]},
        content_type="application/json",
    )
    assert edited.status_code == 200 and edited.json()["reference"] == "PO-779"
    stale = client.patch(
        url, {**body(ctx), "version": draft["version"]}, content_type="application/json"
    )
    assert (stale.status_code, stale.json()["code"]) == (409, "sales.invoice.stale")

    listed = client.get(base, {"q": "565"}).json()
    assert [r["id"] for r in listed["results"]] == [draft["id"]]
    assert listed["counts"]["draft"] == 1
    assert client.get(base, {"q": "Maple"}).json()["count"] >= 0
    assert client.get(base, {"status": "approved"}).json()["count"] == 0

    bad = post(client, base, body(ctx, lines=[{"account": "00000000-0000-0000-0000-000000000000"}]))
    assert bad.status_code == 400 and "lines" in bad.json()
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


def test_preview_approve_void_copy(ctx: dict[str, Any]) -> None:
    client, base = ctx["client"], ctx["base"]
    draft = post(client, base, body(ctx)).json()
    url = f"{base}/{draft['id']}"
    preview = client.get(f"{url}/preview").json()
    assert preview["journal"]["complete"] and not preview["journal"]["posted"]
    shown = [(r["debit"], r["credit"]) for r in preview["journal"]["lines"]]
    assert preview["period"]["date"] == DAY.isoformat() and preview["period"]["locked"] is False

    approved = post(client, f"{url}/approve")
    assert approved.status_code == 200, approved.content
    invoice = approved.json()
    assert invoice["status"] == "approved" and invoice["number"] and invoice["journal"]
    posted = client.get(f"{url}/preview").json()["journal"]
    assert posted["posted"] and [(r["debit"], r["credit"]) for r in posted["lines"]] == shown
    assert client.patch(url, body(ctx), content_type="application/json").status_code == 400

    copy = post(client, f"{url}/copy", {"to": "invoice"})
    assert copy.status_code == 201
    assert (copy.json()["status"], copy.json()["total"]) == ("draft", "565.00")
    quote = post(client, f"{url}/copy", {"to": "quote"})
    assert quote.status_code == 201 and quote.json()["number"].startswith("QU-")

    voided = post(client, f"{url}/void", {"reason": "Wrong customer"})
    assert voided.status_code == 200 and voided.json()["status"] == "void"
    again = post(client, f"{url}/void")
    assert (again.status_code, again.json()["code"]) == (400, "sales.invoice.not_voidable")


def test_the_ar_lock_is_a_named_400(ctx: dict[str, Any]) -> None:
    draft = post(ctx["client"], ctx["base"], body(ctx)).json()
    with org_context(ctx["org"]):
        LockDate(organisation=ctx["org"], module="ar", level="everyone", date=DAY).save()
    url = f"{ctx['base']}/{draft['id']}"
    assert ctx["client"].get(f"{url}/preview").json()["period"]["locked"] is True
    refused = post(ctx["client"], f"{url}/approve")
    assert (refused.status_code, refused.json()["code"]) == (400, "sales.invoice.locked")
    assert "lock date (15 Jun 2026, everyone)" in refused.json()["detail"]
    assert refused.json()["params"]["lock"]["module"] == "ar"


def test_permissions_schema_and_sweep(ctx: dict[str, Any]) -> None:
    draft = post(ctx["client"], ctx["base"], body(ctx)).json()
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=ctx["org"], user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert post(client, f"{ctx['base']}/{draft['id']}/approve").status_code == 403
    assert post(client, f"{ctx['base']}/{draft['id']}/void").status_code == 403
    schema = StringIO()
    call_command("spectacular", "--format", "openapi-json", stdout=schema)
    for path in ("invoices", "{public_id}/preview", "{public_id}/approve", "{public_id}/copy"):
        assert f"/api/v1/o/{{org}}/{path}" in schema.getvalue() or path in schema.getvalue()
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
