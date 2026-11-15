"""A-06-T02 — storage backend, organisation-prefixed keys, signed URL service (5 minutes).

Acceptance: URL expires. The signed URL is SigV4 with ``X-Amz-Expires=300`` — S3, Hetzner Object
Storage and MinIO refuse it after that — and the service reports the moment it expires. Also:
keys under the organisation's prefix, safe names, a key or document of another organisation is
refused, only clean documents are served, inline vs download disposition with the real name,
previews, quarantine moves, the bucket command.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import StringIO
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from django.core.management import call_command
from django.utils import timezone

from numo9.files import storage
from numo9.files.models import Document, DocumentStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def stored(
    org: Organisation, name: str = "Facture été.pdf", data: bytes = b"%PDF-1.4 x"
) -> Document:
    key = storage.new_key(org, name)
    storage.put_bytes(key, data, "application/pdf")
    item = Document(
        organisation=org,
        name=name,
        file_key=key,
        mime="application/pdf",
        size=len(data),
        status=DocumentStatus.CLEAN,
    )
    item.save()
    return item


def query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


# ---- acceptance: the URL expires ----------------------------------------------------------------


def test_signed_urls_expire_after_five_minutes(org: Organisation) -> None:
    item = stored(org)
    before = timezone.now()
    signed = storage.signed_url(item)
    params = query(signed.url)
    assert params["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
    assert params["X-Amz-Expires"] == "300"
    signed_at = datetime.strptime(params["X-Amz-Date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    assert abs((signed_at - before).total_seconds()) < 5
    assert timedelta(seconds=299) <= signed.expires_at - before <= timedelta(seconds=301)
    assert requests.get(signed.url, timeout=10).content == b"%PDF-1.4 x"  # works before expiry


def test_the_lifetime_follows_the_setting(org: Organisation, settings: object) -> None:
    settings.NUMO9_FILES_SIGNED_URL_SECONDS = 60  # type: ignore[attr-defined]
    storage.reset_storages()
    assert query(storage.signed_url(stored(org)).url)["X-Amz-Expires"] == "60"


# ---- keys ---------------------------------------------------------------------------------------


def test_keys_are_under_the_organisation_prefix(org: Organisation) -> None:
    key = storage.new_key(org, "../../etc/passwd")
    assert key.startswith(f"org/{org.public_id}/")
    assert key.endswith("/etc-passwd") and ".." not in key
    assert storage.key_in_org(org, key)
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    assert not storage.key_in_org(other, key)
    assert not storage.key_in_org(org, f"org/{org.public_id}/../{other.public_id}/x")


@pytest.mark.parametrize(
    ("name", "safe"),
    [
        ("Facture été 2026.pdf", "Facture-ete-2026.pdf"),
        ("   ", "file"),
        ("a/b\\c.png", "a-b-c.png"),
    ],
)
def test_safe_file_names(name: str, safe: str) -> None:
    assert storage.safe_filename(name) == safe


# ---- what may be signed --------------------------------------------------------------------


def test_another_organisations_document_is_refused(org: Organisation) -> None:
    item = stored(org)
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with org_context(other), pytest.raises(storage.ForeignDocument):
        storage.signed_url(item)
    with org_context(None), pytest.raises(storage.ForeignDocument):
        storage.signed_url(item)


def test_a_key_outside_the_prefix_is_refused(org: Organisation) -> None:
    item = stored(org)
    item.file_key = "org/someone-else/x.pdf"
    with pytest.raises(storage.ForeignDocument):
        storage.signed_url(item)


@pytest.mark.parametrize(
    "status", [DocumentStatus.UPLOADING, DocumentStatus.SCANNING, DocumentStatus.INFECTED]
)
def test_only_clean_documents_are_served(org: Organisation, status: str) -> None:
    item = stored(org)
    item.status = status
    with pytest.raises(storage.DocumentNotReady):
        storage.signed_url(item)


def test_inline_or_download_with_the_real_name(org: Organisation) -> None:
    item = stored(org)
    inline = query(storage.signed_url(item).url)
    download = query(storage.signed_url(item, download=True).url)
    assert inline["response-content-disposition"].startswith('inline; filename="Facture-ete.pdf"')
    assert "filename*=UTF-8''Facture%20%C3%A9t%C3%A9.pdf" in inline["response-content-disposition"]
    assert download["response-content-disposition"].startswith("attachment;")
    assert inline["response-content-type"] == "application/pdf"


def test_preview_urls_need_a_preview(org: Organisation) -> None:
    item = stored(org)
    with pytest.raises(storage.DocumentNotReady):
        storage.signed_url(item, variant="preview")
    item.preview_key = storage.derived_key(item.file_key, "preview.jpg")
    storage.put_bytes(item.preview_key, b"jpeg", "image/jpeg")
    assert "derived/preview.jpg" in storage.signed_url(item, variant="preview").url


# ---- objects -------------------------------------------------------------------------------


def test_size_hash_head_and_quarantine(org: Organisation) -> None:
    item = stored(org, data=b"hello world")
    assert storage.object_size(item.file_key) == 11
    assert storage.object_size(item.file_key + "-missing") is None
    assert storage.read_head(item.file_key, 5) == b"hello"
    assert storage.sha256_of(item.file_key) == (
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )
    storage.move_to_quarantine(item.file_key)
    assert storage.object_size(item.file_key) is None
    assert storage.object_size(item.file_key, storage.quarantine_storage()) == 11


def test_the_buckets_command_creates_missing_buckets(s3: str) -> None:
    client = storage.client()
    client.delete_bucket(Bucket="numo9-quarantine")
    out = StringIO()
    call_command("files_buckets", stdout=out)
    assert "numo9-files: exists" in out.getvalue()
    assert "numo9-quarantine: created" in out.getvalue()
