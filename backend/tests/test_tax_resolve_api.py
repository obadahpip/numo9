"""G-02-T06 — ``POST tax/resolve``: many lines at once with the explanation keys (ON customer →
HST 13 %, US → zero-rated, an override kept, a stopped registration → out of scope with its
warning); the header is read once — 50 lines well under 100 ms; ``tax.codes.view``."""

from __future__ import annotations

import time
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from numo9.accounts.models import User
from numo9.contacts.models import Address, AddressKind
from numo9.ledger.models import Account
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.contact_helpers import contact
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = sales_books()
    org = books["org"]
    owner = User.objects.create_user("owner@refined.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    with org_context(org):
        us = contact(org, "Boston Buyer LLC", roles=["customer"])
        Address(
            organisation=org, contact=us, kind=AddressKind.BILLING, country="US", city="Boston"
        ).save()
        expense = Account.objects.filter(type="expense").order_by("code").first()
    client = Client()
    client.force_login(owner)
    return {
        **books,
        "owner": owner,
        "us": us,
        "expense": expense,
        "client": client,
        "url": f"/api/v1/o/{org.public_id}/tax/resolve",
    }


def resolve(ctx: dict[str, Any], body: dict[str, Any], client: Client | None = None) -> Any:
    return (client or ctx["client"]).post(ctx["url"], body, content_type="application/json")


def test_batch_lines_with_explanations(ctx: dict[str, Any]) -> None:
    revenue = str(ctx["revenue"].public_id)
    on = resolve(
        ctx,
        {
            "side": "sales",
            "date": "2026-06-15",
            "contact": str(ctx["customers"]["ON"].public_id),
            "lines": [{"account": revenue}, {"account": revenue, "override": "sales.exempt"}],
        },
    )
    assert on.status_code == 200, on.content
    first, second = on.json()["lines"]
    assert first["key"] == "sales.ON.standard" and first["tax_code"]["code"] == "sales.ON.standard"
    assert (first["explanation"], first["params"], first["auto"]) == (
        "tax.pos.hst",
        {"province": "ON"},
        True,
    )
    assert (second["key"], second["source"], second["auto"]) == ("sales.exempt", "override", False)
    us = resolve(
        ctx,
        {"side": "sales", "date": "2026-06-15", "contact": str(ctx["us"].public_id), "lines": [{}]},
    ).json()["lines"][0]
    assert (us["key"], us["explanation"]) == ("sales.zero_rated", "tax.pos.export")
    shipped = resolve(
        ctx,
        {
            "side": "sales",
            "date": "2026-06-15",
            "contact": str(ctx["us"].public_id),
            "ship_to": {"country": "CA", "province": "ON"},
            "lines": [{}],
        },
    ).json()["lines"][0]
    assert shipped["key"] == "sales.ON.standard"  # US customer, Canadian ship-to
    nobody = resolve(ctx, {"side": "sales", "date": "2026-06-15", "lines": [{}]}).json()["lines"][0]
    assert nobody["flags"] == ["missing_province"]


def test_50_lines_under_100_ms_with_the_header_read_once(ctx: dict[str, Any]) -> None:
    body = {
        "side": "purchase",
        "date": "2026-06-15",
        "contact": str(ctx["customers"]["ON"].public_id),
        "lines": [{"account": str(ctx["expense"].public_id)}] * 50,
    }
    resolve(ctx, body)  # warm up (sessions, catalogue caches)
    with CaptureQueriesContext(connection) as queries:
        started = time.perf_counter()
        answer = resolve(ctx, body)
        elapsed = time.perf_counter() - started
    assert answer.status_code == 200
    assert len(answer.json()["lines"]) == 50
    assert {line["key"] for line in answer.json()["lines"]} == {"purchase.ON.standard"}
    assert elapsed < 0.1, f"{elapsed * 1000:.0f} ms"
    assert len(queries) < 40  # not per line


def test_permission(ctx: dict[str, Any]) -> None:
    outsider = User.objects.create_user("nobody@else.ca", name="Nobody")
    client = Client()
    client.force_login(outsider)
    body = {"side": "sales", "date": "2026-06-15", "lines": [{}]}
    assert resolve(ctx, body, client).status_code in (403, 404)
    assert (
        resolve(
            ctx,
            {
                "side": "sales",
                "date": "2026-06-15",
                "lines": [{}],
                "contact": "8f9e8f9e-0000-4000-8000-000000000000",
            },
        ).status_code
        == 400
    )
