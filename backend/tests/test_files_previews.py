"""A-06-T05 — thumbnail/preview generation (PDF first page, images incl. HEIC).

Acceptance: preview available < 5 s. Each case runs the preview job body and measures it, then
fetches the preview through a signed URL. Also: PDF first page; PNG, JPEG (EXIF orientation),
TIFF and HEIC; sizes (1600 px preview, 256 px thumbnail); password-protected PDF → no preview,
still downloadable; CSV → unsupported; damaged PDF → failed; only clean documents.
"""

from __future__ import annotations

import io
import time
from collections.abc import Callable, Iterator

import pillow_heif
import pytest
import requests
from PIL import Image
from pypdf import PdfWriter

from numo9.files import previews, storage
from numo9.files.models import Document, DocumentStatus, PreviewStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.files_helpers import CSV, PDF, png

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("s3")]

PREVIEW_BUDGET_SECONDS = 5.0


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


def clean(org: Organisation, name: str, mime: str, data: bytes) -> Document:
    key = storage.new_key(org, name)
    storage.put_bytes(key, data, mime)
    item = Document(
        organisation=org,
        name=name,
        file_key=key,
        mime=mime,
        size=len(data),
        status=DocumentStatus.CLEAN,
    )
    item.save()
    return item


def image_bytes(fmt: str, size: tuple[int, int], **save: object) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (255, 209, 0)).save(out, fmt, **save)
    return out.getvalue()


def heic(size: tuple[int, int]) -> bytes:
    out = io.BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", size, (17, 120, 200))).save(out, quality=60)
    return out.getvalue()


def a4_pdf(pages: int = 3) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)  # US Letter, 8.5 × 11 in
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def timed_preview(item: Document) -> float:
    started = time.perf_counter()
    previews.make_preview(str(item.public_id))
    elapsed = time.perf_counter() - started
    item.refresh_from_db()
    return elapsed


def fetched(item: Document, variant: str) -> Image.Image:
    response = requests.get(storage.signed_url(item, variant=variant).url, timeout=10)
    assert response.status_code == 200
    return Image.open(io.BytesIO(response.content))


# ---- acceptance: < 5 s, for every previewable type -----------------------------------------


@pytest.mark.parametrize(
    ("name", "mime", "make"),
    [
        ("statement.pdf", "application/pdf", lambda: a4_pdf()),
        ("tiny.pdf", "application/pdf", lambda: PDF),
        ("receipt.png", "image/png", lambda: png((1200, 900))),
        ("photo.jpg", "image/jpeg", lambda: image_bytes("JPEG", (4032, 3024))),
        ("scan.tiff", "image/tiff", lambda: image_bytes("TIFF", (2480, 3508))),
        ("iphone.heic", "image/heic", lambda: heic((2016, 1512))),
    ],
)
def test_preview_is_ready_within_five_seconds(
    org: Organisation, name: str, mime: str, make: Callable[[], bytes]
) -> None:
    item = clean(org, name, mime, make())
    elapsed = timed_preview(item)
    assert item.preview_status == PreviewStatus.READY
    assert elapsed < PREVIEW_BUDGET_SECONDS, f"{name}: {elapsed:.2f} s"
    preview, thumbnail = fetched(item, "preview"), fetched(item, "thumbnail")
    assert preview.format == thumbnail.format == "JPEG"
    assert max(preview.size) <= 1600 and max(thumbnail.size) <= 256


def test_pdf_preview_is_the_first_page_at_full_width(org: Organisation) -> None:
    item = clean(org, "statement.pdf", "application/pdf", a4_pdf())
    timed_preview(item)
    preview = fetched(item, "preview")
    assert preview.size[0] == 1600 or preview.size[1] == 1600
    assert preview.size[1] > preview.size[0]  # portrait page


def test_jpeg_is_turned_upright(org: Organisation) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise to display
    item = clean(org, "photo.jpg", "image/jpeg", image_bytes("JPEG", (400, 200), exif=exif))
    timed_preview(item)
    assert fetched(item, "preview").size == (200, 400)


# ---- no preview ----------------------------------------------------------------------------


def test_a_password_protected_pdf_has_no_preview(org: Organisation) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("s3cret")
    out = io.BytesIO()
    writer.write(out)
    item = clean(org, "locked.pdf", "application/pdf", out.getvalue())
    timed_preview(item)
    assert item.preview_status == PreviewStatus.PASSWORD and item.password_protected
    assert "X-Amz-Expires" in storage.signed_url(item).url  # still downloadable


def test_other_types_are_unsupported_and_damaged_files_failed(org: Organisation) -> None:
    sheet = clean(org, "bank.csv", "text/csv", CSV)
    timed_preview(sheet)
    assert sheet.preview_status == PreviewStatus.UNSUPPORTED
    damaged = clean(org, "broken.pdf", "application/pdf", b"%PDF-1.4 not really")
    timed_preview(damaged)
    assert damaged.preview_status == PreviewStatus.FAILED
    with pytest.raises(storage.DocumentNotReady):
        storage.signed_url(damaged, variant="preview")


def test_only_clean_documents_get_a_preview(org: Organisation) -> None:
    item = clean(org, "receipt.png", "image/png", png())
    item.status = DocumentStatus.SCANNING
    item.save(update_fields=["status"])
    assert previews.make_preview(str(item.public_id)) == {"skipped": True}
