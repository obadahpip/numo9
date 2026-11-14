"""A-06-T01 — Document and Attachment models.

Acceptance: the migration creates the tables. Also: defaults (uploading, upload, inbox, preview
pending); statuses and folders checked by the database; 25 MB limit; period YYYY-MM and tax-year
range; tags tidied, limited and checked; attachments link a document to any record of the same
organisation once; row-level security; audit; scoping.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction

from numo9.audit.models import AuditEvent
from numo9.contacts.models import Contact
from numo9.files.models import (
    MAX_FILE_SIZE,
    Attachment,
    Document,
    DocumentSource,
    DocumentStatus,
    Folder,
    PreviewStatus,
)
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


def document(org: Organisation, name: str = "invoice.pdf", **fields: Any) -> Document:
    item = Document(organisation=org, name=name, file_key=f"org/{org.public_id}/x/{name}", **fields)
    item.save()
    return item


def codes(excinfo: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return {f: [e.code or "" for e in errs] for f, errs in excinfo.value.error_dict.items()}


@pytest.mark.parametrize("table", ["files_document", "files_attachment", "files_inboundmessage"])
def test_migration_creates_the_tables_with_row_level_security(table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s", [table]
        )
        assert cursor.fetchone() == (True, True)


def test_defaults(org: Organisation) -> None:
    item = document(org)
    assert (item.status, item.source, item.folder, item.preview_status) == (
        DocumentStatus.UPLOADING,
        DocumentSource.UPLOAD,
        Folder.INBOX,
        PreviewStatus.PENDING,
    )
    assert item.extension == "pdf" and item.tags == [] and item.sender_known


def test_the_database_checks_statuses_size_and_key(org: Organisation) -> None:
    item = document(org)
    for change in (
        {"status": "lost"},
        {"folder": "trash"},
        {"size": MAX_FILE_SIZE + 1},
        {"period": "2026-13"},
        {"tax_year": 1800},
        {"file_key": ""},
    ):
        with pytest.raises(IntegrityError), transaction.atomic():
            Document.objects.filter(pk=item.pk).update(**change)


def test_25_mb_limit(org: Organisation) -> None:
    assert document(org, size=MAX_FILE_SIZE).size == MAX_FILE_SIZE
    with pytest.raises(ValidationError) as excinfo:
        document(org, size=MAX_FILE_SIZE + 1)
    assert codes(excinfo) == {"size": ["files.size.too_large"]}


def test_period_and_tax_year(org: Organisation) -> None:
    assert document(org, period="2026-10", tax_year=2026).period == "2026-10"
    with pytest.raises(ValidationError) as excinfo:
        document(org, period="10/2026", tax_year=3000)
    assert codes(excinfo) == {
        "period": ["files.period.format"],
        "tax_year": ["files.tax_year.range"],
    }


def test_tags_are_tidied_limited_and_checked(org: Organisation) -> None:
    item = document(org, tags=[" GST  return ", "gst return", "Q3", ""])
    assert item.tags == ["GST return", "Q3"]
    with pytest.raises(ValidationError) as excinfo:
        document(org, tags=[f"tag {i}" for i in range(21)])
    assert codes(excinfo) == {"tags": ["files.tags.limit"]}
    with pytest.raises(ValidationError) as excinfo:
        document(org, tags=["<script>"])
    assert codes(excinfo) == {"tags": ["files.tags.format"]}


def test_attachment_links_a_document_to_a_record_once(org: Organisation) -> None:
    item = document(org)
    maple: Contact = contact(org, "Maple Supply Ltd.")
    ct = ContentType.objects.get_for_model(Contact)
    link = Attachment(
        organisation=org, document=item, content_type=ct, object_public_id=maple.public_id
    )
    link.save()
    assert link.record_type == "contacts.Contact"
    with pytest.raises(IntegrityError), transaction.atomic():
        Attachment(
            organisation=org, document=item, content_type=ct, object_public_id=maple.public_id
        ).save()
    link.soft_delete()
    Attachment(
        organisation=org, document=item, content_type=ct, object_public_id=maple.public_id
    ).save()  # detached: may be attached again


def test_an_attachment_stays_in_its_organisation(org: Organisation) -> None:
    item = document(org)
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    stray = Attachment(
        organisation=other,
        document=item,
        content_type=ContentType.objects.get_for_model(Contact),
        object_public_id=item.public_id,
    )
    with pytest.raises(ValidationError):
        stray.save()


def test_changes_are_audited_and_rows_scoped(org: Organisation) -> None:
    item = document(org)
    item.period = "2026-09"
    item.save()
    actions = list(
        AuditEvent.objects.filter(object_type="files.Document")
        .order_by("id")
        .values_list("action", flat=True)
    )
    assert actions == ["files.document.created", "files.document.updated"]
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        assert Document.objects.count() == 0
