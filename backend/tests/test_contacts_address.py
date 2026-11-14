"""B-01-T04 — contact addresses (billing / shipping) and their Canadian validators.

Acceptance: "M5V 2T6" valid; "12345" invalid for CA. Also: forgiving postal-code input stored
normalised; the 13 provinces and territories; postal code and province must agree; addresses
outside Canada keep region and postal code as free text and refuse a province; one billing and one
shipping address per contact; printed lines; the contact's organisation; audit; row-level security.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from numo9.audit.models import AuditEvent
from numo9.contacts.models import Address, AddressKind, Contact
from numo9.orgsettings.validators import Province
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def maple(org: Organisation) -> Contact:
    return contact(org, "Maple Supply Ltd.")


def address(item: Contact, kind: str = AddressKind.BILLING, **fields: str) -> Address:
    a = Address(contact=item, kind=kind, **fields)
    a.save()
    return a


def codes(excinfo: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return {f: [e.code or "" for e in errs] for f, errs in excinfo.value.error_dict.items()}


# ---- acceptance -------------------------------------------------------------------------------


def test_a_canadian_postal_code_is_valid(maple: Contact) -> None:
    a = address(maple, line1="200 King St W", city="Toronto", province="ON", postal_code="M5V 2T6")
    a.refresh_from_db()
    assert (a.province, a.postal_code, a.country) == ("ON", "M5V 2T6", "CA")


def test_a_zip_code_is_invalid_for_canada(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        address(maple, city="Toronto", province="ON", postal_code="12345")
    assert codes(excinfo) == {"postal_code": ["orgsettings.postal_code.invalid"]}
    assert not Address.objects.exists()


# ---- Canadian rules -----------------------------------------------------------------------------


@pytest.mark.parametrize("typed", ["m5v2t6", " M5V  2T6 ", "m5v-2t6"])
def test_postal_code_input_is_forgiving(maple: Contact, typed: str) -> None:
    assert address(maple, province="on", postal_code=typed).postal_code == "M5V 2T6"


@pytest.mark.parametrize("bad", ["D5V 2T6", "M5V 2T", "W1A 1A1", "M5V2T6X"])
def test_malformed_postal_codes_are_refused(maple: Contact, bad: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        address(maple, province="ON", postal_code=bad)
    assert codes(excinfo) == {"postal_code": ["orgsettings.postal_code.invalid"]}


@pytest.mark.parametrize("province", Province.values)
def test_every_province_and_territory_is_accepted(maple: Contact, province: str) -> None:
    assert address(maple, province=province).province == province


def test_an_unknown_province_is_refused_also_by_the_database(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        address(maple, province="ZZ")
    assert codes(excinfo) == {"province": ["orgsettings.province.invalid"]}
    a = address(maple, province="QC")
    with pytest.raises(IntegrityError), transaction.atomic():
        Address.objects.filter(pk=a.pk).update(province="ZZ")


def test_postal_code_and_province_must_agree(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        address(maple, province="QC", postal_code="M5V 2T6")
    assert codes(excinfo) == {"postal_code": ["orgsettings.postal_code.province_mismatch"]}
    assert address(maple, province="QC", postal_code="H2Y 1C6").postal_code == "H2Y 1C6"


def test_a_canadian_address_may_be_partial(maple: Contact) -> None:
    a = address(maple, line1="1 Rue Principale", city="Gatineau")
    assert (a.province, a.postal_code) == ("", "")


# ---- other countries ----------------------------------------------------------------------------


def test_an_address_outside_canada_uses_region_and_free_postal_code(maple: Contact) -> None:
    a = address(
        maple,
        kind=AddressKind.SHIPPING,
        line1="350 5th Ave",
        city="New York",
        region="NY",
        postal_code="10118",
        country="us",
    )
    a.refresh_from_db()
    assert (a.country, a.region, a.postal_code, a.province) == ("US", "NY", "10118", "")
    assert a.lines() == ["350 5th Ave", "New York NY 10118", "US"]


def test_a_province_outside_canada_is_refused(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        address(maple, province="ON", country="US")
    assert codes(excinfo) == {"province": ["contacts.address.province_outside_canada"]}


def test_country_must_be_a_two_letter_code(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        address(maple, country="Canada")
    assert "country" in codes(excinfo)


# ---- one per kind, lines, organisation, audit, RLS ---------------------------------------------


def test_one_billing_and_one_shipping_address_per_contact(maple: Contact) -> None:
    address(maple, AddressKind.BILLING, city="Toronto")
    address(maple, AddressKind.SHIPPING, city="Mississauga")
    with pytest.raises(ValidationError) as excinfo:
        address(maple, AddressKind.BILLING, city="Ottawa")
    assert codes(excinfo) == {"kind": ["contacts.address.kind_taken"]}
    with pytest.raises(IntegrityError), transaction.atomic():
        Address.objects.bulk_create(
            [Address(organisation=maple.organisation, contact=maple, kind="billing")]
        )
    old = maple.addresses.get(kind=AddressKind.BILLING)
    old.soft_delete()
    assert address(maple, AddressKind.BILLING, city="Ottawa").city == "Ottawa"


def test_printed_lines_of_a_canadian_address(maple: Contact) -> None:
    a = address(
        maple,
        attention="Accounts payable",
        line1="200 King St W",
        line2="Suite 1400",
        city="Toronto",
        province="ON",
        postal_code="m5v2t6",
    )
    assert a.lines() == ["Accounts payable", "200 King St W", "Suite 1400", "Toronto ON M5V 2T6"]
    assert str(a) == "Accounts payable, 200 King St W, Suite 1400, Toronto ON M5V 2T6"


def test_the_address_belongs_to_the_contact_organisation(org: Organisation, maple: Contact) -> None:
    assert address(maple, city="Toronto").organisation_id == org.pk
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    stray = Address(contact=maple, organisation=other, kind="shipping")
    with pytest.raises(ValidationError) as excinfo:
        stray.save()
    assert codes(excinfo) == {"contact": ["contacts.address.contact"]}


def test_address_changes_are_audited(maple: Contact) -> None:
    a = address(maple, city="Toronto", province="ON")
    a.city = "Ottawa"
    a.save()
    events = list(
        AuditEvent.objects.filter(object_type="contacts.Address", object_id=str(a.public_id))
        .order_by("id")
        .values_list("action", "changes")
    )
    assert [action for action, _ in events] == [
        "contacts.address.created",
        "contacts.address.updated",
    ]
    assert events[1][1] == {"city": ["Toronto", "Ottawa"]}


def test_the_address_table_has_row_level_security() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["contacts_address"],
        )
        assert cursor.fetchone() == (True, True)
