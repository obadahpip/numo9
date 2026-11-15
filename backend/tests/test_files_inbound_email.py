"""A-06-T07 — inbound webhook → parse MIME → one document per attachment; signature; idempotent.

Acceptance: an email lands in less than 60 s, in the right organisation (webhook + processing job
timed together). Also: 10 attachments → 10 documents; HMAC signature, replay window and missing
secret refused; duplicate Message-ID is a no-op; unknown address is reported, not stored; unknown
senders accepted and flagged, members and contact people known; refused attachments listed while
the others are kept; no session or CSRF needed; organisations without the feature skipped.
"""

from __future__ import annotations

import time
from email.message import EmailMessage
from typing import Any
from unittest import mock

import pytest
from django.test import Client

from numo9.contacts.models import ContactPerson
from numo9.files import inbound, storage
from numo9.files.inbound_email import sign
from numo9.files.models import Document, DocumentSource, DocumentStatus, InboundMessage
from numo9.files.tasks import process_inbound
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.files_helpers import EXE, PDF, owner_of, png
from tests.job_helpers import deliver

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]

SECRET = "inbound-test-secret"  # noqa: S105 - test value
URL = "/api/v1/inbound/email"


@pytest.fixture(autouse=True)
def _secret(settings: Any) -> None:
    settings.NUMO9_INBOUND_WEBHOOK_SECRET = SECRET


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def other() -> Organisation:
    return Organisation.objects.create(name="Northern Lights Ltd.")


def email(
    to: str,
    attachments: list[tuple[str, bytes, str]],
    sender: str = "billing@hydro.example",
    message_id: str = "<m-1@hydro.example>",
) -> bytes:
    message = EmailMessage()
    message["From"] = f"Hydro Billing <{sender}>"
    message["To"] = to
    message["Subject"] = "Your October bill"
    message["Message-ID"] = message_id
    message.set_content("Your bill is attached.")
    for name, data, mime in attachments:
        maintype, subtype = mime.split("/")
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return message.as_bytes()


def post(
    body: bytes,
    *,
    timestamp: int | None = None,
    signature: str | None = None,
    recipient: str = "",
) -> Any:
    sent = int(time.time()) if timestamp is None else timestamp
    return Client().post(
        URL,
        data=body,
        content_type="message/rfc822",
        HTTP_X_NUMO9_TIMESTAMP=str(sent),
        HTTP_X_NUMO9_SIGNATURE=signature if signature is not None else sign(body, sent, SECRET),
        headers={"X-Numo9-Recipient": recipient} if recipient else None,
    )


def process_all(sent: list[dict[str, Any]]) -> list[Any]:
    return [deliver(process_inbound, m) for m in sent if m["task"] == "numo9.files.process_inbound"]


def docs(org: Organisation) -> list[Document]:
    with org_context(org):
        return list(Document.objects.filter(deleted_at__isnull=True).order_by("name"))


# ---- acceptance ---------------------------------------------------------------------------------


def test_an_email_lands_in_the_right_organisation_within_60_seconds(
    org: Organisation, other: Organisation, sent: list[dict[str, Any]]
) -> None:
    inbound.inbound_address(other)  # another organisation with its own address
    address = inbound.inbound_address(org).address
    started = time.perf_counter()
    response = post(email(address, [("bill.pdf", PDF, "application/pdf")]))
    process_all(sent)
    elapsed = time.perf_counter() - started
    assert response.status_code == 202 and response.json()["status"] == "queued"
    assert elapsed < 60
    (document,) = docs(org)
    assert docs(other) == []
    assert (document.name, document.source, document.status) == (
        "bill.pdf",
        DocumentSource.EMAIL,
        DocumentStatus.SCANNING,
    )
    assert document.sender == "billing@hydro.example" and document.mime == "application/pdf"
    assert document.inbound_message is not None
    assert document.inbound_message.subject == "Your October bill"


def test_ten_attachments_make_ten_documents(org: Organisation, sent: list[dict[str, Any]]) -> None:
    address = inbound.inbound_address(org).address
    files = [(f"receipt-{i}.png", png((20 + i, 20)), "image/png") for i in range(10)]
    post(email(address, files))
    (result,) = process_all(sent)
    assert len(result["documents"]) == 10 and len(docs(org)) == 10
    with org_context(org):
        assert InboundMessage.objects.get().attachment_count == 10


# ---- signature ----------------------------------------------------------------------------------


def test_a_bad_signature_is_refused(org: Organisation) -> None:
    body = email(inbound.inbound_address(org).address, [("bill.pdf", PDF, "application/pdf")])
    response = post(body, signature="0" * 64)
    assert response.status_code == 403 and response.json()["code"] == "files.inbound_signature"
    assert docs(org) == []


def test_an_old_request_is_refused_as_a_replay(org: Organisation) -> None:
    body = email(inbound.inbound_address(org).address, [])
    assert post(body, timestamp=int(time.time()) - 301).status_code == 403
    assert post(body, timestamp=int(time.time()) - 200).status_code == 202


def test_no_secret_means_inbound_is_off(org: Organisation, settings: Any) -> None:
    settings.NUMO9_INBOUND_WEBHOOK_SECRET = ""
    body = email(inbound.inbound_address(org).address, [])
    assert post(body, signature=sign(body, int(time.time()), "")).status_code == 403


# ---- routing, idempotency -----------------------------------------------------------------------


def test_the_same_message_twice_is_stored_once(
    org: Organisation, sent: list[dict[str, Any]]
) -> None:
    body = email(inbound.inbound_address(org).address, [("bill.pdf", PDF, "application/pdf")])
    first, second = post(body), post(body)
    assert first.json()["status"] == "queued" and second.json()["status"] == "duplicate"
    assert first.json()["message"] == second.json()["message"]
    process_all(sent)
    process_all(sent)  # a redelivered job does nothing twice
    assert len(docs(org)) == 1


def test_an_unknown_address_is_reported_not_stored(org: Organisation) -> None:
    response = post(email("docs+zzzzzzzzzzzz@in.numo9.ca", [("bill.pdf", PDF, "application/pdf")]))
    assert response.status_code == 202 and response.json() == {"status": "unrouted"}


def test_the_envelope_recipient_routes_a_bcc(org: Organisation) -> None:
    address = inbound.inbound_address(org).address
    body = email("accounts@maple.example", [])
    assert post(body, recipient=address).json()["status"] == "queued"


def test_the_raw_message_is_kept_in_the_organisation_prefix(org: Organisation) -> None:
    body = email(inbound.inbound_address(org).address, [])
    post(body)
    with org_context(org):
        record = InboundMessage.objects.get()
    assert storage.key_in_org(org, record.raw_key)
    assert storage.open_object(record.raw_key).read() == body


def test_organisations_without_the_feature_are_skipped(org: Organisation) -> None:
    body = email(inbound.inbound_address(org).address, [])
    with mock.patch("numo9.files.inbound_email.get_resolver") as resolver:
        resolver.return_value.allows.return_value = False
        assert post(body).json() == {"status": "not_in_package"}


# ---- senders and refused attachments ------------------------------------------------------------


def test_unknown_senders_are_flagged_and_known_ones_are_not(
    org: Organisation, sent: list[dict[str, Any]]
) -> None:
    owner_of(org, "dana@maple.ca")
    with org_context(org):
        hydro = contact(org, "Hydro One", roles=["supplier"])
        ContactPerson(contact=hydro, first_name="Billing", email="billing@hydro.example").save()
    address = inbound.inbound_address(org).address
    post(
        email(
            address,
            [("a.pdf", PDF + b"%a", "application/pdf")],
            sender="billing@hydro.example",
            message_id="<1@x>",
        )
    )
    post(
        email(
            address,
            [("b.pdf", PDF + b"%b", "application/pdf")],
            sender="Dana@Maple.ca",
            message_id="<2@x>",
        )
    )
    post(
        email(
            address,
            [("c.pdf", PDF + b"%c", "application/pdf")],
            sender="spam@unknown.example",
            message_id="<3@x>",
        )
    )
    process_all(sent)
    assert [(d.name, d.sender_known) for d in docs(org)] == [
        ("a.pdf", True),
        ("b.pdf", True),
        ("c.pdf", False),
    ]


def test_refused_attachments_are_listed_and_the_others_kept(
    org: Organisation, sent: list[dict[str, Any]]
) -> None:
    address = inbound.inbound_address(org).address
    post(
        email(
            address,
            [
                ("bill.pdf", PDF, "application/pdf"),
                ("invoice.pdf", EXE, "application/pdf"),
                ("setup.exe", EXE, "application/octet-stream"),
            ],
        )
    )
    (result,) = process_all(sent)
    assert [d.name for d in docs(org)] == ["bill.pdf"]
    assert result["rejected"] == [
        {"name": "invoice.pdf", "code": "files.type_mismatch"},
        {"name": "setup.exe", "code": "files.type_not_allowed"},
    ]
