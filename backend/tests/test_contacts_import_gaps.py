"""B-03-T14 — gap tests gap-15 / gap-21 for the contacts import (xero_teardown §3).

- gap-15 — Xero's import keeps at most 5 people per contact and a blank person column deletes
  people. Numo9 imports people in long format, unlimited, and a blank cell never deletes;
- gap-21 — Xero matches on the contact name: a renamed contact becomes a duplicate and re-importing
  duplicates. Numo9 matches by external ID / number: re-importing the same file → 0 duplicates and
  0 changes; a renamed contact updates in place.

Also B-03-T13: the template's headers are the mapping fields, in order.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator

import pytest

from numo9.contacts.export import template_csv
from numo9.contacts.importing import CONTACT, PERSON
from numo9.contacts.models import Contact, ContactPerson
from numo9.imports.runs import create_run, dry_run
from numo9.imports.tasks import run_apply
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
COLUMNS = {"External ID": "external_id", "Name": "display_name"}


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def _import(entity: str, text: str, columns: dict[str, str]) -> dict[str, int]:
    run = create_run(entity, text.encode(), "file.csv")
    dry_run(run, columns)
    counts: dict[str, int] = run_apply(run)["counts"]
    return counts


@pytest.mark.gap("gap-21")
def test_reimport_makes_no_duplicates_and_no_changes(org: Organisation) -> None:
    file = "External ID,Name\nX-1,Maple Leaf Supply Ltd.\nX-2,Birch Bakery Co.\n"
    assert _import("contacts.contact", file, COLUMNS)["create"] == 2
    again = _import("contacts.contact", file, COLUMNS)
    assert (again["create"], again["update"], again["unchanged"]) == (0, 0, 2)
    assert Contact.objects.count() == 2


@pytest.mark.gap("gap-21")
def test_renamed_contact_updates_in_place(org: Organisation) -> None:
    _import("contacts.contact", "External ID,Name\nX-1,Maple Leaf Supply Ltd.\n", COLUMNS)
    counts = _import(
        "contacts.contact", "External ID,Name\nX-1,Maple Leaf Supplies Inc.\n", COLUMNS
    )
    assert counts["update"] == 1
    assert list(Contact.objects.values_list("display_name", flat=True)) == [
        "Maple Leaf Supplies Inc."
    ]


@pytest.mark.gap("gap-15")
def test_more_than_five_people_and_blank_never_deletes(org: Organisation) -> None:
    _import("contacts.contact", "External ID,Name\nX-1,Maple Leaf Supply Ltd.\n", COLUMNS)
    people = "Contact,Email\n" + "".join(f"X-1,p{n}@maple.ca\n" for n in range(1, 9))
    columns = {"Contact": "contact_ref", "Email": "email"}
    assert _import("contacts.person", people, columns)["create"] == 8
    blanks = "Contact,Email,Phone\n" + "".join(f"X-1,p{n}@maple.ca,\n" for n in range(1, 3))
    _import("contacts.person", blanks, {**columns, "Phone": "phone"})
    assert ContactPerson.objects.count() == 8  # nobody deleted by blank columns
    assert _import("contacts.contact", "External ID,Name\nX-1,\n", COLUMNS)["unchanged"] == 1


@pytest.mark.parametrize("entity", [CONTACT, PERSON])
def test_template_headers_are_the_mapping_fields(entity: object) -> None:
    headers = next(csv.reader(io.StringIO(template_csv(entity.key).decode("utf-8-sig"))))  # type: ignore[attr-defined]
    assert headers == [str(f.label) for f in entity.fields]  # type: ignore[attr-defined]
