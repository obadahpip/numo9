"""Virus scan of documents (A-06-T04).

Every finalised document is scanned before anyone can open it (status ``scanning``; no signed URL
is given until it is ``clean``). The job streams the object from the bucket to clamd:

- **clean** → status ``clean``, ``scanned_at``; the preview job is started (A-06-T05);
- **infected** → the object moves to the quarantine bucket (same key) and leaves the files bucket;
  status ``infected`` with the signature in ``scan_result``; the person who uploaded it and the
  organisation's owners get an email (``files/email/infected``) — the file is never served;
- **scanner unavailable** → the job raises and A-08 retries it with backoff (up to 8 times); the
  document stays ``scanning`` meanwhile, never "clean by default".
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from numo9.audit.service import record
from numo9.tenancy.models import OrganisationMember, OrganisationRole

from . import storage
from .clamav import scan
from .models import Document, DocumentStatus

CHUNK = 1024 * 1024


def queue_scan(document: Document, *, user: Any = None) -> None:
    """Start the scan job once the current transaction commits (one run per document)."""
    from numo9.jobs.runtime import start_job

    from .tasks import scan_document

    start_job(
        scan_document,
        organisation=document.organisation,
        key=f"scan:{document.public_id}",
        created_by=user,
        document_id=str(document.public_id),
    )


def _chunks(key: str) -> Any:
    body = storage.open_object(key)
    yield from iter(lambda: body.read(CHUNK), b"")


def scan_document(document_id: str) -> dict[str, Any]:
    document = Document.objects.filter(public_id=document_id, deleted_at__isnull=True).first()
    if document is None or document.status != DocumentStatus.SCANNING:
        return {"skipped": True}  # removed meanwhile, or already scanned (a redelivery)
    result = scan(_chunks(document.file_key))
    document.scanned_at = timezone.now()
    if result.clean:
        document.status = DocumentStatus.CLEAN
        document.scan_result = "OK"
        document.save(update_fields=["status", "scan_result", "scanned_at", "updated_at"])
        from .previews import queue_preview

        queue_preview(document)
        return {"status": "clean"}
    storage.move_to_quarantine(document.file_key)
    document.status = DocumentStatus.INFECTED
    document.scan_result = result.signature[:200]
    document.save(update_fields=["status", "scan_result", "scanned_at", "updated_at"])
    record(
        "files.document.quarantined",
        obj=document,
        meta={"signature": document.scan_result, "bucket": "quarantine"},
    )
    transaction.on_commit(lambda: notify_infected(document))
    return {"status": "infected", "signature": document.scan_result}


def recipients(document: Document) -> list[str]:
    """The uploader and the organisation's owners (each address once)."""
    emails: list[str] = []
    if document.created_by is not None:
        emails.append(document.created_by.email)
    owners = OrganisationMember.objects.filter(
        organisation_id=document.organisation_id, role=OrganisationRole.OWNER
    ).select_related("user")
    emails += [m.user.email for m in owners]
    return list(dict.fromkeys(e for e in emails if e))


def notify_infected(document: Document) -> int:
    """Email the uploader and owners that a file was quarantined (A-07 moves this to the
    notification centre)."""
    to = recipients(document)
    if not to:
        return 0
    with translation.override(document.organisation.locale or settings.LANGUAGE_CODE):
        subject = _("A file was quarantined: %(name)s") % {"name": document.name}
        body = _(
            "%(name)s, added to %(organisation)s, contains a virus (%(signature)s). It was moved "
            "to quarantine and can't be opened or downloaded. If you expected this file, ask the "
            "sender for a clean copy."
        ) % {
            "name": document.name,
            "organisation": document.organisation.name,
            "signature": document.scan_result,
        }
    return send_mail(subject, body, None, to)
