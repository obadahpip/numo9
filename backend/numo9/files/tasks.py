"""Background jobs of the documents inbox (A-06): virus scan (T04), previews (T05)."""

from __future__ import annotations

from typing import Any

from numo9.jobs.queues import IO
from numo9.jobs.runtime import org_job

from . import scanning


@org_job(name="numo9.files.scan_document", queue=IO, max_retries=8)
def scan_document(*, org_id: str, document_id: str) -> dict[str, Any]:
    """Scan one document with ClamAV; clean → previews, infected → quarantine + notification."""
    return scanning.scan_document(document_id)


@org_job(name="numo9.files.make_preview", queue=IO, max_retries=3)
def make_preview(*, org_id: str, document_id: str) -> dict[str, Any]:
    """Draw the preview and thumbnail of a clean document."""
    from . import previews

    return previews.make_preview(document_id)


@org_job(name="numo9.files.process_inbound", queue=IO, max_retries=5)
def process_inbound(*, org_id: str, message_id: str) -> dict[str, Any]:
    """Store one document per attachment of an inbound email."""
    from . import inbound_email

    return inbound_email.process(message_id)
