"""D-02-T11 — the quotes API: create a draft with an optional line and an alternative group
(server figures of the counted lines), edit with the version check (409), the side check (a
purchase tax code is a 400 naming the line), list with counts per status equal to the tabs'
(the same enum, gap-05), delete a draft only; send without email (a public link), accept,
convert to an invoice (201), revise (the old link says "superseded"), decline; the public link's
preview / accept / decline / pdf endpoints without signing in (revoked → 410); permissions,
OpenAPI, tenant sweep and permission check."""

from __future__ import annotations

import base64
import datetime as dt
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.sales.models import QuoteLink
from numo9.sales.quote_links import link_token
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.journal_helpers import people
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db
TODAY = dt.date.today()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = sales_books()
    who = people(books["org"])
    owner = Client()
    owner.force_login(who["owner"])
    with org_context(books["org"]):
        code = code_for("sales.ON.standard", "sales", TODAY, books["org"])
        purchase = code_for("purchase.ON.standard", "purchase", TODAY, books["org"])
    base = f"/api/v1/o/{books['org'].public_id}/quotes"
    return {**books, **who, "client": owner, "base": base, "code": code, "purchase": purchase}


def line(ctx: dict[str, Any], price: str, **over: Any) -> dict[str, Any]:
    return {
        "description": over.pop("description", f"Line {price}"),
        "quantity": "1",
        "unit_price": price,
        "account": str(ctx["revenue"].public_id),
        "tax_code": str(ctx["code"].public_id),
        **over,
    }


def body(ctx: dict[str, Any], **over: Any) -> dict[str, Any]:
    return {
        "customer": str(ctx["customers"]["ON"].public_id),
        "date": TODAY.isoformat(),
        "title": "Kitchen renovation",
        "deposit_type": "percent",
        "deposit_value": "20",
        "lines": [
            line(ctx, "1000", description="Cabinets"),
            line(ctx, "200", description="Install", is_optional=True),
            line(ctx, "500", description="Oak", alternative_group="Wood"),
            line(ctx, "800", description="Walnut", alternative_group="Wood", selected=False),
        ],
        **over,
    }


def post(client: Client, url: str, data: dict[str, Any] | None = None) -> Any:
    return client.post(url, data or {}, content_type="application/json")


def test_create_edit_list_delete(ctx: dict[str, Any]) -> None:
    client, base = ctx["client"], ctx["base"]
    made = post(client, base, body(ctx))
    assert made.status_code == 201, made.content
    quote = made.json()
    assert (quote["status"], quote["number"]) == ("draft", "QU-0001")
    assert quote["expiry_date"] == (TODAY + dt.timedelta(days=30)).isoformat()
    assert [
        (x["is_optional"], x["alternative_group"], x["selected"], x["counted"])
        for x in quote["lines"]
    ] == [
        (False, "", True, True),
        (True, "", False, False),
        (False, "Wood", True, True),
        (False, "Wood", False, False),
    ]
    assert (quote["total"], quote["tax_total"], quote["deposit_amount"]) == (
        "1695.00",
        "195.00",
        "339.00",
    )
    url = f"{base}/{quote['id']}"
    edited = client.patch(
        url,
        {**body(ctx, title="Kitchen v2"), "version": quote["version"]},
        content_type="application/json",
    )
    assert edited.status_code == 200 and edited.json()["title"] == "Kitchen v2"
    stale = client.patch(
        url, {**body(ctx), "version": quote["version"]}, content_type="application/json"
    )
    assert (stale.status_code, stale.json()["code"]) == (409, "sales.quote.stale")
    wrong = post(
        client, base, body(ctx, lines=[line(ctx, "10", tax_code=str(ctx["purchase"].public_id))])
    )
    assert wrong.status_code == 400 and wrong.json()["code"] == "documents.lines.invalid"
    assert wrong.json()["problems"][0]["line"] == 1
    both = post(
        client, base, body(ctx, lines=[line(ctx, "1", is_optional=True, alternative_group="A")])
    )
    assert both.status_code == 400 and "lines" in both.json()
    early = post(client, base, body(ctx, expiry_date=(TODAY - dt.timedelta(days=1)).isoformat()))
    assert early.status_code == 400 and "expiry_date" in early.json()

    listed = client.get(base).json()
    assert listed["counts"] == {
        "draft": 1,
        "sent": 0,
        "viewed": 0,
        "accepted": 0,
        "declined": 0,
        "expired": 0,
        "invoiced": 0,
    }
    assert listed["tabs"]["all"] == listed["count"] == 1 and listed["tabs"]["draft"] == 1
    assert client.get(base, {"q": "QU-0001"}).json()["count"] == 1
    assert client.get(base, {"tab": "sent"}).json()["count"] == 0
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


def test_lifecycle_actions_and_public_link(ctx: dict[str, Any], s3: str) -> None:
    client, base = ctx["client"], ctx["base"]
    quote = post(client, base, body(ctx)).json()
    url = f"{base}/{quote['id']}"
    assert post(client, f"{url}/link").json()["code"] == "sales.quote.not_sent"
    sent = post(client, f"{url}/send", {"email": False})
    assert sent.status_code == 200, sent.content
    assert sent.json()["status"] == "sent" and sent.json()["link"]["url"].count("/q/") == 1
    assert client.patch(url, body(ctx), content_type="application/json").status_code == 400
    counts = client.get(base).json()
    assert counts["tabs"]["sent"] == counts["counts"]["sent"] + counts["counts"]["viewed"] == 1

    with org_context(ctx["org"]):
        token = link_token(QuoteLink.objects.get(quote__public_id=quote["id"]))
    public = Client()  # signed out
    page = public.get(f"/api/v1/q/{token}").json()
    assert page["status"] == "viewed" and page["deposit"] == "339.00"
    optional = page["lines"][1]["id"]
    walnut = page["lines"][3]["id"]
    oak = page["lines"][2]["id"]
    preview = post(public, f"/api/v1/q/{token}/preview", {"selections": {optional: True}})
    assert preview.status_code == 200 and preview.json()["total"] == "1921.00"
    swap = post(public, f"/api/v1/q/{token}/preview", {"selections": {oak: False, walnut: True}})
    assert swap.json()["total"] == "2034.00"
    assert public.get(f"/api/v1/q/{token}").json()["total"] == "1695.00"  # nothing saved
    assert public.get(f"/api/v1/q/{token}/pdf")["Content-Type"] == "application/pdf"
    unnamed = post(public, f"/api/v1/q/{token}/accept", {"typed_name": " "})
    assert (unnamed.status_code, unnamed.json()["code"]) == (400, "sales.quote.name_required")
    signature = "data:image/png;base64," + base64.b64encode(PNG).decode()
    accepted = post(
        public,
        f"/api/v1/q/{token}/accept",
        {"typed_name": "Jo Lee", "signature": signature, "selections": {optional: True}},
    )
    assert accepted.status_code == 200, accepted.content
    assert (accepted.json()["status"], accepted.json()["total"]) == ("accepted", "1921.00")
    assert accepted.json()["can_accept"] is False and accepted.json()["accepted_by"] == "Jo Lee"
    late = post(public, f"/api/v1/q/{token}/decline", {"reason": "Changed my mind"})
    assert (late.status_code, late.json()["code"]) == (400, "sales.quote.accepted")

    detail = client.get(url).json()
    assert detail["acceptance"]["typed_name"] == "Jo Lee" and detail["acceptance"]["signed"]
    assert detail["deposit_invoice"]["total"] == "384.20"  # 20 % of 1921.00
    invoice = post(client, f"{url}/invoice")
    assert invoice.status_code == 201, invoice.content
    assert invoice.json()["total"] == "1536.80"  # 1921.00 less the 384.20 deposit
    assert client.get(url).json()["status"] == "invoiced"
    assert post(client, f"{url}/invoice").json()["code"] == "sales.quote.not_accepted"

    other = post(client, base, body(ctx)).json()
    other_url = f"{base}/{other['id']}"
    post(client, f"{other_url}/send", {"email": False})
    revised = post(client, f"{other_url}/revise")
    assert revised.status_code == 201 and revised.json()["revises"]["id"] == other["id"]
    with org_context(ctx["org"]):
        old_token = link_token(QuoteLink.objects.get(quote__public_id=other["id"]))
    assert public.get(f"/api/v1/q/{old_token}").json()["reason"] == "superseded"
    assert client.get(other_url).json()["superseded_by"]["id"] == revised.json()["id"]
    declined = post(client, f"{other_url}/decline", {"reason": "Superseded"})
    assert declined.json()["status"] == "declined"
    assert client.delete(f"{other_url}/link").status_code == 200
    assert public.get(f"/api/v1/q/{old_token}").status_code == 410
    assert post(public, f"/api/v1/q/{old_token}/accept", {"typed_name": "X"}).status_code == 410
    assert public.get("/api/v1/q/nonsense/pdf").status_code == 404
    copy = post(client, f"{other_url}/copy", {"to": "quote"})
    assert copy.status_code == 201 and copy.json()["number"].startswith("QU-")


def test_public_decline_permissions_schema_and_sweep(ctx: dict[str, Any]) -> None:
    client, base = ctx["client"], ctx["base"]
    quote = post(client, base, body(ctx)).json()
    url = f"{base}/{quote['id']}"
    post(client, f"{url}/send", {"email": False})
    with org_context(ctx["org"]):
        token = link_token(QuoteLink.objects.get(quote__public_id=quote["id"]))
    declined = post(Client(), f"/api/v1/q/{token}/decline", {"reason": "Too dear"})
    assert declined.status_code == 200 and declined.json()["status"] == "declined"
    assert client.get(url).json()["decline_reason"] == "Too dear"

    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=ctx["org"], user=employee, role="employee")
    viewer = Client()
    viewer.force_login(employee)
    assert viewer.get(url).status_code == 403
    assert post(viewer, base, body(ctx)).status_code == 403
    assert post(viewer, f"{url}/revise").status_code == 403
    schema = StringIO()
    call_command("spectacular", "--format", "openapi-json", stdout=schema)
    for path in ("/quotes", "{public_id}/invoice", "/q/{token}/accept", "/q/{token}/preview"):
        assert path in schema.getvalue()
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
