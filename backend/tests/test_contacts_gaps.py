"""B-01-T19 — gap tests gap-19 / gap-20 for contacts, and the QC → GST+QST fixture.

Each test observes a row of the Phase 0 gap table (xero_teardown §3.1, §3.2):

- gap-19 — Xero infers customer/supplier from transactions, so a brand-new contact is in neither
  list. Numo9 sets roles explicitly on the contact: a new customer is a customer at once, a
  contact can be both, and every role list filters on the stored roles (the titled list screens
  are B-01-T14's Playwright check);
- gap-20 — Xero has no contact currency, no withholding/T4A flag, no duplicate warning and only
  "block" for the credit limit. Numo9 contacts carry a currency (ISO 4217), a T4A flag, a credit
  limit with warn or block, duplicates are found while typing (name, email, BN, tax ID) and every
  organisation has a payment-terms master (B-01-T05). The exemption certificate (B-01-T08) and the
  credit override approval (B-01-T13) join this gap's tests with their tasks;
- fixture — one customer per province and territory (``fixtures/contacts_ca/contacts.json``): each
  defaults to its province's sales tax, and the Quebec contact to GST + QST (deliverable
  acceptance).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.contacts.duplicates import Reason, find_duplicates
from numo9.contacts.models import Address, AddressKind, Contact, ContactRole, CreditMode
from numo9.contacts.tax import contact_tax_hint
from numo9.orgsettings.validators import Province
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "contacts_ca" / "contacts.json").read_text("utf-8")
)
AS_OF = date.fromisoformat(FIXTURE["as_of"])


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def load_fixture(org: Organisation) -> dict[str, Contact]:
    loaded = {}
    for row in FIXTURE["contacts"]:
        item = contact(org, row["display_name"], roles=row["roles"])
        Address(contact=item, kind=AddressKind.BILLING, **row["billing"]).save()
        loaded[row["billing"]["province"]] = item
    return loaded


def in_role(role: str) -> list[str]:
    return sorted(
        Contact.objects.filter(roles__contains=[role], status="active").values_list(
            "display_name", flat=True
        )
    )


# ---- gap-19: explicit roles ---------------------------------------------------------------------


@pytest.mark.gap("gap-19")
def test_a_new_contact_is_in_its_role_list_before_any_transaction(org: Organisation) -> None:
    contact(org, "Brand New Customer", roles=["customer"])
    contact(org, "Brand New Supplier", roles=["supplier"])
    assert in_role(ContactRole.CUSTOMER) == ["Brand New Customer"]
    assert in_role(ContactRole.SUPPLIER) == ["Brand New Supplier"]


@pytest.mark.gap("gap-19")
def test_roles_are_set_on_the_contact_and_a_contact_can_have_several(org: Organisation) -> None:
    both = contact(org, "Érable Distribution inc.", roles=["customer", "supplier"])
    contact(org, "Canada Revenue Agency", roles=["government_agency"])
    contact(org, "Jordan Contractor", roles=["contractor"])
    assert both.is_customer and both.is_supplier
    assert (
        in_role(ContactRole.CUSTOMER)
        == in_role(ContactRole.SUPPLIER)
        == ["Érable Distribution inc."]
    )
    assert in_role(ContactRole.GOVERNMENT_AGENCY) == ["Canada Revenue Agency"]
    assert in_role(ContactRole.CONTRACTOR) == ["Jordan Contractor"]


@pytest.mark.gap("gap-19")
def test_a_role_is_never_inferred_and_always_required(org: Organisation) -> None:
    with pytest.raises(ValidationError) as excinfo:
        contact(org, "No role", roles=[])
    assert excinfo.value.error_dict["roles"][0].code == "contacts.roles.required"


@pytest.mark.gap("gap-19")
def test_archived_contacts_leave_the_role_lists(org: Organisation) -> None:
    item = contact(org, "Old Customer", roles=["customer"])
    item.archive()
    assert in_role(ContactRole.CUSTOMER) == []
    assert Contact.objects.filter(status="archived").count() == 1


# ---- gap-20: currency, withholding, duplicates, credit warn vs block ---------------------------


@pytest.mark.gap("gap-20")
def test_contacts_have_a_currency(org: Organisation) -> None:
    assert contact(org, "Canadian").currency == "CAD"
    assert contact(org, "Northern Lights Studio", currency="usd").currency == "USD"


@pytest.mark.gap("gap-20")
def test_organisations_have_a_payment_terms_master(org: Organisation) -> None:
    from numo9.contacts.models import PaymentTerm

    codes = set(PaymentTerm.objects.values_list("code", flat=True))
    assert {"due_on_receipt", "net_15", "net_30", "net_60", "2_10_net_30", "eom"} <= codes


@pytest.mark.gap("gap-20")
def test_contacts_have_a_t4a_withholding_flag(org: Organisation) -> None:
    item = contact(org, "Jordan Contractor", roles=["contractor"], t4a_flag=True)
    item.refresh_from_db()
    assert item.t4a_flag is True


@pytest.mark.gap("gap-20")
def test_credit_limit_can_warn_or_block(org: Organisation) -> None:
    warn = contact(org, "Warn me", credit_limit=Decimal("5000"))
    block = contact(org, "Block me", credit_limit=Decimal("25000"), credit_mode="block")
    assert (warn.credit_mode, block.credit_mode) == (CreditMode.WARN, CreditMode.BLOCK)


@pytest.mark.gap("gap-20")
def test_duplicates_are_found_while_typing(org: Organisation) -> None:
    contact(org, "Maple Supply Ltd.", bn="123456782", tax_id="US 12-3456789")
    assert [m.reasons for m in find_duplicates(name="Maple Suply")] == [[Reason.NAME]]
    assert find_duplicates(bn="123456782")[0].reasons == [Reason.BN]
    assert find_duplicates(tax_id="US123456789")[0].reasons == [Reason.TAX_ID]


# ---- fixture: every province defaults to its own sales tax, QC → GST+QST ---------------------


def test_the_fixture_covers_every_province_and_territory() -> None:
    provinces = sorted(row["billing"]["province"] for row in FIXTURE["contacts"])
    assert provinces == sorted(Province.values)


@pytest.mark.gap("gap-20")
def test_quebec_contact_defaults_to_gst_and_qst(org: Organisation) -> None:
    quebec = load_fixture(org)["QC"]
    hint = contact_tax_hint(quebec, AS_OF)
    assert quebec.display_name == "Érable Distribution inc."
    assert hint is not None and hint.code == "GST+QST"
    assert hint.label == "GST 5 % + QST 9.975 %"


def test_every_fixture_contact_defaults_to_its_province_tax(org: Organisation) -> None:
    loaded = load_fixture(org)
    expected = {row["billing"]["province"]: row["expected_tax_hint"] for row in FIXTURE["contacts"]}
    actual = {
        province: getattr(contact_tax_hint(item, AS_OF), "code", None)
        for province, item in loaded.items()
    }
    assert actual == expected
