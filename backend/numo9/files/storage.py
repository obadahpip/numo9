"""Object storage for documents (A-06-T02): S3-compatible buckets, organisation-prefixed keys,
signed URLs.

- **Buckets** — ``files`` (every stored document, its preview and thumbnail) and ``quarantine``
  (infected files, never served). Hetzner Object Storage in staging/prod (ADR-0002), MinIO in the
  dev stack (``manage.py files_buckets`` creates them). Accessed through django-storages'
  ``S3Storage`` (SigV4, path-style addressing — MinIO and Hetzner both accept it).
- **Keys** — every object of an organisation lives under ``org/<organisation public id>/``:
  ``org/<id>/2026/11/<random>/<safe file name>``. ``key_in_org()`` is checked before any key is
  read, finalised or signed, so a key of Org 1 can never be used from Org 2.
- **Signed URLs** — ``signed_url(document)``: a presigned ``GET`` valid 5 minutes
  (``NUMO9_FILES_SIGNED_URL_SECONDS``; S3/MinIO refuse it after ``X-Amz-Expires``), only for a
  clean document of the active organisation, with the file name in ``Content-Disposition``
  (inline to preview, attachment to download).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache
from typing import IO, Any
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone
from storages.backends.s3 import S3Storage

from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

CHUNK = 1024 * 1024


class ForeignDocument(LookupError):
    """The document or key belongs to another organisation (answered as 404)."""


class DocumentNotReady(RuntimeError):
    """The document isn't clean yet (uploading, scanning) or is quarantined: nothing to serve."""


def _storage(bucket: str) -> S3Storage:
    return S3Storage(
        bucket_name=bucket,
        endpoint_url=settings.NUMO9_FILES_S3_ENDPOINT_URL or None,
        region_name=settings.NUMO9_FILES_S3_REGION or None,
        access_key=settings.NUMO9_FILES_S3_ACCESS_KEY or None,
        secret_key=settings.NUMO9_FILES_S3_SECRET_KEY or None,
        signature_version="s3v4",
        addressing_style="path",
        default_acl=None,
        file_overwrite=False,
        querystring_auth=True,
        querystring_expire=settings.NUMO9_FILES_SIGNED_URL_SECONDS,
    )


@cache
def files_storage() -> S3Storage:
    return _storage(settings.NUMO9_FILES_BUCKET)


@cache
def quarantine_storage() -> S3Storage:
    return _storage(settings.NUMO9_FILES_QUARANTINE_BUCKET)


def reset_storages() -> None:
    """Forget the cached storages (tests that change the settings)."""
    files_storage.cache_clear()
    quarantine_storage.cache_clear()


def client(storage: S3Storage | None = None) -> Any:
    return (storage or files_storage()).connection.meta.client


# ---- keys -------------------------------------------------------------------------------------


def org_prefix(organisation: Organisation) -> str:
    return f"org/{organisation.public_id}/"


def safe_filename(name: str) -> str:
    """A storage-safe version of a file name: ``Facture été 2026.pdf`` → ``Facture-ete-2026.pdf``
    (the real name is kept on the document)."""
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w.\-]+", "-", text).strip(".-")[-100:]
    return text or "file"


def new_key(organisation: Organisation, filename: str, *, now: datetime | None = None) -> str:
    moment = now or timezone.now()
    return f"{org_prefix(organisation)}{moment:%Y/%m}/{uuid.uuid4().hex}/{safe_filename(filename)}"


def derived_key(file_key: str, name: str) -> str:
    """Key of an object made from a document (preview, thumbnail), next to it."""
    return f"{file_key.rsplit('/', 1)[0]}/derived/{name}"


def key_in_org(organisation: Organisation, key: str) -> bool:
    return bool(key) and key.startswith(org_prefix(organisation)) and ".." not in key


def check_key(organisation: Organisation, key: str) -> None:
    if not key_in_org(organisation, key):
        raise ForeignDocument(key)


# ---- objects ----------------------------------------------------------------------------------


def object_size(key: str, storage: S3Storage | None = None) -> int | None:
    """Size in bytes of an object, ``None`` when it doesn't exist."""
    try:
        head = client(storage).head_object(Bucket=(storage or files_storage()).bucket_name, Key=key)
    except Exception:  # botocore ClientError 404, or the bucket is unreachable
        return None
    return int(head["ContentLength"])


def open_object(key: str, storage: S3Storage | None = None) -> IO[bytes]:
    body: IO[bytes] = client(storage).get_object(
        Bucket=(storage or files_storage()).bucket_name, Key=key
    )["Body"]
    return body


def read_head(key: str, length: int = 8192) -> bytes:
    """The first bytes of an object (MIME detection)."""
    response = client().get_object(
        Bucket=files_storage().bucket_name, Key=key, Range=f"bytes=0-{length - 1}"
    )
    data: bytes = response["Body"].read()
    return data


def sha256_of(key: str) -> str:
    digest = hashlib.sha256()
    body = open_object(key)
    for chunk in iter(lambda: body.read(CHUNK), b""):
        digest.update(chunk)
    return digest.hexdigest()


def put_bytes(key: str, data: bytes, content_type: str, storage: S3Storage | None = None) -> None:
    client(storage).put_object(
        Bucket=(storage or files_storage()).bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
    )


def delete_object(key: str, storage: S3Storage | None = None) -> None:
    if key:
        client(storage).delete_object(Bucket=(storage or files_storage()).bucket_name, Key=key)


def move_to_quarantine(key: str) -> None:
    """Copy an object to the quarantine bucket (same key), then delete it from the files bucket."""
    client(quarantine_storage()).copy_object(
        Bucket=quarantine_storage().bucket_name,
        Key=key,
        CopySource={"Bucket": files_storage().bucket_name, "Key": key},
    )
    delete_object(key)


# ---- presigned upload and signed download -------------------------------------------------------


def presigned_post(key: str, max_size: int, content_type: str = "") -> dict[str, Any]:
    """A browser form that uploads one file straight to the bucket under ``key`` (5 minutes,
    1 byte … ``max_size``)."""
    conditions: list[Any] = [["content-length-range", 1, max_size]]
    fields: dict[str, str] = {}
    if content_type:
        fields["Content-Type"] = content_type
        conditions.append({"Content-Type": content_type})
    form: dict[str, Any] = client().generate_presigned_post(
        files_storage().bucket_name,
        key,
        Fields=fields or None,
        Conditions=conditions,
        ExpiresIn=settings.NUMO9_FILES_SIGNED_URL_SECONDS,
    )
    return form


@dataclass(frozen=True)
class SignedUrl:
    url: str
    expires_at: datetime


def content_disposition(name: str, *, download: bool) -> str:
    """RFC 6266 header with an ASCII fallback and the UTF-8 name (RFC 5987)."""
    kind = "attachment" if download else "inline"
    ascii_name = safe_filename(name).replace('"', "")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


def signed_key_url(key: str, *, name: str, mime: str, download: bool = False) -> SignedUrl:
    seconds = settings.NUMO9_FILES_SIGNED_URL_SECONDS
    url = files_storage().url(
        key,
        parameters={
            "ResponseContentDisposition": content_disposition(name, download=download),
            "ResponseContentType": mime or "application/octet-stream",
        },
        expire=seconds,
    )
    return SignedUrl(url=url, expires_at=timezone.now() + timedelta(seconds=seconds))


def signed_url(document: Any, *, download: bool = False, variant: str = "file") -> SignedUrl:
    """A 5-minute URL for a clean document of the active organisation.

    ``variant``: ``file`` (the document), ``preview`` or ``thumbnail`` (JPEG images, A-06-T05).
    Raises ``ForeignDocument`` for another organisation's document and ``DocumentNotReady`` while
    it is uploading, being scanned or quarantined (or has no such preview).
    """
    organisation = current_org()
    if organisation is None or document.organisation_id != organisation.pk:
        raise ForeignDocument(str(document.public_id))
    check_key(organisation, document.file_key)
    if not document.is_clean:
        raise DocumentNotReady(document.status)
    if variant == "file":
        return signed_key_url(
            document.file_key, name=document.name, mime=document.mime, download=download
        )
    key = document.preview_key if variant == "preview" else document.thumbnail_key
    if not key:
        raise DocumentNotReady(f"no {variant}")
    check_key(organisation, key)
    return signed_key_url(key, name=f"{variant}.jpg", mime="image/jpeg")
