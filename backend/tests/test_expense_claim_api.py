"""E-04-T08 — expense claims API: create a draft (receipts, mileage priced at the CRA rate), list
with counts, edit and delete drafts, submit, approve (reimbursement bill linked); the form's
helpers (categories most-used first, tax codes, mileage rate with YTD km, receipt upload);
security: an employee sees and edits only their own claims (others' are 404), can't enter a
claim for someone else, can't approve; permissions on the system roles; OpenAPI; sweeps."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.models import Account
from numo9.purchases.models import ExpenseClaim
from numo9.rbac.models import ApprovalLimit
from numo9.rbac.system_roles import system_role
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.journal_helpers import document
from tests.purchase_helpers import DAY, member, purchase_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = purchase_books()
    org = books["org"]
    with org_context(org):
        ApprovalLimit.objects.create(
            user=books["owner"], doc_type="expense_claim", max_amount=D("1000")
        )
        books["office"] = Account.objects.get(code="6080")
        books["travel"] = Account.objects.get(code="6200")
    books["hst"] = code_for("purchase.ON.standard", "purchase", DAY, org)
    books["employee"] = member(org, "emp@refined.ca", "employee")
    books["colleague"] = member(org, "pat@refined.ca", "employee")
    books["base"] = f"/api/v1/o/{org.public_id}/expense-claims"
    return books


def client(user: User) -> Client:
    c = Client()
    c.force_login(user)
    return c


def send(c: Client, method: str, url: str, body: Any = None) -> Any:
    return getattr(c, method)(url, body or {}, content_type="application/json")


def payload(books: dict[str, Any], **over: Any) -> dict[str, Any]:
    return {
        "title": "Ottawa client visit",
        "lines": [
            {
                "kind": "receipt",
                "date": DAY.isoformat(),
                "merchant": "Staples",
                "account": str(books["office"].public_id),
                "tax_code": str(books["hst"].public_id),
                "amount": "56.50",
            },
            {
                "kind": "mileage",
                "date": DAY.isoformat(),
                "from_place": "Toronto office",
                "to_place": "Ottawa client",
                "distance_km": "100",
            },
        ],
        **over,
    }


def test_create_list_edit_submit_approve(books: dict[str, Any]) -> None:
    me = client(books["employee"])
    made = send(me, "post", books["base"], payload(books))
    assert made.status_code == 201, made.json()
    claim = made.json()
    assert (claim["status"], claim["number"], claim["total"]) == ("draft", "", "129.50")
    assert claim["claimant"]["name"] == "Emp" and claim["can_edit"] is True
    mileage = claim["lines"][1]
    assert (mileage["amount"], mileage["rate_detail"][0]["rate"]) == ("73.00", "0.73")
    assert claim["lines"][0]["split"]["claimable"] == "6.50"
    listed = me.get(books["base"]).json()
    assert [r["id"] for r in listed["results"]] == [claim["id"]]
    assert listed["counts"]["draft"] == 1 and listed["can_view_all"] is False
    url = f"{books['base']}/{claim['id']}"
    edited = send(me, "patch", url, payload(books, title="Ottawa visit (2 days)"))
    assert edited.status_code == 200, edited.json()
    assert edited.json()["title"] == "Ottawa visit (2 days)"
    submitted = send(me, "post", f"{url}/submit")
    assert submitted.status_code == 200, submitted.json()
    assert (submitted.json()["status"], submitted.json()["number"]) == ("submitted", "EXP-0001")
    assert submitted.json()["can_edit"] is False
    locked = send(me, "patch", url, payload(books))
    assert locked.json()["code"] == "purchases.expense.not_editable"
    assert send(me, "post", f"{url}/approve").status_code == 403  # employee: no approve
    done = send(client(books["owner"]), "post", f"{url}/approve")
    assert done.status_code == 200, done.json()
    assert done.json()["status"] == "approved"
    assert done.json()["bill"]["number"] == "BILL-0001"
    assert done.json()["bill"]["amount_due"] == "129.50"


def test_delete_a_draft_only(books: dict[str, Any]) -> None:
    me = client(books["employee"])
    claim = send(me, "post", books["base"], payload(books)).json()
    url = f"{books['base']}/{claim['id']}"
    assert send(me, "delete", url).status_code == 204
    assert me.get(url).status_code == 404


def test_submit_refusals_are_400_with_the_rule(books: dict[str, Any]) -> None:
    me = client(books["employee"])
    body = payload(books)
    body["lines"][0]["account"] = None
    claim = send(me, "post", books["base"], body).json()
    refused = send(me, "post", f"{books['base']}/{claim['id']}/submit")
    assert (refused.status_code, refused.json()["code"]) == (
        400,
        "purchases.expense.category_missing",
    )
    bad = payload(books)
    bad["lines"][1].pop("distance_km")
    assert send(me, "post", books["base"], bad).status_code == 400


def test_employee_sees_and_edits_own_claims_only(books: dict[str, Any]) -> None:
    mine = send(client(books["employee"]), "post", books["base"], payload(books)).json()
    other = client(books["colleague"])
    url = f"{books['base']}/{mine['id']}"
    assert other.get(url).status_code == 404
    assert send(other, "patch", url, payload(books)).status_code == 404
    assert send(other, "delete", url).status_code == 404
    assert send(other, "post", f"{url}/submit").status_code == 404
    assert other.get(books["base"]).json()["results"] == []
    # Someone with purchases.expenses.view sees everyone's claims.
    everyone = client(books["owner"]).get(books["base"]).json()
    assert [r["id"] for r in everyone["results"]] == [mine["id"]]
    assert everyone["can_view_all"] is True
    assert client(books["owner"]).get(url).status_code == 200


def test_entering_a_claim_for_someone_else_needs_write(books: dict[str, Any]) -> None:
    body = payload(books, claimant=str(books["colleague"].public_id))
    refused = send(client(books["employee"]), "post", books["base"], body)
    assert refused.status_code == 403
    made = send(client(books["owner"]), "post", books["base"], body)
    assert made.status_code == 201, made.json()
    assert made.json()["claimant"]["id"] == str(books["colleague"].public_id)
    stranger = User.objects.create_user("x@else.ca", name="X")
    body = payload(books, claimant=str(stranger.public_id))
    assert send(client(books["owner"]), "post", books["base"], body).status_code == 400


def test_receipt_must_be_the_persons_own_upload(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        theirs = document(books["org"], "theirs.jpg")
    body = payload(books)
    body["lines"][0]["receipt"] = str(theirs.public_id)
    refused = send(client(books["employee"]), "post", books["base"], body)
    assert refused.status_code == 400
    assert "receipt" in refused.json()["lines"]["0"]
    assert send(client(books["owner"]), "post", books["base"], body).status_code == 201


def test_categories_most_used_first_and_tax_codes(books: dict[str, Any]) -> None:
    me = client(books["employee"])
    body = payload(books)
    body["lines"][0]["account"] = str(books["travel"].public_id)
    send(me, "post", books["base"], body)
    shown = me.get(f"{books['base']}/categories").json()
    assert shown["categories"][0]["code"] == "6200" and shown["categories"][0]["used"] == 1
    assert {"6010", "6080"} <= {c["code"] for c in shown["categories"]}
    meals = next(c for c in shown["categories"] if c["code"] == "6010")
    assert meals["itc_restriction_pct"] == "50"
    assert shown["default_tax_code"] == str(
        code_for("purchase.ON.standard", "purchase", dt.date.today(), books["org"]).public_id
    )


def test_mileage_rate_with_year_to_date_km(books: dict[str, Any]) -> None:
    me = client(books["employee"])
    send(me, "post", books["base"], payload(books))  # 100 km on DAY
    later = (DAY + dt.timedelta(days=5)).isoformat()
    shown = me.get(f"{books['base']}/mileage-rate", {"date": later}).json()
    assert (shown["first_tier_rate"], shown["second_tier_rate"]) == ("0.73", "0.67")
    assert (shown["tier_threshold_km"], shown["year_to_date_km"]) == (5000, "100")
    assert me.get(f"{books['base']}/mileage-rate", {"date": "1990-01-01"}).status_code == 404
    assert me.get(f"{books['base']}/mileage-rate", {"date": "nope"}).status_code == 400


def test_receipt_upload_start_and_finalize(books: dict[str, Any]) -> None:
    from unittest import mock

    me = client(books["employee"])
    form = {"url": "https://bucket.test/", "fields": {"key": "k"}}
    with mock.patch("numo9.files.services.storage.presigned_post", return_value=form):
        started = send(me, "post", f"{books['base']}/receipts", {"name": "r.jpg", "size": 1200})
    assert started.status_code == 201, started.json()
    assert started.json()["upload"]["url"] == "https://bucket.test/"
    doc = started.json()["document"]["id"]
    other = send(client(books["colleague"]), "post", f"{books['base']}/receipts/{doc}/finalize")
    assert other.status_code == 404  # someone else's upload


def test_permissions_on_the_system_roles() -> None:
    for key in ("employee", "sales", "payroll", "hr", "purchasing", "owner", "admin"):
        assert "purchases.expenses.own" in system_role("organisation", key).permission_keys(), key
    assert (
        "purchases.expenses.view" not in system_role("organisation", "employee").permission_keys()
    )
    assert "purchases.expenses.own" not in system_role("practice", "reviewer").permission_keys()


def test_hr_member_without_view_lists_only_their_own(books: dict[str, Any]) -> None:
    hr = client(member(books["org"], "hr@refined.ca", "hr"))
    send(client(books["employee"]), "post", books["base"], payload(books))
    assert hr.get(books["base"]).json()["results"] == []


def test_sweeps_and_openapi() -> None:
    from drf_spectacular.generators import SchemaGenerator

    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
    schema = SchemaGenerator().get_schema(request=None, public=True)  # type: ignore[no-untyped-call]
    paths = schema["paths"]
    prefix = "/api/v1/o/{org}/expense-claims"
    for route in (
        "",
        "/categories",
        "/mileage-rate",
        "/receipts",
        "/receipts/{public_id}/finalize",
        "/{public_id}",
        "/{public_id}/submit",
        "/{public_id}/approve",
        "/{public_id}/reject",
    ):
        assert f"{prefix}{route}" in paths, route


def test_claims_of_another_organisation_are_404(books: dict[str, Any]) -> None:
    from numo9.tenancy.models import Organisation

    claim = send(client(books["employee"]), "post", books["base"], payload(books)).json()
    elsewhere = Organisation.objects.create(name="Elsewhere Inc.")
    stranger = member(elsewhere, "stranger@else.ca", "owner")
    url = f"/api/v1/o/{elsewhere.public_id}/expense-claims/{claim['id']}"
    assert client(stranger).get(url).status_code == 404
    with org_context(books["org"]):
        assert ExpenseClaim.objects.count() == 1
