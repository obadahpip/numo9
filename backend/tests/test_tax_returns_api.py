"""G-03-T10 — the GST/HST returns API: generate, recalculate (with entries), review (not by the
preparer), send back, file, amend; the drill-down and the PDF / CSV worksheet; ``changed`` when
the books move under a draft; a refusal is a 422 with its code; an employee is refused; the
routes are in the OpenAPI schema; the tenant sweep and permission check pass."""

from __future__ import annotations

import datetime as dt
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.sales.posting import approve as approve_invoice
from numo9.tenancy.models import (
    OrganisationMember,
    Practice,
    PracticeAssignment,
    PracticeMember,
)
from tests.sales_helpers import draft
from tests.tax_report_helpers import june_books

pytestmark = pytest.mark.django_db


def _client(user: Any) -> Client:
    client = Client()
    client.force_login(user)
    return client


def _post(client: Client, url: str, body: dict[str, Any] | None = None) -> Any:
    return client.post(url, body or {}, content_type="application/json")


def _adviser(org: Any) -> User:
    practice = Practice.objects.create(name="North Star CPA")
    assignment = PracticeAssignment.objects.create(practice=practice, organisation=org)
    adviser = User.objects.create_user("sam@northstar.ca", name="Sam Patel")
    member = PracticeMember.objects.create(practice=practice, user=adviser, role="accountant")
    assignment.assigned_staff.add(member)
    return adviser


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = june_books()
    org = books["org"]
    adviser = _adviser(org)
    return {
        **books,
        "q1": books["period"],
        "owner_user": books["owner"],
        "reg": books["registration"],
        "owner": _client(books["owner"]),
        "adviser": _client(adviser),
        "base": f"/api/v1/o/{org.public_id}/tax/returns",
    }


def _sell(ctx: dict[str, Any], amount: str) -> None:
    sale = draft(ctx["sales"], [("1", amount, "sales.ON.standard")], date=dt.date(2026, 6, 20))
    approve_invoice(sale, ctx["owner_user"])


def test_the_workflow_end_to_end(ctx: dict[str, Any]) -> None:
    owner, adviser, base = ctx["owner"], ctx["adviser"], ctx["base"]
    made = _post(owner, base, {"period": str(ctx["q1"].public_id)})
    assert made.status_code == 201, made.content
    body0 = made.json()
    url = f"{base}/{body0['id']}"
    assert (body0["status"], body0["version"], body0["is_current"]) == ("draft", 1, True)
    lines = {row["line"]: row for row in body0["lines"]}
    assert lines["103"]["amount"] == "130.00" and lines["103"]["label"]
    assert lines["101"]["drill"] and lines["107"]["entry"]
    assert body0["changed"] == [] and body0["prepared_by"]["name"]

    _sell(ctx, "200.00")
    changed = owner.get(url).json()["changed"]
    assert {"line": "103", "was": "130.00", "now": "156.00"} in changed

    again = _post(owner, f"{url}/recalculate", {"entries": {"107": "5.00"}})
    assert again.status_code == 200, again.content
    body = again.json()
    assert body["entries"] == {"107": "5.00"} and body["changed"] == []
    assert {r["line"]: r["amount"] for r in body["lines"]}["103"] == "156.00"
    bad = _post(owner, f"{url}/recalculate", {"entries": {"103": "1.00"}})
    assert bad.status_code == 400

    drill = owner.get(f"{url}/drill", {"line": "103"})
    assert drill.status_code == 200 and drill.json()["line"] == "103"
    assert owner.get(f"{url}/drill", {"line": "999"}).status_code == 400

    assert _post(owner, f"{url}/review").status_code == 403  # the preparer
    refused = _post(owner, f"{url}/file", {"confirmation_no": "GH-1"})
    assert (refused.status_code, refused.json()["code"]) == (422, "tax.return.status")
    reviewed = _post(adviser, f"{url}/review")
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "reviewed"
    blank = _post(adviser, f"{url}/send-back", {"reason": " "})
    assert (blank.status_code, blank.json()["code"]) == (422, "tax.return.reason_required")
    back = _post(adviser, f"{url}/send-back", {"reason": "Check line 107"})
    assert back.json()["status"] == "draft"
    _post(adviser, f"{url}/review")
    filed = _post(
        owner, f"{url}/file", {"confirmation_no": "GH-2026-0001", "filed_on": "2026-07-20"}
    )
    assert filed.status_code == 200, filed.content
    assert (filed.json()["status"], filed.json()["filed_on"]) == ("filed", "2026-07-20")
    assert filed.json()["period"]["locked"] is True

    amended = _post(adviser, f"{url}/amend", {"reason": "Missed a bill"})
    assert amended.status_code == 201
    assert (amended.json()["version"], amended.json()["status"]) == (2, "draft")
    versions = owner.get(f"{base}/{amended.json()['id']}").json()["versions"]
    assert len(versions) == 2
    listed = owner.get(base, {"registration": str(ctx["reg"].public_id)}).json()["returns"]
    assert [r["version"] for r in listed] == [2, 1]
    assert owner.get(f"{url}").json()["is_current"] is False


def test_the_worksheet_exports(ctx: dict[str, Any]) -> None:
    made = _post(ctx["owner"], ctx["base"], {"period": str(ctx["q1"].public_id)}).json()
    url = f"{ctx['base']}/{made['id']}"
    csv = ctx["owner"].get(f"{url}/csv")
    assert csv.status_code == 200 and csv["Content-Type"].startswith("text/csv")
    assert "gst-hst-return-2026-06-01-2026-06-30-v1.csv" in csv["Content-Disposition"]
    assert b"103" in csv.content and b"130.00" in csv.content
    pdf = ctx["owner"].get(f"{url}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_unknown_period_and_return_are_404(ctx: dict[str, Any]) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert _post(ctx["owner"], ctx["base"], {"period": missing}).status_code == 404
    assert ctx["owner"].get(f"{ctx['base']}/{missing}").status_code == 404


def test_an_employee_is_refused_and_the_checks_pass(ctx: dict[str, Any]) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=ctx["org"], user=employee, role="employee")
    client = _client(employee)
    assert _post(client, ctx["base"], {"period": str(ctx["q1"].public_id)}).status_code == 403
    schema = StringIO()
    call_command("spectacular", "--format", "openapi-json", stdout=schema)
    text = schema.getvalue()
    for tail in ("returns", "recalculate", "review", "send-back", "file", "amend", "drill"):
        assert tail in text
    assert "/api/v1/o/{org}/tax/returns/{public_id}/pdf" in text
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
