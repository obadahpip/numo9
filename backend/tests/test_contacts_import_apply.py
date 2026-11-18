"""B-03-T08 — apply job: per-row transaction, outcomes stored, audited; re-import → 0 changes.

Acceptance (gap-21): re-importing the same file makes 0 changes and creates 0 duplicates. The
applied run stores each row's outcome; a row the model refuses (bad BN check digit) is reported
while the other rows are imported; the import is one audit batch attributed to the person; the
job is registered.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.contacts.models import Address, Contact
from numo9.imports.models import ImportRunRow
from numo9.imports.runs import create_run, dry_run
from numo9.imports.tasks import JOB, apply_import, run_apply
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db

CSV = (
    "External ID,Name,Roles,BN,Province,Postal code\n"
    "X-1,Maple Leaf Supply Ltd.,Supplier,,ON,M5V 2T6\n"
    "X-2,Birch Bakery Co.,Customer,123456789,,\n"
    "X-3,Cedar Foods Inc.,Customer; Supplier,,QC,H2X 1Y4\n"
)
COLUMNS = {
    "External ID": "external_id",
    "Name": "display_name",
    "Roles": "roles",
    "BN": "bn",
    "Province": "billing_province",
    "Postal code": "billing_postal_code",
}


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


def _import(actor: User | None = None) -> dict[int, ImportRunRow]:
    run = create_run("contacts.contact", CSV.encode(), "contacts.csv", actor=actor)
    dry_run(run, COLUMNS)
    run_apply(run, actor=actor)
    run.refresh_from_db()
    assert run.status == "applied"
    return {r.row: r for r in ImportRunRow.objects.filter(run=run)}


def test_apply_imports_each_row_and_reports_refusals(org: Organisation) -> None:
    person = User.objects.create_user("dana@cpa.ca", password="x" * 12, name="Dana Lee")
    rows = _import(person)
    assert [rows[n].action for n in (2, 3, 4)] == ["create", "error", "create"]
    assert rows[3].errors[0]["field"] == "bn"  # the model's check digit rule
    assert sorted(Contact.objects.values_list("display_name", flat=True)) == [
        "Cedar Foods Inc.",
        "Maple Leaf Supply Ltd.",
    ]
    cedar = Contact.objects.get(external_id="X-3")
    assert sorted(cedar.roles) == ["customer", "supplier"]
    assert Address.objects.get(contact=cedar).postal_code == "H2X 1Y4"
    batch = AuditEvent.objects.filter(action="audit.batch.completed").order_by("-id").first() or (
        AuditEvent.objects.filter(batch_id__isnull=False).order_by("-id").first()
    )
    assert batch is not None and batch.actor_user_id == person.pk


def test_reimporting_the_same_file_changes_nothing(org: Organisation) -> None:
    _import()
    count = Contact.objects.count()
    rows = _import()
    assert [rows[n].action for n in (2, 4)] == ["unchanged", "unchanged"]
    assert Contact.objects.count() == count  # 0 duplicates


def test_the_job_is_registered() -> None:
    assert apply_import.name == JOB
