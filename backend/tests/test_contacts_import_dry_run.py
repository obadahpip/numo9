"""B-03-T07 — dry-run report stored as ``ImportRun`` / ``ImportRunRow`` with action and changes.

Acceptance: a dry run writes 0 contacts. A file with a new contact, an update (renamed by
external ID), an unchanged row and two invalid rows gives one stored row each with its action,
before/after changes and reasons; no contact, person or address is written; a duplicate key within
the file is refused on its second row.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.contacts.models import Address, Contact, ContactPerson
from numo9.imports.models import ImportRunRow
from numo9.imports.runs import create_run, dry_run
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db

CSV = (
    "External ID,Name,Email,Province,Postal code\n"
    "X-1,Maple Leaf Supplies Inc.,dana@m.ca,ON,M5V 2T6\n"
    "X-2,Birch Bakery Co.,,,\n"
    "X-3,Cedar Foods,,Ontar,\n"
    "X-4,,,,\n"
    "X-1,Maple again,,,\n"
    "X-9,Pine Ltd.,orders@pine.ca,QC,h2x1y4\n"
)
COLUMNS = {
    "External ID": "external_id",
    "Name": "display_name",
    "Email": "email",
    "Province": "billing_province",
    "Postal code": "billing_postal_code",
}


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def test_dry_run_stores_every_row_and_writes_nothing(org: Organisation) -> None:
    contact(org, "Maple Leaf Supply Ltd.", external_id="X-1")
    contact(org, "Birch Bakery Co.", external_id="X-2")
    before = (Contact.objects.count(), ContactPerson.objects.count(), Address.objects.count())

    run = create_run("contacts.contact", CSV.encode(), "contacts.csv")
    report = dry_run(run, COLUMNS)

    assert (
        Contact.objects.count(),
        ContactPerson.objects.count(),
        Address.objects.count(),
    ) == before
    assert report.counts == {"create": 1, "update": 1, "unchanged": 1, "error": 3}
    rows = {r.row: r for r in ImportRunRow.objects.filter(run=run)}
    assert rows[2].action == "update"
    assert rows[2].changes["display_name"] == ["Maple Leaf Supply Ltd.", "Maple Leaf Supplies Inc."]
    assert rows[2].changes["billing_postal_code"] == ["", "M5V 2T6"]
    assert rows[3].action == "unchanged"
    assert rows[4].errors[0]["code"] == "contacts.import.province"
    assert rows[5].errors[0]["code"] == "contacts.import.required"
    assert rows[6].errors[0]["code"] == "contacts.import.duplicate_row"
    assert rows[7].action == "create" and rows[7].changes["billing_postal_code"][1] == "H2X 1Y4"
    run.refresh_from_db()
    assert (run.status, run.counts["create"]) == ("reviewed", 1)
