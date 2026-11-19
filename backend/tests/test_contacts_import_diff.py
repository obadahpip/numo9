"""B-03-T06 — non-destructive diff engine (blank cells never clear, ``__CLEAR__`` does).

Acceptance: blank cell → unchanged (unit + property). The diff lists before/after per field,
including the primary person's email and the addresses; applying it changes exactly those
fields; ``CLEAR`` empties; a property test over random rows with blanks shows a blank never
changes a stored value.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.contacts.import_diff import CONTACT_FIELDS, apply, diff
from numo9.contacts.import_normalise import normalise_row
from numo9.contacts.models import Address, Contact, ContactPerson
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def _maple(org: Organisation) -> Contact:
    item = contact(org, "Maple Leaf Supply Ltd.", legal_name="Maple Leaf Supply", tax_id="X-1")
    ContactPerson(organisation=org, contact=item, first_name="Dana", email="dana@m.ca").save()
    Address(organisation=org, contact=item, kind="billing", city="Toronto", province="ON").save()
    return item


def test_diff_and_apply_change_exactly_what_the_row_says(org: Organisation) -> None:
    maple = _maple(org)
    values = normalise_row(
        {
            "display_name": "Maple Leaf Supplies Inc.",
            "legal_name": "",
            "tax_id": "__CLEAR__",
            "email": "orders@m.ca",
            "billing_city": "Ottawa",
            "billing_province": "",
        }
    ).values
    changes = diff(maple, values)
    assert changes == {
        "display_name": ["Maple Leaf Supply Ltd.", "Maple Leaf Supplies Inc."],
        "tax_id": ["X-1", ""],
        "email": ["dana@m.ca", "orders@m.ca"],
        "billing_city": ["Toronto", "Ottawa"],
    }
    apply(maple, changes)
    maple.refresh_from_db()
    assert (maple.display_name, maple.legal_name, maple.tax_id) == (
        "Maple Leaf Supplies Inc.",
        "Maple Leaf Supply",
        "",
    )
    assert ContactPerson.objects.get(contact=maple).email == "orders@m.ca"
    billing = Address.objects.get(contact=maple)
    assert (billing.city, billing.province) == ("Ottawa", "ON")
    assert diff(maple, values) == {}  # applying again changes nothing


def test_a_new_contact_diff_lists_every_given_value(org: Organisation) -> None:
    values = normalise_row({"display_name": "Birch Bakery Co.", "roles": "customer"}).values
    assert diff(None, values) == {
        "display_name": ["", "Birch Bakery Co."],
        "roles": ["", ["customer"]],
    }


TEXT_FIELDS = ("display_name", "legal_name", "tax_id", "email", "billing_city", "billing_line1")


@settings(
    max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
)
@given(
    cells=st.fixed_dictionaries(
        {},
        optional={
            key: st.one_of(
                st.just(""), st.just("   "), st.text(alphabet="abc XYZ", min_size=1, max_size=8)
            )
            for key in TEXT_FIELDS
        },
    )
)
def test_property_a_blank_cell_never_changes_a_stored_value(
    org: Organisation, cells: dict[str, str]
) -> None:
    maple = Contact.objects.filter(display_name="Maple Leaf Supply Ltd.").first() or _maple(org)
    if "email" in cells and cells["email"].strip():
        cells["email"] = "x@y.ca"
    changes = diff(maple, normalise_row(cells).values)
    for key, value in cells.items():
        if not value.strip():
            assert key not in changes, (key, changes)
    assert set(changes) <= set(CONTACT_FIELDS) | {"email", "phone"} | {
        f"{k}_{p}"
        for k in ("billing", "shipping")
        for p in ("line1", "line2", "city", "province", "postal_code", "country")
    }
