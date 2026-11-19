"""B-01-T06 — sales/purchase defaults on a contact (accounts from C-01, payment terms, amounts).

Acceptance: the account picker is validated by type. A sales default must be an account a sales
line may use (revenue, other income…), a purchase default one a bill may use (expenses, assets);
an expense as sales default, revenue as purchase default, a bank or engine (AR) account, an
archived account or another organisation's account is refused with the field and a code; payment
terms must be this organisation's active terms; "amounts are" defaults to tax exclusive.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError

from numo9.contacts.models import AmountsAre, Contact, PaymentTerm, seed_payment_terms
from numo9.ledger.archive import archive_account
from numo9.ledger.models import Account
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def chart(org: Organisation) -> dict[str, Account]:
    return {
        "sales": account(org, "4000", "Sales", subtype="revenue", gifi_id="8000"),
        "supplies": account(org, "6100", "Office supplies", gifi_id="8811"),
        "equipment": account(org, "1700", "Equipment", subtype="fixed_asset", gifi_id="1740"),
        "bank": account(org, "1000", "Chequing", subtype="bank", gifi_id="1001"),
        "ar": account(
            org, "1100", "Accounts receivable", subtype="current_asset", system_role="ar"
        ),
    }


def _refused(item: Contact) -> dict[str, list[str]]:
    with pytest.raises(ValidationError) as caught:
        item.save()
    return {
        field: [e.code or "" for e in errors] for field, errors in caught.value.error_dict.items()
    }


def test_defaults_that_fit_are_saved(org: Organisation, chart: dict[str, Account]) -> None:
    seed_payment_terms(org)
    net30 = PaymentTerm.objects.filter(days=30).order_by("position").first()
    assert net30 is not None
    item = contact(
        org,
        "Maple Leaf Supply Ltd.",
        roles=["customer", "supplier"],
        sales_account=chart["sales"],
        sales_payment_term=net30,
        purchase_account=chart["equipment"],
        purchase_payment_term=net30,
        purchase_amounts_are=AmountsAre.TAX_INCLUSIVE,
    )
    stored = Contact.objects.get(pk=item.pk)
    assert (stored.sales_account, stored.purchase_account) == (chart["sales"], chart["equipment"])
    assert stored.sales_amounts_are == AmountsAre.TAX_EXCLUSIVE  # the default
    assert stored.purchase_amounts_are == AmountsAre.TAX_INCLUSIVE


@pytest.mark.parametrize(
    ("field", "key"),
    [
        ("sales_account", "supplies"),  # an expense on sales lines
        ("sales_account", "bank"),
        ("sales_account", "ar"),  # the engine posts to AR itself
        ("purchase_account", "sales"),  # revenue on bills
        ("purchase_account", "bank"),
    ],
)
def test_account_that_doesnt_fit_its_side_is_refused(
    org: Organisation, chart: dict[str, Account], field: str, key: str
) -> None:
    item = Contact(
        organisation=org, display_name="Birch Ltd.", roles=["customer"], **{field: chart[key]}
    )
    assert _refused(item) == {field: [f"contacts.defaults.{field}"]}


def test_archived_or_other_organisations_account_is_refused(
    org: Organisation, chart: dict[str, Account]
) -> None:
    archive_account(chart["supplies"])
    item = Contact(organisation=org, display_name="Birch Ltd.", roles=["supplier"])
    item.purchase_account = Account.objects.get(pk=chart["supplies"].pk)
    assert "purchase_account" in _refused(item)

    other = Organisation.objects.create(name="Other Inc.")
    with org_context(other):
        theirs = account(other, "4000", "Their sales", subtype="revenue", gifi_id="8000")
    item = Contact(organisation=org, display_name="Cedar Ltd.", roles=["customer"])
    item.sales_account = theirs
    assert "sales_account" in _refused(item)


def test_payment_term_must_be_this_organisations_and_active(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Inc.")
    seed_payment_terms(other)
    with org_context(other):
        theirs = PaymentTerm.objects.first()
    item = Contact(organisation=org, display_name="Birch Ltd.", roles=["customer"])
    item.sales_payment_term = theirs
    assert _refused(item) == {"sales_payment_term": ["contacts.defaults.payment_term"]}
