"""Previews and thumbnails (A-06-T05).

After a document is scanned clean, a job draws two JPEG images next to it in the bucket
(``…/derived/preview.jpg`` up to 1600 px, ``…/derived/thumbnail.jpg`` up to 256 px):

- **PDF** — the first page, rendered with PDFium (``pypdfium2``); a password-protected PDF gets
  no preview (``preview_status = password``, ``password_protected``) and stays downloadable;
- **images** — PNG, JPEG, TIFF (first frame) and HEIC/HEIF (iPhone photos, via ``pillow-heif``),
  turned upright from their EXIF orientation;
- other types (CSV, XLSX, DOCX, bank files) — ``unsupported``: the inbox shows a file icon;
- a file that can't be read — ``failed`` (the document stays downloadable).

Served by the signed-URL service as ``variant=preview`` / ``thumbnail`` (5 minutes).
"""

from __future__ import annotations

import io
from typing import Any

import pillow_heif
import pypdfium2 as pdfium
from PIL import Image, ImageOps

from . import storage
from .models import Document, DocumentStatus, PreviewStatus

PREVIEW_SIZE = (1600, 1600)
THUMBNAIL_SIZE = (256, 256)
IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/tiff", "image/heic", "image/heif"})

pillow_heif.register_heif_opener()


class PasswordProtected(Exception):
    pass


def queue_preview(document: Document) -> None:
    from numo9.jobs.runtime import start_job

    from .tasks import make_preview

    start_job(
        make_preview,
        organisation=document.organisation,
        key=f"preview:{document.public_id}",
        document_id=str(document.public_id),
    )


def first_page(data: bytes) -> Image.Image:
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise PasswordProtected from exc
        raise
    try:
        page = pdf[0]
        width = page.get_width() or 1
        image: Image.Image = page.render(scale=min(4.0, PREVIEW_SIZE[0] / width)).to_pil()
        return image
    finally:
        pdf.close()


def picture(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.seek(0)
    upright = ImageOps.exif_transpose(image)
    return upright if upright is not None else image


def jpeg(image: Image.Image, size: tuple[int, int]) -> bytes:
    copy = image.convert("RGB")
    copy.thumbnail(size)
    out = io.BytesIO()
    copy.save(out, "JPEG", quality=82, optimize=True)
    return out.getvalue()


def render(document: Document, data: bytes) -> Image.Image | None:
    """The image to preview, ``None`` when the type has no preview."""
    if document.mime == "application/pdf":
        return first_page(data)
    if document.mime in IMAGE_TYPES:
        return picture(data)
    return None


def make_preview(document_id: str) -> dict[str, Any]:
    document = Document.objects.filter(public_id=document_id, deleted_at__isnull=True).first()
    if document is None or document.status != DocumentStatus.CLEAN:
        return {"skipped": True}
    data = storage.open_object(document.file_key).read()
    fields = ["preview_status", "updated_at"]
    try:
        image = render(document, data)
    except PasswordProtected:
        document.preview_status = PreviewStatus.PASSWORD
        document.password_protected = True
        document.save(update_fields=[*fields, "password_protected"])
        return {"preview": PreviewStatus.PASSWORD}
    except Exception:  # a damaged file: no preview, still downloadable
        document.preview_status = PreviewStatus.FAILED
        document.save(update_fields=fields)
        return {"preview": PreviewStatus.FAILED}
    if image is None:
        document.preview_status = PreviewStatus.UNSUPPORTED
        document.save(update_fields=fields)
        return {"preview": PreviewStatus.UNSUPPORTED}
    preview_key = storage.derived_key(document.file_key, "preview.jpg")
    thumbnail_key = storage.derived_key(document.file_key, "thumbnail.jpg")
    storage.put_bytes(preview_key, jpeg(image, PREVIEW_SIZE), "image/jpeg")
    storage.put_bytes(thumbnail_key, jpeg(image, THUMBNAIL_SIZE), "image/jpeg")
    document.preview_key, document.thumbnail_key = preview_key, thumbnail_key
    document.preview_status = PreviewStatus.READY
    document.save(update_fields=[*fields, "preview_key", "thumbnail_key"])
    return {"preview": PreviewStatus.READY}
