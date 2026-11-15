"""Inbound email → documents (A-06-T07).

The email provider (SP-03, chosen with A-07) receives every mail for ``in.<domain>`` and posts each
one to ``POST /api/v1/inbound/email`` as the **raw RFC 822 message**:

- ``X-Numo9-Timestamp`` — Unix seconds when the provider sent it;
- ``X-Numo9-Signature`` — ``hex(HMAC-SHA256(NUMO9_INBOUND_WEBHOOK_SECRET, "<timestamp>." + body))``;
- ``X-Numo9-Recipient`` — the envelope recipient (optional; else To / Cc / Delivered-To are read).

A missing or wrong signature, or a timestamp more than 5 minutes away (replay), is refused (403).
The provider-specific adapter (Postmark, Mailgun or SES payloads → this format) is written when
the provider is chosen; this endpoint is the contract.

``receive(body)`` routes the mail by its ``docs+<token>@`` address (A-06-T06) and records it once
per organisation by ``Message-ID`` (a redelivered webhook is a no-op), keeps the raw message in the
organisation's prefix and starts ``process_inbound``, which stores **one document per attachment**
(``source = email``, the sender, ``sender_known`` when the sender is a member of the organisation or
a person of one of its contacts — unknown senders are accepted and flagged). Each document then
goes through the same checks as an upload (type from content, 25 MB, virus scan). Attachments that
fail are listed on the message (``rejected``), the others are kept.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.audit.service import record as audit
from numo9.catalogue.entitlements import get_resolver
from numo9.i18n.errors import CatalogueError
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

from . import storage
from .inbound import resolve
from .models import DocumentSource, InboundMessage

#: Signed requests older (or newer) than this are refused as replays.
SIGNATURE_TOLERANCE_SECONDS = 300
#: A raw message carries up to 10 attachments of 25 MB, base64-encoded (+37 %).
MAX_MESSAGE_BYTES = 360 * 1024 * 1024
FEATURE = "accounting.documents.write"


class BadSignature(Exception):
    pass


def sign(body: bytes, timestamp: int, secret: str | None = None) -> str:
    key = (secret if secret is not None else settings.NUMO9_INBOUND_WEBHOOK_SECRET).encode()
    return hmac.new(key, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def verify(body: bytes, timestamp: str, signature: str, *, now: float | None = None) -> None:
    secret = settings.NUMO9_INBOUND_WEBHOOK_SECRET
    if not secret:
        raise BadSignature("inbound email is not configured (no webhook secret)")
    try:
        sent = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise BadSignature("missing timestamp") from exc
    if abs((now if now is not None else time.time()) - sent) > SIGNATURE_TOLERANCE_SECONDS:
        raise BadSignature("timestamp outside the tolerance (replay?)")
    if not signature or not hmac.compare_digest(sign(body, sent, secret), signature.lower()):
        raise BadSignature("signature mismatch")


def parse(body: bytes) -> EmailMessage:
    message: EmailMessage = BytesParser(policy=policy.default).parsebytes(body)
    return message


def recipients(message: EmailMessage, envelope: str = "") -> list[str]:
    candidates = [envelope] if envelope else []
    for header in ("Delivered-To", "X-Original-To", "To", "Cc"):
        candidates += [address for _, address in getaddresses(message.get_all(header, []))]
    return [c for c in dict.fromkeys(a.strip() for a in candidates) if c]


@dataclass
class Received:
    status: str  # "queued" | "duplicate" | "unrouted" | "not_in_package"
    message: InboundMessage | None = None


def message_id_of(message: EmailMessage, body: bytes) -> str:
    value = str(message.get("Message-ID", "") or "").strip()
    return value[:998] if value else f"<sha256:{hashlib.sha256(body).hexdigest()}@numo9>"


def receive(body: bytes, envelope_recipient: str = "") -> Received:
    """Route, record once and queue the processing of one raw message."""
    message = parse(body)
    address = next(
        (a for a in map(resolve, recipients(message, envelope_recipient)) if a is not None), None
    )
    if address is None:
        return Received("unrouted")
    organisation = address.organisation
    if not get_resolver().allows(organisation, FEATURE):
        return Received("not_in_package")
    sender = parseaddr(str(message.get("From", "")))[1].lower()
    message_id = message_id_of(message, body)
    with org_context(organisation):
        existing = InboundMessage.objects.filter(message_id=message_id).first()
        if existing is not None:
            return Received("duplicate", existing)
        record = InboundMessage(
            organisation=organisation,
            message_id=message_id,
            sender=sender[:254],
            subject=str(message.get("Subject", ""))[:300],
            recipient=address.address,
            received_at=timezone.now(),
        )
        try:
            with transaction.atomic():
                record.save()
        except IntegrityError:  # the same message delivered twice at the same moment
            return Received("duplicate", InboundMessage.objects.get(message_id=message_id))
        record.raw_key = storage.new_key(organisation, f"inbound-{record.public_id}.eml")
        storage.put_bytes(record.raw_key, body, "message/rfc822")
        record.save(update_fields=["raw_key", "updated_at"])
        _queue(record)
    return Received("queued", record)


def _queue(record: InboundMessage) -> None:
    from numo9.jobs.runtime import start_job

    from .tasks import process_inbound

    start_job(
        process_inbound,
        organisation=record.organisation,
        key=f"inbound:{record.public_id}",
        message_id=str(record.public_id),
    )


def sender_is_known(organisation: Organisation, sender: str) -> bool:
    """A member of the organisation, or a person of one of its contacts."""
    from numo9.contacts.models import ContactPerson

    if not sender:
        return False
    if OrganisationMember.objects.filter(
        organisation=organisation, user__email__iexact=sender
    ).exists():
        return True
    return ContactPerson.objects.filter(email=sender.lower(), deleted_at__isnull=True).exists()


def process(message_public_id: str) -> dict[str, Any]:
    """One document per attachment of a recorded message (runs in its organisation)."""
    from .services import store_received

    record = InboundMessage.objects.filter(public_id=message_public_id).first()
    if record is None or record.processed_at is not None:
        return {"skipped": True}
    message = parse(storage.open_object(record.raw_key).read())
    known = sender_is_known(record.organisation, record.sender)
    stored: list[str] = []
    rejected: list[dict[str, str]] = []
    for part in message.iter_attachments():
        name = part.get_filename() or ""
        data = part.get_payload(decode=True) or b""
        if not isinstance(data, bytes):  # pragma: no cover - a multipart "attachment"
            continue
        try:
            document = store_received(
                record.organisation,
                name,
                data,
                source=DocumentSource.EMAIL,
                sender=record.sender,
                sender_known=known,
                inbound_message=record,
            )
        except CatalogueError as exc:
            rejected.append({"name": name, "code": str(exc.get_codes())})
            continue
        stored.append(str(document.public_id))
    record.attachment_count = len(stored)
    record.rejected = rejected
    record.processed_at = timezone.now()
    record.save(update_fields=["attachment_count", "rejected", "processed_at", "updated_at"])
    audit(
        "files.inbound.processed",
        obj=record,
        object_label=record.subject or record.sender,
        meta={
            "sender": record.sender,
            "sender_known": known,
            "documents": len(stored),
            "rejected": rejected,
            "message_id": record.message_id,
        },
    )
    return {"documents": stored, "rejected": rejected, "sender_known": known}
