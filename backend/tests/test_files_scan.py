"""A-06-T04 — virus scan job via clamd; infected → quarantine bucket + notification.

Acceptance: EICAR file quarantined. Also: the clamd INSTREAM protocol and its answers; a clean
file becomes ready and its preview job starts; the scan runs as a background job started when the
upload is finalised (once per document); a scanner that is down or answers ERROR leaves the file
"scanning" and the job retries; the uploader and owners are emailed; quarantined files are never
served; a redelivered scan does nothing twice. Real ClamAV: set NUMO9_TEST_CLAMD_HOST to run
``test_real_clamd_finds_eicar`` against it.
"""

from __future__ import annotations

import contextlib
import os
import socket
from collections.abc import Iterator
from typing import Any

import pytest
from django.core import mail

from numo9.audit.models import AuditEvent
from numo9.files import clamav, scanning, storage
from numo9.files.models import Document, DocumentStatus
from numo9.files.tasks import make_preview, scan_document
from numo9.jobs.models import JobRun, JobStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.files_helpers import EICAR, PDF, FakeClamd, api, owner_of, upload
from tests.job_helpers import deliver

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def client(org: Organisation) -> Any:
    return api(owner_of(org))


@pytest.fixture
def active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def finalised(client: Any, org: Organisation, name: str, data: bytes) -> Document:
    response = upload(client, org, name, data)
    assert response.status_code == 200, response.json()
    with org_context(org):
        document: Document = Document.objects.get(public_id=response.json()["id"])
    return document


# ---- acceptance ---------------------------------------------------------------------------------


def test_an_eicar_file_is_quarantined(client: Any, org: Organisation, clamd: FakeClamd) -> None:
    item = finalised(client, org, "bill.csv", EICAR)
    with org_context(org):
        assert scanning.scan_document(str(item.public_id)) == {
            "status": "infected",
            "signature": "Eicar-Test-Signature",
        }
        item.refresh_from_db()
    assert item.status == DocumentStatus.INFECTED and item.scan_result == "Eicar-Test-Signature"
    assert storage.object_size(item.file_key) is None  # gone from the files bucket
    assert storage.object_size(item.file_key, storage.quarantine_storage()) == len(EICAR)
    with org_context(org):
        event = AuditEvent.objects.get(action="files.document.quarantined")
    assert event.meta["signature"] == "Eicar-Test-Signature"
    with org_context(org), pytest.raises(storage.DocumentNotReady):
        storage.signed_url(item)


def test_the_uploader_and_owners_are_emailed(
    client: Any, org: Organisation, clamd: FakeClamd, django_capture_on_commit_callbacks: Any
) -> None:
    item = finalised(client, org, "bill.csv", EICAR)
    with org_context(org), django_capture_on_commit_callbacks(execute=True):
        scanning.scan_document(str(item.public_id))
    (message,) = mail.outbox
    assert message.to == ["dana@maple.ca"]
    assert message.subject == "A file was quarantined: bill.csv"
    assert "Eicar-Test-Signature" in message.body and "can't be opened" in message.body


# ---- clean files ---------------------------------------------------------------------------


def test_a_clean_file_becomes_ready_and_its_preview_starts(
    client: Any, org: Organisation, clamd: FakeClamd, sent: list[dict[str, Any]]
) -> None:
    item = finalised(client, org, "invoice.pdf", PDF)
    scan_message = next(m for m in sent if m["task"] == "numo9.files.scan_document")
    assert deliver(scan_document, scan_message) == {"status": "clean"}
    with org_context(org):
        item.refresh_from_db()
    assert item.status == DocumentStatus.CLEAN and item.scanned_at is not None
    assert clamd.scanned == [PDF]
    assert [m["task"] for m in sent].count("numo9.files.make_preview") == 1
    assert deliver(scan_document, scan_message) == {"status": "clean"}  # redelivery: stored result


def test_finalising_starts_one_scan_job(
    client: Any, org: Organisation, sent: list[dict[str, Any]]
) -> None:
    item = finalised(client, org, "invoice.pdf", PDF)
    runs = JobRun.platform_runs.filter(task_name="numo9.files.scan_document")
    assert runs.count() == 1
    assert runs.get().payload["document_id"] == str(item.public_id)
    assert [m["task"] for m in sent] == ["numo9.files.scan_document"]


# ---- scanner problems ----------------------------------------------------------------------


def test_a_scanner_that_is_down_is_retried_and_the_file_stays_scanning(
    client: Any, org: Organisation, settings: Any, sent: list[dict[str, Any]]
) -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()  # nothing listens there
    settings.NUMO9_CLAMD_HOST, settings.NUMO9_CLAMD_PORT = "127.0.0.1", free_port
    settings.NUMO9_CLAMD_TIMEOUT = 2
    item = finalised(client, org, "invoice.pdf", PDF)
    message = next(m for m in sent if m["task"] == "numo9.files.scan_document")
    with contextlib.suppress(Exception):  # how the retry surfaces depends on eager Celery
        deliver(scan_document, message)
    run = JobRun.platform_runs.get(task_name="numo9.files.scan_document")
    # eager Celery runs the retries at once: every try failed, the run ends in the dead letters
    assert run.attempts == scan_document.max_retries + 1
    assert run.status in (JobStatus.RETRYING, JobStatus.DEAD)
    with org_context(org):
        item.refresh_from_db()
    assert item.status == DocumentStatus.SCANNING


def test_an_error_answer_is_not_clean(
    client: Any, org: Organisation, settings: Any, active: None
) -> None:
    errorful = FakeClamd(mode="error")
    settings.NUMO9_CLAMD_HOST, settings.NUMO9_CLAMD_PORT = "127.0.0.1", errorful.port
    with pytest.raises(clamav.ScannerUnavailable):
        clamav.scan([b"data"])
    errorful.close()


@pytest.mark.parametrize(
    ("line", "result"),
    [
        ("stream: OK", clamav.ScanResult(clean=True)),
        ("stream: Win.Test.EICAR_HDB-1 FOUND", clamav.ScanResult(False, "Win.Test.EICAR_HDB-1")),
    ],
)
def test_answers(line: str, result: clamav.ScanResult) -> None:
    assert clamav.parse(line) == result


def test_large_files_are_streamed_in_chunks(clamd: FakeClamd) -> None:
    data = b"A" * (3 * clamav.CHUNK + 17)
    assert clamav.scan([data[:100_000], data[100_000:]]).clean
    assert clamd.scanned == [data]


def test_a_removed_or_already_scanned_document_is_skipped(
    client: Any, org: Organisation, clamd: FakeClamd
) -> None:
    item = finalised(client, org, "invoice.pdf", PDF)
    with org_context(org):
        assert scanning.scan_document(str(item.public_id)) == {"status": "clean"}
        assert scanning.scan_document(str(item.public_id)) == {"skipped": True}
    assert len(clamd.scanned) == 1
    assert make_preview.name == "numo9.files.make_preview"


@pytest.mark.skipif(not os.environ.get("NUMO9_TEST_CLAMD_HOST"), reason="needs a ClamAV daemon")
def test_real_clamd_finds_eicar(settings: Any) -> None:
    settings.NUMO9_CLAMD_HOST = os.environ["NUMO9_TEST_CLAMD_HOST"]
    settings.NUMO9_CLAMD_PORT = int(os.environ.get("NUMO9_TEST_CLAMD_PORT", "3310"))
    assert not clamav.scan([EICAR]).clean
    assert clamav.scan([PDF]).clean
