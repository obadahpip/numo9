"""B-03-T05 — matcher: external ID → number → opt-in BN, never the name.

Acceptance: a renamed contact is matched by its ID. The external ID wins, then the contact number
(a merged contact's number leads to the survivor), then the BN only when opted in and unique; a
row with only a name never matches (a new contact); keys pointing at two contacts are refused.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.contacts.import_match import match_contact
from numo9.contacts.merge import merge_contacts
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def test_renamed_contact_is_matched_by_its_id_never_by_name(org: Organisation) -> None:
    maple = contact(org, "Maple Leaf Supply Ltd.", external_id="XERO-17", bn="123456782")
    renamed = match_contact({"external_id": "XERO-17", "display_name": "Maple Leaf Supplies Inc."})
    assert (renamed.contact, renamed.by) == (maple, "external_id")
    assert match_contact({"number": maple.number.lower()}).contact == maple
    assert match_contact({"display_name": "Maple Leaf Supply Ltd."}).contact is None
    assert match_contact({"bn": "123456782"}).contact is None  # BN only when opted in
    assert match_contact({"bn": "123456782"}, match_bn=True).by == "bn"


def test_merged_contacts_number_leads_to_the_survivor(org: Organisation) -> None:
    survivor = contact(org, "Maple Leaf Supply Ltd.")
    merged = contact(org, "Maple Leaf Suply")
    merge_contacts(survivor, merged)
    assert match_contact({"number": merged.number}).contact == survivor


def test_keys_pointing_at_two_contacts_are_refused(org: Organisation) -> None:
    first = contact(org, "Maple Leaf Supply Ltd.", external_id="A-1")
    second = contact(org, "Birch Bakery Co.")
    found = match_contact({"external_id": "A-1", "number": second.number})
    assert found.contact is None and str(first) in found.conflict and str(second) in found.conflict
