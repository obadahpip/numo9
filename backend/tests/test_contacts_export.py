"""B-03-T10 — export CSV/XLSX in importable shape (round trip).

Acceptance: export → import = 0 changes. Contacts with roles, BN, credit limit, a primary person
and both addresses, plus a merged alias (not exported), are exported as CSV and XLSX; importing
either file back with the automatic mapping finds every column and reports every row unchanged;
people export in long format and re-import unchanged too.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest

from numo9.contacts.export import export_csv, export_xlsx
from numo9.contacts.merge import merge_contacts
from numo9.contacts.models import Address, ContactPerson
from numo9.imports.mapping import as_columns, resolve
from numo9.imports.runs import create_run, dry_run
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def _world(org: Organisation) -> None:
    maple = contact(
        org,
        "Maple Leaf Supply Ltd.",
        roles=["customer", "supplier"],
        bn="123456782",
        external_id="X-1",
        credit_limit=Decimal("5000.00"),
        credit_mode="block",
    )
    ContactPerson(
        organisation=org, contact=maple, first_name="Dana", email="dana@m.ca", phone="416-555-0100"
    ).save()
    ContactPerson(organisation=org, contact=maple, first_name="Sam", email="sam@m.ca").save()
    Address(
        organisation=org,
        contact=maple,
        kind="billing",
        line1="1 King St W",
        city="Toronto",
        province="ON",
        postal_code="M5V 2T6",
    ).save()
    Address(
        organisation=org,
        contact=maple,
        kind="shipping",
        city="Seattle",
        country="US",
        region="WA",
        postal_code="98101",
    ).save()
    contact(org, "Birch Bakery Co.", t4a_flag=True, language="fr-ca")
    merge_contacts(contact(org, "Cedar Foods Inc."), contact(org, "Cedar Foods"))


@pytest.mark.parametrize(
    ("entity", "export", "name"),
    [
        ("contacts.contact", export_csv, "contacts.csv"),
        ("contacts.contact", export_xlsx, "contacts.xlsx"),
        ("contacts.person", export_csv, "people.csv"),
    ],
)
def test_export_then_import_changes_nothing(
    org: Organisation, entity: str, export: object, name: str
) -> None:
    _world(org)
    data = export(entity)  # type: ignore[operator]
    run = create_run(entity, data, name)
    columns = as_columns(resolve(entity, run.headers))
    assert all(columns.values()), columns  # every exported column maps back by itself
    report = dry_run(run, columns)
    assert report.counts["error"] == 0, [r.errors for r in report.rows if r.errors]
    assert report.counts["create"] == report.counts["update"] == 0
    assert report.counts["unchanged"] == (3 if entity == "contacts.contact" else 2)
