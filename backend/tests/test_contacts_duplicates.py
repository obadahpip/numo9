"""B-01-T10 — duplicate detection service.

Acceptance: typing "Maple Suply" finds "Maple Supply". Also: name keys (case, accents, punctuation,
company forms); similarity threshold 0.6; exact email (people), BN and tax ID matches with their
reasons; the same name in another province is a warning (listed with its province); merged
contacts never, archived ones yes; the contact being edited is excluded; ordering and limit;
names under 3 characters are not compared; the trigram index exists; the active organisation only.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connection

from numo9.contacts.duplicates import (
    NAME_SIMILARITY,
    DuplicateMatch,
    Reason,
    find_duplicates,
    name_key,
    tax_id_key,
)
from numo9.contacts.models import Address, Contact, ContactPerson
from numo9.contacts.tax import contact_province
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
    return contact(org, "Maple Supply Ltd.", bn="123456782", tax_id="US 12-3456789")


def names(matches: list[DuplicateMatch]) -> list[str]:
    return [m.contact.display_name for m in matches]


# ---- acceptance -------------------------------------------------------------------------------


def test_typing_maple_suply_finds_maple_supply(maple: Contact) -> None:
    matches = find_duplicates(name="Maple Suply")
    assert names(matches) == ["Maple Supply Ltd."]
    assert matches[0].reasons == [Reason.NAME]
    assert matches[0].similarity is not None and matches[0].similarity >= NAME_SIMILARITY
    assert not matches[0].is_exact


# ---- name keys ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Maple Supply Ltd.", "maple supply"),
        ("MAPLE SUPPLY LIMITED", "maple supply"),
        ("Érable Distribution Ltée", "erable distribution"),
        ("Les Entreprises Côté S.E.N.C.", "les entreprises cote"),
        ("The Corner Store Inc.", "corner store"),
        ("Smith & Sons Co. Ltd", "smith and sons"),
        ("Inc.", "inc"),  # nothing but a company form: kept
        ("Co-op Atlantic", "co op atlantic"),
    ],
)
def test_name_keys(name: str, key: str) -> None:
    assert name_key(name) == key


def test_the_name_key_is_kept_up_to_date(maple: Contact) -> None:
    assert maple.name_key == "maple supply"
    maple.display_name = "Maple Supplies (Ontario) Inc."
    maple.save(update_fields=["display_name", "updated_at"])
    maple.refresh_from_db()
    assert maple.name_key == "maple supplies ontario"


def test_accents_and_company_forms_do_not_hide_a_duplicate(org: Organisation) -> None:
    contact(org, "Érable Distribution Ltée")
    assert names(find_duplicates(name="erable distribution inc")) == ["Érable Distribution Ltée"]
    assert names(find_duplicates(name="ÉRABLE DISTRIBUTIONS")) == ["Érable Distribution Ltée"]


def test_names_below_the_threshold_are_not_listed(org: Organisation, maple: Contact) -> None:
    contact(org, "Pacific Coast Foods")
    assert find_duplicates(name="Atlantic Fisheries") == []
    assert find_duplicates(name="Maple Grove Bakery") == []


def test_short_names_are_not_compared(maple: Contact) -> None:
    assert find_duplicates(name="Ma") == []
    assert find_duplicates(name="") == []


# ---- exact identifiers --------------------------------------------------------------------------


def test_same_email_bn_or_tax_id(org: Organisation, maple: Contact) -> None:
    ContactPerson(contact=maple, first_name="Anne", email="ap@maplesupply.ca").save()
    assert find_duplicates(email=" AP@MapleSupply.ca ")[0].reasons == [Reason.EMAIL]
    assert find_duplicates(bn="123 456 782 RT 0001")[0].reasons == [Reason.BN]
    assert find_duplicates(tax_id="us123456789")[0].reasons == [Reason.TAX_ID]
    assert tax_id_key("us 12-345/678.9") == "US123456789"
    assert find_duplicates(bn="12345678") == []  # not a BN: not compared


def test_removed_people_do_not_match(maple: Contact) -> None:
    anne = ContactPerson(contact=maple, first_name="Anne", email="ap@maplesupply.ca")
    anne.save()
    anne.soft_delete()
    assert find_duplicates(email="ap@maplesupply.ca") == []


def test_all_reasons_of_one_contact_are_combined(maple: Contact) -> None:
    ContactPerson(contact=maple, first_name="Anne", email="ap@maplesupply.ca").save()
    (match,) = find_duplicates(
        name="Maple Suply", email="ap@maplesupply.ca", bn="123456782", tax_id="US123456789"
    )
    assert match.reasons == [Reason.BN, Reason.TAX_ID, Reason.EMAIL, Reason.NAME]
    assert match.is_exact


# ---- warnings, not blocks -----------------------------------------------------------------------


def test_same_name_in_another_province_is_listed_with_its_province(org: Organisation) -> None:
    ontario = contact(org, "Northern Supply")
    Address(contact=ontario, kind="billing", province="ON").save()
    quebec = contact(org, "Northern Supply")  # saving the second one is allowed
    Address(contact=quebec, kind="billing", province="QC").save()
    matches = find_duplicates(name="Northern Supply", exclude=quebec)
    assert [(m.contact.pk, contact_province(m.contact)) for m in matches] == [(ontario.pk, "ON")]


def test_merged_contacts_are_never_listed_archived_ones_are(
    org: Organisation, maple: Contact
) -> None:
    merged = contact(org, "Maple Suppy")
    merged.soft_delete()  # what a merge does to the merged contact (B-01-T12)
    maple.archive()
    matches = find_duplicates(name="Maple Supply")
    assert names(matches) == ["Maple Supply Ltd."] and matches[0].contact.is_archived


def test_the_contact_being_edited_is_excluded(maple: Contact) -> None:
    assert find_duplicates(name="Maple Supply", bn="123456782", exclude=maple) == []


# ---- ordering, limit, index, organisation -------------------------------------------------------


def test_exact_matches_come_first_then_by_similarity(org: Organisation) -> None:
    contact(org, "Maple Supply")
    contact(org, "Maple Supplies")
    by_bn = contact(org, "Something Else Entirely", bn="123456782")
    matches = find_duplicates(name="Maple Supply", bn="123456782")
    assert matches[0].contact.pk == by_bn.pk
    assert names(matches[1:]) == ["Maple Supply", "Maple Supplies"]


def test_the_limit_applies(org: Organisation) -> None:
    for i in range(15):
        contact(org, f"Maple Supply {i}")
    assert len(find_duplicates(name="Maple Supply", limit=5)) == 5
    assert len(find_duplicates(name="Maple Supply")) == 10


def test_the_trigram_index_exists() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = %s",
            ["contacts_contact_name_trgm_idx"],
        )
        (definition,) = cursor.fetchone()
    assert "gin_trgm_ops" in definition and "name_key" in definition


def test_only_the_active_organisation_is_searched(maple: Contact) -> None:
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert find_duplicates(name="Maple Supply", bn="123456782") == []
