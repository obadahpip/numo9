"""A-06-T09 — attach/detach documents to any organisation record; list a record's attachments.

Acceptance: attach to a contact works. Also: list newest first with the document; attaching twice
is one link (200); detach keeps the document and the history; a record of another organisation,
an unknown record or a non-record type is refused; quarantined documents can't be attached;
permissions (view to list, manage to attach); audit events.
"""

from __future__ import annotations

from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.contacts.models import Contact
from numo9.files.models import Attachment, Document, DocumentStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.contact_helpers import contact
from tests.files_helpers import PDF, api, owner_of, png, upload

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def client(org: Organisation) -> Any:
    return api(owner_of(org))


@pytest.fixture
def maple(org: Organisation) -> Contact:
    with org_context(org):
        return contact(org, "Maple Supply Ltd.")


def base(org: Organisation) -> str:
    return f"/api/v1/o/{org.public_id}/files/attachments"


def attach(
    client: Any,
    org: Organisation,
    document: str,
    record: Any,
    record_type: str = "contacts.Contact",
) -> Any:
    return client.post(
        base(org),
        {"document": document, "record_type": record_type, "record_id": str(record)},
        format="json",
    )


def listing(client: Any, org: Organisation, record: Any) -> Any:
    return client.get(base(org), {"record_type": "contacts.Contact", "record_id": str(record)})


# ---- acceptance -----------------------------------------------------------------------------


def test_attach_to_a_contact_works(client: Any, org: Organisation, maple: Contact) -> None:
    bill = upload(client, org, "bill.pdf", PDF).json()
    receipt = upload(client, org, "receipt.png", png()).json()
    first = attach(client, org, bill["id"], maple.public_id)
    assert first.status_code == 201
    assert first.json()["record_type"] == "contacts.Contact"
    assert first.json()["record_id"] == str(maple.public_id)
    assert first.json()["attached_by"] == "Dana Lee"
    attach(client, org, receipt["id"], maple.public_id)
    names = [a["document"]["name"] for a in listing(client, org, maple.public_id).json()["results"]]
    assert names == ["receipt.png", "bill.pdf"]  # newest first


# ---- links ----------------------------------------------------------------------------------


def test_attaching_twice_is_one_link(client: Any, org: Organisation, maple: Contact) -> None:
    bill = upload(client, org, "bill.pdf", PDF).json()
    assert attach(client, org, bill["id"], maple.public_id).status_code == 201
    again = attach(client, org, bill["id"], maple.public_id)
    assert again.status_code == 200
    with org_context(org):
        assert Attachment.objects.filter(deleted_at__isnull=True).count() == 1


def test_detach_keeps_the_document_and_the_history(
    client: Any, org: Organisation, maple: Contact
) -> None:
    bill = upload(client, org, "bill.pdf", PDF).json()
    link = attach(client, org, bill["id"], maple.public_id).json()
    assert client.delete(f"{base(org)}/{link['id']}").status_code == 204
    assert listing(client, org, maple.public_id).json()["results"] == []
    assert client.delete(f"{base(org)}/{link['id']}").status_code == 404
    with org_context(org):
        assert Document.objects.filter(public_id=bill["id"], deleted_at__isnull=True).exists()
        actions = list(
            AuditEvent.objects.filter(object_type="files.Attachment")
            .order_by("id")
            .values_list("action", flat=True)
        )
    assert actions == ["files.attachment.created", "files.attachment.deleted"]


def test_a_document_attaches_to_several_records(client: Any, org: Organisation) -> None:
    bill = upload(client, org, "bill.pdf", PDF).json()
    with org_context(org):
        one, two = contact(org, "One"), contact(org, "Two")
    for record in (one, two):
        assert attach(client, org, bill["id"], record.public_id).status_code == 201
    assert len(listing(client, org, two.public_id).json()["results"]) == 1


# ---- refused --------------------------------------------------------------------------------


def test_records_of_another_organisation_or_unknown_are_404(client: Any, org: Organisation) -> None:
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other):
        theirs = contact(other, "Theirs")
    bill = upload(client, org, "bill.pdf", PDF).json()
    assert attach(client, org, bill["id"], theirs.public_id).status_code == 404
    assert (
        attach(client, org, bill["id"], "6f1c1a52-0000-4000-8000-000000000000").status_code == 404
    )
    assert listing(client, org, theirs.public_id).status_code == 404


@pytest.mark.parametrize("record_type", ["accounts.User", "files.Attachment", "nope.Thing", "x"])
def test_only_organisation_records_take_documents(
    client: Any, org: Organisation, maple: Contact, record_type: str
) -> None:
    bill = upload(client, org, "bill.pdf", PDF).json()
    response = attach(client, org, bill["id"], maple.public_id, record_type=record_type)
    assert response.status_code == 400 and response.json()["code"] == "files.record_type"


def test_quarantined_documents_cant_be_attached(
    client: Any, org: Organisation, maple: Contact
) -> None:
    bill = upload(client, org, "bill.pdf", PDF).json()
    with org_context(org):
        Document.objects.filter(public_id=bill["id"]).update(status=DocumentStatus.INFECTED)
    response = attach(client, org, bill["id"], maple.public_id)
    assert response.status_code == 409 and response.json()["code"] == "files.quarantined"


def test_attaching_needs_manage_and_listing_needs_view(
    client: Any, org: Organisation, maple: Contact
) -> None:
    bill = upload(client, org, "bill.pdf", PDF).json()
    hr = User.objects.create_user(email="hr@maple.ca", password="x" * 12, name="Hana")
    OrganisationMember.objects.create(organisation=org, user=hr, role=OrganisationRole.HR)
    reader = api(hr)  # HR: documents read-only
    assert listing(reader, org, maple.public_id).status_code == 200
    assert attach(reader, org, bill["id"], maple.public_id).status_code == 403
