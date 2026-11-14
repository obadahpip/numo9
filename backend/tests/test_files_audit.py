"""A-06-T15 — documents audit hooks + i18n keys.

Acceptance: events present — every step of a document's life leaves its audit event in the
organisation's log, with a readable label: upload (created), finalise and scan (edited),
quarantine, a duplicate received, edits and tags, bulk archive (one batch), opening the original
(previews aren't logged), attach and detach, inbound address created and rotated, an email
received (with what was refused). Also: the action labels and the files error messages are in
the English and French catalogues (backend .po and frontend JSON).
"""

from __future__ import annotations

import json
import re
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest
from django.test import Client
from django.utils import translation

from numo9.audit.models import AuditEvent
from numo9.audit.presenter import ACTION_LABELS, action_label, type_label
from numo9.files import inbound, scanning
from numo9.files.inbound_email import sign
from numo9.files.models import Document, DocumentStatus
from numo9.files.tasks import process_inbound
from numo9.i18n import errors
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.files_helpers import EICAR, EXE, PDF, FakeClamd, api, owner_of, png, upload
from tests.job_helpers import deliver

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]

ROOT = Path(__file__).resolve().parents[2]
SECRET = "inbound-audit-secret"  # noqa: S105 - test value


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def client(org: Organisation) -> Any:
    return api(owner_of(org))


def files(org: Organisation) -> str:
    return f"/api/v1/o/{org.public_id}/files"


def actions(org: Organisation, **filters: Any) -> list[str]:
    with org_context(org):
        return list(
            AuditEvent.objects.filter(**filters).order_by("id").values_list("action", flat=True)
        )


def clean(org: Organisation, document_id: str) -> Document:
    with org_context(org):
        scanning.scan_document(document_id)
        document: Document = Document.objects.get(public_id=document_id)
    return document


# ---- acceptance: events present -------------------------------------------------------------


def test_a_documents_life_is_in_the_audit_log(
    client: Any, org: Organisation, clamd: FakeClamd
) -> None:
    created = upload(client, org, "bill.pdf", PDF).json()
    document = clean(org, created["id"])
    assert document.status == DocumentStatus.CLEAN
    on_document = {"object_type": "files.Document", "object_id": created["id"]}
    assert actions(org, **on_document)[:2] == ["files.document.created", "files.document.updated"]

    # Edit: period and tags (one event, both fields in the diff).
    client.patch(
        f"{files(org)}/{created['id']}",
        {"period": "2026-10", "tags": ["Hydro"]},
        format="json",
    )
    with org_context(org):
        edit = AuditEvent.objects.filter(**on_document).order_by("id").last()
    assert edit is not None and edit.action == "files.document.updated"
    assert {"period", "tags"} <= set(edit.changes)

    # Opening the original is logged; the preview isn't.
    before = len(actions(org, action="files.document.downloaded"))
    client.get(f"{files(org)}/{created['id']}/url", {"download": "true"})
    client.get(f"{files(org)}/{created['id']}/url", {"variant": "preview"})
    opened = actions(org, action="files.document.downloaded")
    assert len(opened) == before + 1
    with org_context(org):
        meta = AuditEvent.objects.filter(action="files.document.downloaded").last()
    assert meta is not None and meta.meta["download"] is True

    # A duplicate: the existing document records that the same file arrived again.
    upload(client, org, "bill-again.pdf", PDF)
    assert "files.document.duplicate_received" in actions(org, **on_document)

    # Bulk archive: one batch, the document's own edit inside it.
    client.post(f"{files(org)}/bulk", {"ids": [created["id"]], "action": "archive"}, format="json")
    with org_context(org):
        archived = AuditEvent.objects.filter(**on_document).order_by("id").last()
    assert archived is not None and archived.batch_id is not None
    assert archived.changes["folder"][-1] == "archived"

    # Attach and detach.
    with org_context(org):
        maple = contact(org, "Maple Supply Ltd.")
    link = client.post(
        f"{files(org)}/attachments",
        {
            "document": created["id"],
            "record_type": "contacts.Contact",
            "record_id": str(maple.public_id),
        },
        format="json",
    ).json()
    client.delete(f"{files(org)}/attachments/{link['id']}")
    assert actions(org, object_type="files.Attachment") == [
        "files.attachment.created",
        "files.attachment.deleted",
    ]


def test_quarantine_is_logged_with_the_signature(
    client: Any, org: Organisation, clamd: FakeClamd
) -> None:
    created = upload(client, org, "notes.csv", EICAR).json()
    clean(org, created["id"])
    with org_context(org):
        event = AuditEvent.objects.get(action="files.document.quarantined")
    assert event.object_id == created["id"]
    assert event.meta["signature"] == "Eicar-Test-Signature"


def test_inbound_address_creation_and_rotation_are_logged(client: Any, org: Organisation) -> None:
    client.get(f"{files(org)}/inbound-address")
    client.post(f"{files(org)}/inbound-address/rotate")
    trail = actions(org, object_type="files.InboundAddress")
    assert trail.count("files.inboundaddress.created") == 2  # the first address and its successor
    assert "files.inboundaddress.updated" in trail  # the old one, retired with its grace period


def test_an_email_received_is_logged_with_what_was_refused(
    org: Organisation, settings: Any, sent: list[dict[str, Any]]
) -> None:
    settings.NUMO9_INBOUND_WEBHOOK_SECRET = SECRET
    address = inbound.inbound_address(org).address
    message = EmailMessage()
    message["From"] = "Hydro Billing <billing@hydro.example>"
    message["To"] = address
    message["Subject"] = "Your October bill"
    message["Message-ID"] = "<audit-1@hydro.example>"
    message.set_content("Attached.")
    message.add_attachment(PDF, maintype="application", subtype="pdf", filename="bill.pdf")
    message.add_attachment(png(), maintype="image", subtype="png", filename="meter.png")
    message.add_attachment(EXE, maintype="application", subtype="octet-stream", filename="x.exe")
    body = message.as_bytes()
    now = int(time.time())
    Client().post(
        "/api/v1/inbound/email",
        data=body,
        content_type="message/rfc822",
        HTTP_X_NUMO9_TIMESTAMP=str(now),
        HTTP_X_NUMO9_SIGNATURE=sign(body, now, SECRET),
    )
    for job in sent:
        if job["task"] == "numo9.files.process_inbound":
            deliver(process_inbound, job)
    with org_context(org):
        event = AuditEvent.objects.get(action="files.inbound.processed")
    assert event.object_type == "files.InboundMessage"
    assert event.object_label == "Your October bill"
    assert event.meta["sender"] == "billing@hydro.example"
    assert event.meta["sender_known"] is False
    assert event.meta["documents"] == 2
    assert [r["name"] for r in event.meta["rejected"]] == ["x.exe"]
    assert action_label("files.inbound.processed") == "Email received"


# ---- labels and i18n keys -------------------------------------------------------------------

FILES_ACTIONS = {
    "files.document.quarantined",
    "files.document.duplicate_received",
    "files.document.downloaded",
    "files.inbound.processed",
}


def test_every_custom_files_action_has_a_label() -> None:
    assert set(ACTION_LABELS) >= FILES_ACTIONS
    for action in FILES_ACTIONS:
        assert action_label(action) != action
    for object_type, label in (
        ("files.Document", "Document"),
        ("files.Attachment", "Attachment"),
        ("files.InboundMessage", "Inbound email"),
        ("files.InboundAddress", "Inbound address"),
    ):
        assert type_label(object_type) == label


def po_msgids(locale: str) -> set[str]:
    text = (ROOT / "backend" / "locale" / locale / "LC_MESSAGES" / "django.po").read_text("utf-8")
    return {m.replace('\\"', '"') for m in re.findall(r'^msgid "(.+)"$', text, re.MULTILINE)}


@pytest.mark.parametrize("locale", ["en_CA", "fr_CA"])
def test_files_messages_are_in_the_backend_catalogues(locale: str) -> None:
    """The catalogues are written with ``--no-wrap``: one msgid per line."""
    msgids = po_msgids(locale)
    files_errors = [e for name, e in vars(errors).items() if name.startswith("FILES_")]
    assert len(files_errors) >= 10
    with translation.override(None):  # the source text (msgid)
        sources = [str(ACTION_LABELS[a]) for a in FILES_ACTIONS]
        sources += [str(e.message) for e in files_errors]
    for source in sources:
        assert source in msgids, (source, locale)


@pytest.mark.parametrize("locale", ["en-CA", "fr-CA"])
def test_files_keys_are_in_the_frontend_catalogues(locale: str) -> None:
    catalogue = json.loads((ROOT / "frontend" / "messages" / f"{locale}.json").read_text("utf-8"))
    section = catalogue["files"]
    for group in ("address", "attach", "bulk", "col", "create", "grid", "inbox", "uploads"):
        assert group in section, group
