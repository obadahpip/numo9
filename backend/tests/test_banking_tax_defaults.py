"""G-02-T09 — purchase-side tax resolution for spend money (and the sales side for receive
money): account default, then the supplier's province.

Acceptance (integration): an expense account with an HST default and an Ontario supplier gives
the HST 13 % purchase code.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.banking.tax_defaults import AUTO, portions
from numo9.contacts.models import Address, AddressKind, Contact
from numo9.ledger.models import Account, JournalLine
from numo9.ledger.template import load_template
from numo9.orgsettings.service import get_settings
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import people
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = "2026-06-15"


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(organisation):
        settings = get_settings(organisation)
        settings.physical_province = "ON"
        settings.save()
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def owner(org: Organisation) -> Client:
    client = Client()
    client.force_login(people(org)["owner"])
    return client


def url(org: Organisation, suffix: str) -> str:
    return f"/api/v1/o/{org.public_id}/{suffix}"


def send(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def party(org: Organisation, name: str, province: str, roles: list[str]) -> Contact:
    with org_context(org):
        item = contact(org, name, roles=roles)
        Address(
            organisation=org,
            contact=item,
            kind=AddressKind.BILLING,
            country="CA" if province else "US",
            province=province,
            city="Somewhere",
        ).save()
        return item


def bank(client: Client, org: Organisation) -> str:
    made = send(
        client,
        url(org, "bank-accounts"),
        {"type": "chequing", "display_name": "TD Chequing", "institution": "TD"},
    )
    assert made.status_code == 201
    bank_id: str = made.json()["id"]
    with org_context(org):
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
    funded = send(
        client,
        url(org, "bank-transactions"),
        {
            "kind": "receive",
            "bank_account": bank_id,
            "date": "2026-06-01",
            "tax_mode": "no_tax",
            "lines": [{"account": str(sales.public_id), "amount": "5000.00"}],  # type: ignore[union-attr]
        },
    )
    assert funded.status_code == 201, funded.json()
    return bank_id


def default(client: Client, org: Organisation, **query: str) -> dict[str, Any]:
    params = "&".join(f"{k}={v}" for k, v in query.items())
    response = client.get(url(org, f"bank-transactions/tax-default?{params}"))
    assert response.status_code == 200, response.json()
    result: dict[str, Any] = response.json()
    return result


def test_expense_account_with_hst_default_and_ontario_supplier(
    org: Organisation, owner: Client
) -> None:
    with org_context(org):
        office_account = (
            Account.objects.filter(type="expense", default_tax_key="purchase.ON.standard")
            .order_by("code")
            .first()
        )
    assert office_account is not None
    staples = party(org, "Staples", "ON", ["supplier"])
    found = default(
        owner,
        org,
        kind="spend",
        date=D,
        account=str(office_account.public_id),
        contact=str(staples.public_id),
        amount="100.00",
    )
    assert (found["code"], found["source"]) == ("purchase.ON.standard", "account")
    assert found["name"] == "HST 13 % (Ontario) on purchases"
    assert found["taxes"] == [{"role": "itc_receivable", "amount": "13.00", "recoverable": True}]


def test_account_without_key_uses_the_supplier_province(org: Organisation, owner: Client) -> None:
    with org_context(org):
        props = account(org, "4998", "Studio props", subtype="other_income")  # not an expense
    bc = party(org, "Vancouver Props", "BC", ["supplier"])
    found = default(
        owner, org, kind="spend", date=D, account=str(props.public_id), contact=str(bc.public_id)
    )
    assert (found["code"], found["source"], found["explanation"]) == (
        "purchase.BC.standard",
        "place_of_supply",
        "tax.pos.supplier_province",
    )
    assert found["params"] == {"province": "BC"}


def test_receive_money_follows_the_sales_table(org: Organisation, owner: Client) -> None:
    quebec = party(org, "Boutique Laval", "QC", ["customer"])
    us = party(org, "Acme Inc.", "", ["customer"])
    with org_context(org):
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
    assert sales is not None
    qc = default(
        owner,
        org,
        kind="receive",
        date=D,
        account=str(sales.public_id),
        contact=str(quebec.public_id),
    )
    assert qc["code"] == "sales.QC.gst" and qc["explanation"] == "tax.pos.gst_unregistered_qst"
    export = default(owner, org, kind="receive", date=D, contact=str(us.public_id))
    assert export["code"] == "sales.zero_rated"
    nobody = default(owner, org, kind="receive", date=D)
    assert nobody["code"] == "sales.ON.standard" and nobody["flags"] == ["missing_province"]


def test_bc_customer_unregistered_warns(org: Organisation, owner: Client) -> None:
    bc = party(org, "Vancouver Co.", "BC", ["customer"])
    found = default(owner, org, kind="receive", date=D, contact=str(bc.public_id))
    assert found["warnings"] == ["tax.pos.pst_unregistered"]


def test_spend_with_auto_tax_posts_the_itc(org: Organisation, owner: Client) -> None:
    bank_id = bank(owner, org)
    with org_context(org):
        office = (
            Account.objects.filter(type="expense", default_tax_key="purchase.ON.standard")
            .order_by("code")
            .first()
        )
    assert office is not None
    staples = party(org, "Staples", "ON", ["supplier"])
    made = send(
        owner,
        url(org, "bank-transactions"),
        {
            "kind": "spend",
            "bank_account": bank_id,
            "date": D,
            "contact": str(staples.public_id),
            "tax_mode": "inclusive",
            "lines": [{"account": str(office.public_id), "amount": "113.00", "tax_code": AUTO}],
        },
    )
    assert made.status_code == 201, made.json()
    body = made.json()
    assert (body["subtotal"], body["tax_total"], body["total"]) == ("100.00", "13.00", "113.00")
    assert body["lines"][0]["tax_code"] == "purchase.ON.standard"
    with org_context(org):
        itc = JournalLine.objects.get(
            entry__public_id=body["journal"]["id"], account__system_role="itc_receivable"
        )
        assert itc.debit == Decimal("13.00")


def test_auto_in_a_no_tax_transaction_means_no_code(org: Organisation, owner: Client) -> None:
    bank_id = bank(owner, org)
    with org_context(org):
        office = Account.objects.filter(type="expense").order_by("code").first()
    made = send(
        owner,
        url(org, "bank-transactions"),
        {
            "kind": "spend",
            "bank_account": bank_id,
            "date": D,
            "tax_mode": "no_tax",
            "lines": [{"account": str(office.public_id), "amount": "50.00", "tax_code": AUTO}],  # type: ignore[union-attr]
        },
    )
    assert made.status_code == 201, made.json()
    assert made.json()["lines"][0]["tax_code"] == "" and made.json()["tax_total"] == "0.00"


def test_portions_split_pst_as_non_recoverable(org: Organisation) -> None:
    import datetime as dt

    version = code_for("purchase.BC.standard", "purchase", dt.date(2026, 6, 15), org)
    with org_context(org):
        parts = portions(version, Decimal("100.00"), inclusive=False)
    assert [(p.role, p.amount, p.recoverable) for p in parts] == [
        ("itc_receivable", Decimal("5.00"), True),
        ("pst_payable", Decimal("7.00"), False),
    ]
    sales = code_for("sales.QC.standard", "sales", dt.date(2026, 6, 15), org)
    with org_context(org):
        parts = portions(sales, Decimal("100.00"), inclusive=False)
    assert [(p.role, p.amount) for p in parts] == [
        ("gst_hst_payable", Decimal("5.00")),
        ("qst_payable", Decimal("9.98")),
    ]
    assert portions(None, Decimal("1"), inclusive=False) == []


def test_unknown_account_or_contact_is_400(org: Organisation, owner: Client) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    response = owner.get(
        url(org, f"bank-transactions/tax-default?kind=spend&date={D}&account={missing}")
    )
    assert response.status_code == 400
    response = owner.get(
        url(org, f"bank-transactions/tax-default?kind=spend&date={D}&contact={missing}")
    )
    assert response.status_code == 400


def test_explicit_code_without_portions_gets_them(org: Organisation, owner: Client) -> None:
    """F-01-T10 — the spend/receive form sends the code it picked; the server works out the tax."""
    bank_id = bank(owner, org)
    with org_context(org):
        office = Account.objects.filter(type="expense").order_by("code").first()
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
    spent = send(
        owner,
        url(org, "bank-transactions"),
        {
            "kind": "spend",
            "bank_account": bank_id,
            "date": D,
            "tax_mode": "exclusive",
            "lines": [
                {
                    "account": str(office.public_id),  # type: ignore[union-attr]
                    "amount": "100.00",
                    "tax_code": "purchase.BC.standard",
                }
            ],
        },
    )
    assert spent.status_code == 201, spent.json()
    body = spent.json()
    # BC: GST 5 % recoverable (ITC), PST 7 % a cost on the expense line.
    assert (body["subtotal"], body["tax_total"], body["total"]) == ("100.00", "12.00", "112.00")
    assert body["lines"][0]["tax_code"] == "purchase.BC.standard"
    received = send(
        owner,
        url(org, "bank-transactions"),
        {
            "kind": "receive",
            "bank_account": bank_id,
            "date": D,
            "tax_mode": "inclusive",
            "lines": [
                {
                    "account": str(sales.public_id),  # type: ignore[union-attr]
                    "amount": "113.00",
                    "tax_code": "sales.ON.standard",
                }
            ],
        },
    )
    assert received.status_code == 201, received.json()
    assert (received.json()["subtotal"], received.json()["tax_total"]) == ("100.00", "13.00")


def test_code_of_the_other_side_or_unknown_is_400(org: Organisation, owner: Client) -> None:
    """A spend line can't carry a sales code (gap-07): refused with the tax code error."""
    bank_id = bank(owner, org)
    with org_context(org):
        office = Account.objects.filter(type="expense").order_by("code").first()
    for code in ("sales.ON.standard", "nope.XX"):
        refused = send(
            owner,
            url(org, "bank-transactions"),
            {
                "kind": "spend",
                "bank_account": bank_id,
                "date": D,
                "lines": [
                    {"account": str(office.public_id), "amount": "10.00", "tax_code": code}  # type: ignore[union-attr]
                ],
            },
        )
        assert refused.status_code == 400, refused.json()
        assert refused.json()["code"] == "tax.code.unknown"
