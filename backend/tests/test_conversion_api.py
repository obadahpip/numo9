"""C-05-T09 — conversion API ``/api/v1/o/<org>/conversion/``: session, lines, documents,
difference, finalise, import, corrections; feature keys ``accounting.conversion_balances.*``,
permissions ``accounting.conversion.*`` (an employee gets 403); OpenAPI lists every route; the
tenant sweep, the permission check and the feature-key check pass.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.models import JournalEntry
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.conversion_helpers import acct

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    from tests.journal_helpers import people
    from tests.sales_helpers import sales_books

    books = sales_books()
    org = books["org"]
    from numo9.ledger.models import Account
    from tests.contact_helpers import contact

    with org_context(org):
        books["supplier"] = contact(org, "Cedar Supply Co.", roles=["supplier"])
        books["accounts"] = {a.code: a for a in Account.objects.all()}
    books.update(people(org))
    clients = {}
    for key in ("owner", "adviser"):
        client = Client()
        client.force_login(books[key])
        clients[key] = client
    return {
        **books,
        "owner_client": clients["owner"],
        "adviser_client": clients["adviser"],
        "base": f"/api/v1/o/{org.public_id}/conversion/",
    }


def send(client: Client, method: str, url: str, body: dict[str, Any]) -> Any:
    return getattr(client, method)(url, body, content_type="application/json")


def aid(ctx: dict[str, Any], code: str) -> str:
    return str(acct(ctx, code).public_id)


def test_wizard_flow_to_finalise_and_correction(ctx: dict[str, Any]) -> None:
    base, owner, adviser = ctx["base"], ctx["owner_client"], ctx["adviser_client"]
    empty = owner.get(base).json()
    assert empty["session"] is None and empty["difference"] is None
    assert [s["key"] for s in empty["steps"]] == [
        "date",
        "bank",
        "invoices",
        "bills",
        "other",
        "review",
    ]
    made = send(owner, "post", base, {"conversion_date": "2026-01-01"})
    assert made.status_code == 201, made.content
    assert made.json()["session"]["status"] == "draft"
    again = send(owner, "post", base, {"conversion_date": "2026-01-01"})
    assert again.status_code == 400 and again.json()["code"] == "conversion.session.exists"
    saved = send(owner, "patch", base, {"step": "invoices", "completed_steps": ["bank", "date"]})
    assert saved.status_code == 200
    assert saved.json()["session"]["step"] == "invoices"
    assert saved.json()["session"]["completed_steps"] == ["date", "bank"]

    docs = send(
        owner,
        "post",
        f"{base}documents",
        {
            "kind": "invoice",
            "rows": [
                {
                    "contact": "on customer ltd",
                    "number": "INV-1",
                    "date": "2025-11-15",
                    "total": "1000.00",
                },
                {
                    "contact": str(ctx["customers"]["BC"].public_id),
                    "number": "INV-2",
                    "date": "2025-12-01",
                    "due_date": "2025-12-31",
                    "total": "900.00",
                    "outstanding": "500.00",
                },
            ],
        },
    )
    assert docs.status_code == 201, docs.content
    assert [d["number"] for d in docs.json()["documents"]] == ["INV-1", "INV-2"]
    assert docs.json()["documents"][1]["outstanding"] == "500.00"
    bills = send(
        owner,
        "post",
        f"{base}documents",
        {
            "kind": "bill",
            "rows": [
                {
                    "contact": "Cedar Supply Co.",
                    "supplier_invoice_no": "S1",
                    "date": "2025-12-10",
                    "total": "300.00",
                }
            ],
        },
    )
    assert bills.status_code == 201, bills.content

    bad_lines = send(
        owner,
        "put",
        f"{base}lines",
        {
            "lines": [
                {"account": aid(ctx, "1010"), "debit": "5000.00"},
                {"account": aid(ctx, "3000"), "debit": "1.00", "credit": "1.00"},
            ]
        },
    )
    assert bad_lines.status_code == 400
    assert bad_lines.json()["rows"][0]["row"] == 2
    assert bad_lines.json()["rows"][0]["code"] == "conversion.line.both_sides"
    assert owner.get(f"{base}lines").json()["lines"] == []  # all or nothing

    lines = send(
        owner,
        "put",
        f"{base}lines",
        {
            "lines": [
                {"account": aid(ctx, "1010"), "debit": "5,000.00"},
                {"account": aid(ctx, "1100"), "debit": "1500.00"},
                {"account": aid(ctx, "2000"), "credit": "300.00"},
                {"account": aid(ctx, "3000"), "credit": "100.00"},
                {"account": aid(ctx, "3200"), "credit": "6000.00"},
            ]
        },
    )
    assert lines.status_code == 200, lines.content
    meter = lines.json()["difference"]
    assert (meter["debits"], meter["credits"], meter["difference"]) == (
        "6500.00",
        "6400.00",
        "100.00",
    )
    refused = send(owner, "post", f"{base}finalise", {})
    assert refused.status_code == 400
    assert refused.json()["code"] == "conversion.unbalanced"
    assert refused.json()["params"]["difference"] == "100.00"
    assert "Difference 100.00" in refused.json()["detail"]

    send(owner, "put", f"{base}lines", {"lines": [{"account": aid(ctx, "3200"), "credit": "6100"}]})
    difference = owner.get(f"{base}difference").json()["difference"]
    assert difference["can_finalise"] is True and difference["reasons"] == []
    done = send(owner, "post", f"{base}finalise", {"lock_balances": True})
    assert done.status_code == 200, done.content
    session = done.json()["session"]
    assert session["status"] == "finalised" and session["lock_balances"] is True
    assert session["opening_entry"]["number"]
    assert done.json()["difference"]["reasons"][0]["code"] == "conversion.finalised"

    late = send(
        owner, "put", f"{base}lines", {"lines": [{"account": aid(ctx, "1020"), "debit": "1"}]}
    )
    assert (
        late.status_code == 400 and late.json()["rows"][0]["code"] == "conversion.session.finalised"
    )
    body = {
        "reason": "Bank statement",
        "lines": [
            {"account": aid(ctx, "1010"), "debit": "10.00"},
            {"account": aid(ctx, "3100"), "credit": "10.00"},
        ],
    }
    no = send(owner, "post", f"{base}corrections", body)
    assert no.status_code == 400 and no.json()["code"] == "conversion.correction.adviser_only"
    fixed = send(adviser, "post", f"{base}corrections", body)
    assert fixed.status_code == 201, fixed.content
    assert fixed.json()["reason"] == "Bank statement"
    listed = owner.get(f"{base}corrections").json()["corrections"]
    assert [c["id"] for c in listed] == [fixed.json()["id"]]
    with org_context(ctx["org"]):
        assert JournalEntry.objects.filter(type="opening").count() == 2


def test_documents_paste_validated_all_or_nothing(ctx: dict[str, Any]) -> None:
    base, owner = ctx["base"], ctx["owner_client"]
    send(owner, "post", base, {"conversion_date": "2026-01-01"})
    rows = [
        {"contact": "ON Customer Ltd", "number": f"INV-{n}", "date": "2025-12-01", "total": "10"}
        for n in range(1, 21)
    ]
    dry = send(
        owner, "post", f"{base}documents", {"kind": "invoice", "rows": rows, "dry_run": True}
    )
    assert dry.status_code == 200 and dry.json()["ok"] == 20 and dry.json()["written"] == 0
    assert owner.get(f"{base}documents").json()["documents"] == []
    broken = [*rows[:19], {**rows[19], "number": "INV-1", "contact": "Nobody"}]
    bad = send(owner, "post", f"{base}documents", {"kind": "invoice", "rows": broken})
    assert bad.status_code == 400 and bad.json()["errors"] == 1
    (row,) = [r for r in bad.json()["rows"] if not r["ok"]]
    assert row["row"] == 20 and row["errors"][0]["code"] == "conversion.document.contact"
    assert owner.get(f"{base}documents").json()["documents"] == []
    made = send(owner, "post", f"{base}documents", {"kind": "invoice", "rows": rows})
    assert made.status_code == 201 and made.json()["written"] == 20
    listed = owner.get(f"{base}documents", {"kind": "invoice"}).json()["documents"]
    assert len(listed) == 20
    gone = send(owner, "post", f"{base}documents/remove", {"ids": [listed[0]["id"]]})
    assert gone.status_code == 200 and gone.json()["removed"] == 1
    assert len(gone.json()["documents"]) == 19


def test_tb_import_dry_run_and_write(ctx: dict[str, Any]) -> None:
    base, owner = ctx["base"], ctx["owner_client"]
    send(owner, "post", base, {"conversion_date": "2026-01-01"})
    data = b"Code,Debit,Credit\n1010,500.00,\n3000,,500.00\n"
    mapping = owner.post(
        f"{base}import/mapping", {"file": SimpleUploadedFile("tb.csv", data)}
    ).json()
    assert mapping["mapping"] == {"account": "Code", "debit": "Debit", "credit": "Credit"}
    common = {"mapping": '{"account": "Code", "debit": "Debit", "credit": "Credit"}'}
    dry = owner.post(f"{base}import", {"file": SimpleUploadedFile("tb.csv", data), **common})
    assert dry.status_code == 200 and dry.json()["written"] == 0
    real = owner.post(
        f"{base}import",
        {"file": SimpleUploadedFile("tb.csv", data), "dry_run": "false", **common},
    )
    assert real.status_code == 200 and real.json()["written"] == 2
    assert real.json()["difference"]["can_finalise"] is True


def test_permissions_openapi_and_sweep(ctx: dict[str, Any]) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=ctx["org"], user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert client.get(ctx["base"]).status_code == 403
    assert send(client, "post", ctx["base"], {"conversion_date": "2026-01-01"}).status_code == 403
    other = Organisation.objects.create(name="Elsewhere Ltd")
    assert ctx["owner_client"].get(f"/api/v1/o/{other.public_id}/conversion/").status_code == 404
    schema = ctx["owner_client"].get("/api/schema/?format=json").json()
    paths = [p for p in schema["paths"] if "/conversion/" in p]
    assert len(paths) == 9
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())
