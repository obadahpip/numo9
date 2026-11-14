"""A-06-T08 — duplicate detection by SHA-256 within the organisation (link, don't store twice).

Acceptance: the same file twice → one object. Also: the second upload answers with the existing
document (``duplicate: true``) and leaves no second object or document; a renamed copy is still a
duplicate; the same file in another organisation is stored there; a quarantined copy doesn't count;
an emailed copy of an uploaded file is linked; the event is in the existing document's history.
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.files import services, storage
from numo9.files.models import Document, DocumentSource, DocumentStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.files_helpers import PDF, api, owner_of, upload

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def client(org: Organisation) -> Any:
    return api(owner_of(org))


def objects() -> list[str]:
    listing = storage.client().list_objects_v2(Bucket=storage.files_storage().bucket_name)
    return [item["Key"] for item in listing.get("Contents", [])]


def live(org: Organisation) -> list[Document]:
    with org_context(org):
        return list(Document.objects.filter(deleted_at__isnull=True))


def test_the_same_file_twice_is_one_object(client: Any, org: Organisation) -> None:
    first = upload(client, org, "bill.pdf", PDF).json()
    second = upload(client, org, "bill.pdf", PDF).json()
    assert second["duplicate"] is True and second["id"] == first["id"]
    assert len(objects()) == 1
    assert [d.name for d in live(org)] == ["bill.pdf"]


def test_a_renamed_copy_is_a_duplicate(client: Any, org: Organisation) -> None:
    first = upload(client, org, "bill.pdf", PDF).json()
    again = upload(client, org, "October hydro.pdf", PDF).json()
    assert again["id"] == first["id"] and again["name"] == "bill.pdf"
    with org_context(org):
        event = AuditEvent.objects.get(action="files.document.duplicate_received")
    assert event.object_id == first["id"] and event.meta["name"] == "October hydro.pdf"


def test_another_organisation_stores_its_own_copy(client: Any, org: Organisation) -> None:
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    upload(client, org, "bill.pdf", PDF)
    theirs = upload(api(owner_of(other, "lee@northern.ca")), other, "bill.pdf", PDF).json()
    assert theirs["duplicate"] is False
    assert len(objects()) == 2 and len(live(other)) == 1


def test_a_quarantined_copy_does_not_count(client: Any, org: Organisation) -> None:
    first = upload(client, org, "bill.pdf", PDF).json()
    with org_context(org):
        Document.objects.filter(public_id=first["id"]).update(status=DocumentStatus.INFECTED)
    again = upload(client, org, "bill.pdf", PDF).json()
    assert again["duplicate"] is False and again["id"] != first["id"]


def test_an_emailed_copy_links_to_the_uploaded_document(client: Any, org: Organisation) -> None:
    first = upload(client, org, "bill.pdf", PDF).json()
    with org_context(org):
        linked = services.store_received(
            org, "scan.pdf", PDF, source=DocumentSource.EMAIL, sender="billing@hydro.example"
        )
    assert str(linked.public_id) == first["id"]
    assert len(objects()) == 1 and len(live(org)) == 1
