"""G-01-T11 — tax API: components and codes (list by side/date, CRUD, archive, versions),
calculate; reading in every package, editing needs tax.codes.write and tax.manage.

Acceptance: the sales picker endpoint never returns purchase codes; expired versions only with
expired=1 (MB RST 8 % absent on a 2026 date); a code is defined, versioned, archived, restored;
delete is refused (409) once posted lines used it; calculate matches the calculator; an employee
gets 403; 402 without the write feature (reading stays open); the router sweep passes; the
permission catalogue lists tax.codes.view and tax.manage.
"""

from __future__ import annotations

import datetime as dt
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.catalogue import drf as catalogue_drf
from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.rbac.catalogue import catalogue
from numo9.tax.models import TaxCode
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


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
    return f"/api/v1/o/{org.public_id}/tax/{suffix}"


def send(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def test_sales_picker_never_returns_purchase_codes(org: Organisation, owner: Client) -> None:
    sales = owner.get(url(org, "codes?side=sales&date=2026-06-15")).json()["results"]
    assert sales and all(r["side"] == "sales" and r["code"].startswith("sales.") for r in sales)
    on = next(r for r in sales if r["code"] == "sales.ON.standard")
    assert (on["rate"], on["type_label"], on["components"][0]["rate"]) == ("13", "Taxable", "13")
    mb = [r for r in sales if r["code"] == "sales.MB.standard"]
    assert [r["components"][1]["rate"] for r in mb] == ["7"]  # 8 % ended in 2019
    expired = owner.get(url(org, "codes?side=sales&date=2026-06-15&expired=1")).json()["results"]
    assert [r["expired"] for r in expired if r["code"] == "sales.MB.standard"] == [False, True]
    assert owner.get(url(org, "codes?side=both")).status_code == 400


def test_define_version_archive_restore_delete(org: Organisation, owner: Client) -> None:
    comps = owner.get(url(org, "components?key=hst_on")).json()["results"]
    hst = comps[0]["id"]
    made = send(
        owner,
        url(org, "codes"),
        {
            "code": "purchase.ON.fuel",
            "name": "HST on fuel",
            "side": "purchase",
            "type": "taxable",
            "province": "ON",
            "effective_from": "2026-01-01",
            "itc_restriction_pct": "80",
            "components": [{"component": hst}],
        },
    )
    assert made.status_code == 201, made.json()
    code_id = made.json()["id"]
    dup = send(
        owner, url(org, "codes"), {**made.json(), "code": "purchase.ON.fuel", "components": []}
    )
    assert dup.status_code == 400
    revised = send(
        owner,
        url(org, f"codes/{code_id}/versions"),
        {
            "effective_from": "2027-01-01",
            "components": [{"component": hst, "recoverable_pct": "50"}],
        },
    )
    assert revised.status_code == 201 and revised.json()["version"] == 2
    detail = owner.get(url(org, f"codes/{code_id}")).json()
    assert [(v["version"], v["effective_to"]) for v in detail["versions"]] == [
        (1, "2026-12-31"),
        (2, None),
    ]
    archived = send(owner, url(org, f"codes/{code_id}/archive"), {})
    assert archived.json()["archived_at"] is not None
    listed = owner.get(url(org, "codes?side=purchase&date=2026-06-15")).json()["results"]
    assert "purchase.ON.fuel" not in {r["code"] for r in listed}
    assert send(owner, url(org, f"codes/{code_id}/restore"), {}).json()["archived_at"] is None
    with org_context(org):
        fuel, bank = Account.objects.get(code="6210"), Account.objects.get(code="1010")
        post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 15),
                lines=[
                    LineSpec(fuel, debit="10.00", tax_code="purchase.ON.fuel"),
                    LineSpec(bank, credit="10.00"),
                ],
            ),
            user=None,
        )
    used = owner.delete(url(org, f"codes/{code_id}"))
    assert (used.status_code, used.json()["count"]) == (409, 1)
    with org_context(org):
        spare = TaxCode.objects.get(code="sales.exempt")
    assert owner.delete(url(org, f"codes/{spare.public_id}")).status_code == 204


def test_refusals_come_back_as_400(org: Organisation, owner: Client) -> None:
    bad = send(
        owner,
        url(org, "codes"),
        {
            "code": "sales.custom",
            "name": "Bad",
            "side": "sales",
            "type": "taxable",
            "effective_from": "2026-01-01",
            "components": [],
        },
    )
    assert (bad.status_code, bad.json()["code"]) == (400, "tax.code.components_required")
    overlap = send(
        owner,
        url(org, "components"),
        {
            "key": "gst",
            "name": "GST",
            "kind": "gst",
            "authority": "CRA",
            "rate": "6",
            "effective_from": "2026-01-01",
        },
    )
    assert (overlap.status_code, overlap.json()["code"]) == (400, "tax.component.overlap")


def test_calculate(org: Organisation, owner: Client) -> None:
    with org_context(org):
        meals = Account.objects.get(code="6010")
        code = TaxCode.objects.get(code="purchase.ON.standard")
    out = send(
        owner,
        url(org, "calculate"),
        {
            "code": str(code.public_id),
            "amount": "113.00",
            "inclusive": True,
            "account": str(meals.public_id),
        },
    ).json()
    assert (out["net"], out["tax"], out["claimable"], out["cost"]) == (
        "100.00",
        "13.00",
        "6.50",
        "6.50",
    )


def test_permissions_feature_and_sweep(
    org: Organisation, owner: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=org, user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert send(client, url(org, "codes"), {"code": "sales.x"}).status_code == 403
    call_command("tenant_sweep", stdout=StringIO())
    assert {"tax.codes.view", "tax.manage"} <= {p.key for p in catalogue}

    class NoTax:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return not key.startswith("tax.")

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoTax())
    assert owner.get(url(org, "codes?side=sales")).status_code == 200  # reading: every package
    refused = send(owner, url(org, "codes"), {"code": "sales.x"})
    assert (refused.status_code, refused.json()["feature"]) == (402, "tax.codes.write")
