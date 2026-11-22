"""D-01-T09 — document calculation API: stateless calculate and posting preview for sales and
purchase documents; problems named per line; side permissions; p95 under 80 ms for 50 lines."""

from __future__ import annotations

import datetime as dt
import statistics
import time
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.rbac.catalogue import catalogue
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
D = dt.date(2026, 7, 15)


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def owner(org: Organisation) -> Client:
    client = Client()
    client.force_login(people(org)["owner"])
    return client


def url(org: Organisation, suffix: str) -> str:
    return f"/api/v1/o/{org.public_id}/documents/{suffix}"


def post(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def ids(org: Organisation) -> dict[str, str]:
    with org_context(org):
        revenue = Account.objects.filter(subtype="revenue").order_by("code").first()
        expense = (
            Account.objects.filter(type="expense", default_tax_key="purchase.ON.standard")
            .order_by("code")
            .first()
        )
        customer = contact(org, "Maple Café")
    return {
        "revenue": str(revenue.public_id),  # type: ignore[union-attr]
        "expense": str(expense.public_id),  # type: ignore[union-attr]
        "hst": str(code_for("sales.ON.standard", "sales", D, org).public_id),
        "hst_purchase": str(code_for("purchase.ON.standard", "purchase", D, org).public_id),
        "customer": str(customer.public_id),
    }


def invoice(refs: dict[str, str], **extra: Any) -> dict[str, Any]:
    body = {
        "date": D.isoformat(),
        "contact": refs["customer"],
        "lines": [
            {
                "account": refs["revenue"],
                "quantity": "2",
                "unit_price": "50",
                "tax_code": refs["hst"],
            },
            {
                "account": refs["revenue"],
                "quantity": "1",
                "unit_price": "100",
                "discount_type": "percent",
                "discount_value": "10",
                "tax_code": refs["hst"],
            },
        ],
    }
    body.update(extra)
    return body


def test_calculate_sales(org: Organisation, owner: Client) -> None:
    refs = ids(org)
    response = post(owner, url(org, "sales/calculate"), invoice(refs))
    assert response.status_code == 200, response.json()
    body = response.json()
    assert (body["kind"], body["subtotal"], body["tax_total"], body["total"]) == (
        "invoice",
        "190.00",
        "24.70",
        "214.70",
    )
    assert body["lines"][1]["line_discount"] == "10.00"
    assert [(t["key"], t["amount"]) for t in body["tax_by_component"]] == [("hst_on", "24.70")]
    assert body["tax_by_component"][0]["name"]
    assert body["problems"] == []


def test_calculate_flags_problems_without_refusing(org: Organisation, owner: Client) -> None:
    refs = ids(org)
    payload = invoice(refs)
    payload["lines"][1]["tax_code"] = refs["hst_purchase"]
    payload["lines"][0]["account"] = refs["expense"]
    response = post(owner, url(org, "sales/calculate"), payload)
    assert response.status_code == 200
    assert [(p["line"], p["field"], p["code"]) for p in response.json()["problems"]] == [
        (1, "account", "documents.line.account_sales"),
        (2, "tax_code", "documents.line.tax_side"),
    ]


def test_posting_preview_refuses_a_purchase_code_on_a_sales_line(
    org: Organisation, owner: Client
) -> None:
    refs = ids(org)
    payload = invoice(refs)
    payload["lines"][1]["tax_code"] = refs["hst_purchase"]
    response = post(owner, url(org, "sales/posting-preview"), payload)
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "documents.lines.invalid"
    assert body["detail"].startswith("Line 2:")
    assert body["problems"][0]["line"] == 2


def test_posting_preview_sales_and_purchases(org: Organisation, owner: Client) -> None:
    refs = ids(org)
    response = post(
        owner,
        url(org, "sales/posting-preview"),
        invoice(refs, discount_type="amount", discount_value="10"),
    )
    assert response.status_code == 200, response.json()
    journal = response.json()["journal"]
    assert journal["debits"] == journal["credits"] == response.json()["total"]
    assert journal["complete"] is True
    bill = {
        "kind": "bill",
        "date": D.isoformat(),
        "lines": [
            {"account": refs["expense"], "unit_price": "100", "tax_code": refs["hst_purchase"]}
        ],
    }
    response = post(owner, url(org, "purchases/posting-preview"), bill)
    assert response.status_code == 200, response.json()
    codes = {line["account"]["code"]: line for line in response.json()["journal"]["lines"]}
    assert len(codes) == 3


def test_kind_must_match_the_side_and_ids_must_exist(org: Organisation, owner: Client) -> None:
    refs = ids(org)
    assert post(owner, url(org, "sales/calculate"), invoice(refs, kind="bill")).status_code == 400
    missing = "00000000-0000-0000-0000-000000000000"
    payload = invoice(refs)
    payload["lines"][0]["tax_code"] = missing
    response = post(owner, url(org, "sales/calculate"), payload)
    assert response.status_code == 400
    assert (
        post(owner, url(org, "sales/calculate"), invoice(refs, contact=missing)).status_code == 400
    )
    bad = invoice(refs, discount_type="percent", discount_value="120")
    assert post(owner, url(org, "sales/calculate"), bad).status_code == 400


def test_side_permissions(org: Organisation) -> None:
    assert catalogue.get("sales.document.view").module == "sales"
    assert catalogue.get("purchases.document.view").module == "purchases"
    clerk = User.objects.create_user("ana@refined.ca", name="Ana")
    OrganisationMember.objects.create(organisation=org, user=clerk, role="sales")
    client = Client()
    client.force_login(clerk)
    refs = ids(org)
    assert post(client, url(org, "sales/calculate"), invoice(refs)).status_code == 200
    bill = {"date": D.isoformat(), "lines": []}
    assert post(client, url(org, "purchases/calculate"), bill).status_code == 403


def test_other_organisation_cannot_use_my_ids(org: Organisation, owner: Client) -> None:
    refs = ids(org)
    other = Organisation.objects.create(name="Other Co.")
    load_template(other, "ON")
    outsider = Client()
    stranger = User.objects.create_user("x@other.ca", name="X")
    OrganisationMember.objects.create(organisation=other, user=stranger, role="owner")
    outsider.force_login(stranger)
    response = post(outsider, url(other, "sales/calculate"), invoice(refs))
    assert response.status_code == 400  # the accounts and codes don't exist there


def test_fifty_lines_p95_under_80_ms(org: Organisation, owner: Client) -> None:
    refs = ids(org)
    lines = [
        {
            "account": refs["revenue"],
            "quantity": "1.5",
            "unit_price": f"{i}.99",
            "tax_code": refs["hst"],
        }
        for i in range(50)
    ]
    payload = {
        "date": D.isoformat(),
        "lines": lines,
        "discount_type": "percent",
        "discount_value": "5",
    }
    post(owner, url(org, "sales/calculate"), payload)  # warm-up
    timings = []
    for _ in range(20):
        start = time.perf_counter()
        response = post(owner, url(org, "sales/calculate"), payload)
        timings.append((time.perf_counter() - start) * 1000)
        assert response.status_code == 200
    p95 = statistics.quantiles(timings, n=20)[-1]
    assert p95 < 80, f"p95 {p95:.1f} ms"
