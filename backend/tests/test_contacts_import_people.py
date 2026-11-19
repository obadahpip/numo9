"""B-03-T09 — people long-format import (unlimited people per contact, gap-15).

Acceptance: 12 people for one contact are imported. Rows name the contact by external ID or
number; people are matched by email, else name, within that contact; blank cells change nothing
(re-import → unchanged); an unknown contact reference is reported.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.contacts.models import ContactPerson
from numo9.imports.models import ImportRunRow
from numo9.imports.runs import create_run, dry_run
from numo9.imports.tasks import run_apply
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db
COLUMNS = {
    "Contact": "contact_ref",
    "First": "first_name",
    "Last": "last_name",
    "Email": "email",
    "Primary": "is_primary",
}


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def _csv(rows: list[str]) -> bytes:
    return ("Contact,First,Last,Email,Primary\n" + "\n".join(rows) + "\n").encode()


def _run(data: bytes) -> dict[int, ImportRunRow]:
    run = create_run("contacts.person", data, "people.csv")
    dry_run(run, COLUMNS)
    run_apply(run)
    return {r.row: r for r in ImportRunRow.objects.filter(run=run)}


def test_twelve_people_for_one_contact(org: Organisation) -> None:
    maple = contact(org, "Maple Leaf Supply Ltd.", external_id="X-1")
    rows = [f"X-1,Person{n},Lee,p{n}@maple.ca," for n in range(1, 13)]
    rows[4] = "X-1,Person5,Lee,p5@maple.ca,yes"
    result = _run(_csv([*rows, "NOPE,Ghost,,ghost@x.ca,"]))
    assert ContactPerson.objects.filter(contact=maple).count() == 12
    assert ContactPerson.objects.get(contact=maple, is_primary=True).first_name == "Person5"
    assert result[14].errors[0]["code"] == "contacts.import.contact_unknown"

    again = _run(_csv([f"{maple.number},,,p{n}@maple.ca," for n in range(1, 13)]))
    assert {r.action for r in again.values()} == {"unchanged"}
    assert ContactPerson.objects.filter(contact=maple).count() == 12
