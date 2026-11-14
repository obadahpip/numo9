"""A-06-T03 — upload API: presigned POST straight to the bucket + finalize; 25 MB; libmagic.

Acceptance: 26 MB refused; renamed .exe refused. Also: every accepted type passes with its
stored MIME type; a ZIP renamed .xlsx and text renamed .png are refused; refused files leave the
bucket and their document is removed; the declared size and the real size are both checked; empty
files; finalize only once; the presigned form is limited to the organisation's key, 5 minutes and
25 MB; storage outage → 503; permissions.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from botocore.exceptions import EndpointConnectionError
from django.utils import timezone

from numo9.files import storage
from numo9.files.filetypes import DOCX, XLSX
from numo9.files.models import MAX_FILE_SIZE, Document, DocumentStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.files_helpers import (
    CSV,
    EXE,
    OFX,
    PDF,
    api,
    jpeg,
    office,
    owner_of,
    plain_zip,
    png,
    send_to_bucket,
    start_upload,
    upload,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture
def client(org: Organisation) -> Any:
    return api(owner_of(org))


def documents(org: Organisation, **filters: Any) -> list[Document]:
    with org_context(org):
        return list(Document.objects.filter(**filters))


# ---- acceptance -------------------------------------------------------------------------------


def test_26_mb_is_refused_when_declared(client: Any, org: Organisation) -> None:
    response = start_upload(client, org, "scan.pdf", 26 * 1024 * 1024)
    assert response.status_code == 413
    assert response.json()["code"] == "files.too_large"
    assert "26.0 MB" in response.json()["detail"]
    assert documents(org) == []


def test_26_mb_is_refused_when_it_arrives(client: Any, org: Organisation) -> None:
    started = start_upload(client, org, "scan.pdf", 1000)  # declared small, sends 26 MB
    form = started.json()["upload"]
    big = PDF + b"0" * (26 * 1024 * 1024)
    assert send_to_bucket(form, "scan.pdf", big) in (200, 204)
    key = documents(org)[0].file_key
    document_id = started.json()["document"]["id"]
    response = client.post(f"/api/v1/o/{org.public_id}/files/{document_id}/finalize")
    assert response.status_code == 413 and response.json()["code"] == "files.too_large"
    assert storage.object_size(key) is None  # removed from the bucket
    assert documents(org, deleted_at__isnull=True) == []


def test_a_renamed_exe_is_refused(client: Any, org: Organisation) -> None:
    response = upload(client, org, "invoice.pdf", EXE)
    assert response.status_code == 415
    assert response.json()["code"] == "files.type_mismatch"
    detail = response.json()["detail"]  # libmagic names it by version: dosexec or PE
    assert "x-dosexec" in detail or "portable-executable" in detail
    removed = documents(org)[0]
    assert removed.deleted_at is not None and storage.object_size(removed.file_key) is None


def test_an_exe_by_name_is_refused_before_upload(client: Any, org: Organisation) -> None:
    response = start_upload(client, org, "setup.exe", 1000)
    assert response.status_code == 415 and response.json()["code"] == "files.type_not_allowed"


# ---- accepted types ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "data", "stored"),
    [
        ("invoice.pdf", PDF, "application/pdf"),
        ("receipt.png", png(), "image/png"),
        ("receipt.JPG", jpeg(), "image/jpeg"),
        ("ledger.xlsx", office("xlsx"), XLSX),
        ("letter.docx", office("docx"), DOCX),
        ("bank.csv", CSV, "text/csv"),
        ("statement.ofx", OFX, "application/x-ofx"),
        ("statement.qfx", OFX, "application/vnd.intu.qfx"),
    ],
)
def test_accepted_types(
    client: Any, org: Organisation, name: str, data: bytes, stored: str
) -> None:
    response = upload(client, org, name, data)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert (body["mime"], body["size"], body["status"]) == (stored, len(data), "scanning")
    assert len(body["sha256"]) == 64 and body["duplicate"] is False


@pytest.mark.parametrize(
    ("name", "data"),
    [("ledger.xlsx", plain_zip()), ("photo.png", b"just some text"), ("bank.csv", EXE)],
)
def test_content_must_fit_the_extension(
    client: Any, org: Organisation, name: str, data: bytes
) -> None:
    response = upload(client, org, name, data)
    assert response.status_code == 415 and response.json()["code"] == "files.type_mismatch"


def test_empty_files_are_refused(client: Any, org: Organisation) -> None:
    response = start_upload(client, org, "empty.pdf", 0)
    assert response.status_code == 400 and response.json()["code"] == "files.empty"


# ---- flow ---------------------------------------------------------------------------------------


def test_finalize_without_the_file_and_finalize_twice(client: Any, org: Organisation) -> None:
    started = start_upload(client, org, "invoice.pdf", len(PDF))
    url = f"/api/v1/o/{org.public_id}/files/{started.json()['document']['id']}/finalize"
    missing = client.post(url)
    assert missing.status_code == 400 and missing.json()["code"] == "files.upload_missing"
    send_to_bucket(started.json()["upload"], "invoice.pdf", PDF)
    assert client.post(url).status_code == 200
    again = client.post(url)
    assert again.status_code == 409 and again.json()["code"] == "files.not_pending"


def test_the_presigned_form_is_bound_to_the_key_size_and_five_minutes(
    client: Any, org: Organisation
) -> None:
    started = start_upload(client, org, "invoice.pdf", len(PDF)).json()
    fields = started["upload"]["fields"]
    key = fields["key"]
    assert key.startswith(f"org/{org.public_id}/") and key.endswith("/invoice.pdf")
    assert started["document"]["status"] == "uploading" and started["max_size"] == MAX_FILE_SIZE
    policy = json.loads(base64.b64decode(fields["policy"]))
    assert ["content-length-range", 1, MAX_FILE_SIZE] in policy["conditions"]
    assert {"key": key} in policy["conditions"]
    expiry = datetime.fromisoformat(policy["expiration"].replace("Z", "+00:00"))
    assert timedelta(seconds=290) < expiry - timezone.now() <= timedelta(seconds=301)


def test_storage_outage_is_a_503_not_a_server_error(client: Any, org: Organisation) -> None:
    failing = mock.patch.object(
        storage, "presigned_post", side_effect=EndpointConnectionError(endpoint_url="http://s3")
    )
    with failing:
        response = start_upload(client, org, "invoice.pdf", 100)
    assert response.status_code == 503 and response.json()["code"] == "files.storage_unavailable"


def test_detail_of_an_uploaded_document(client: Any, org: Organisation) -> None:
    body = upload(client, org, "invoice.pdf", PDF).json()
    detail = client.get(f"/api/v1/o/{org.public_id}/files/{body['id']}").json()
    assert detail["name"] == "invoice.pdf" and detail["uploaded_by"] == "Dana Lee"
    assert detail["status_label"] == "Checking for viruses"


def test_a_signed_url_waits_for_the_scan(client: Any, org: Organisation) -> None:
    body = upload(client, org, "invoice.pdf", PDF).json()
    url = f"/api/v1/o/{org.public_id}/files/{body['id']}/url"
    waiting = client.get(url)
    assert waiting.status_code == 409 and waiting.json()["code"] == "files.not_ready"
    with org_context(org):
        Document.objects.filter(public_id=body["id"]).update(status=DocumentStatus.CLEAN)
    ready = client.get(url + "?download=1").json()
    assert "X-Amz-Expires=300" in ready["url"] and "attachment" in ready["url"]


def test_uploading_needs_the_permission(org: Organisation) -> None:
    from numo9.accounts.models import User
    from numo9.tenancy.models import OrganisationMember, OrganisationRole

    viewer = User.objects.create_user(email="ro@maple.ca", password="x" * 12, name="Read Only")
    OrganisationMember.objects.create(organisation=org, user=viewer, role=OrganisationRole.EMPLOYEE)
    response = start_upload(api(viewer), org, "invoice.pdf", 100)
    assert response.status_code == 403 and response.json()["code"] == "permission.denied"
