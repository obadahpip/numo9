"""Accepted file types and content-based detection (A-06-T03).

The browser's claim and the file name are never trusted: the type is detected from the content
with libmagic (``python-magic``) and must fit the file's extension.

| Extension | Stored as | Content must be |
|---|---|---|
| pdf | application/pdf | a PDF |
| png, jpg/jpeg, tif/tiff, heic/heif | the image type | that image (HEIC: image/heic, heif) |
| xlsx, docx | the Office Open XML type | a ZIP package with the matching Office parts |
| csv, ofx, qfx, qbo | text/csv, application/x-ofx… | text, no NUL bytes (OFX is SGML/XML) |

Anything else — an executable renamed ``invoice.pdf``, a ZIP renamed ``.xlsx``, a ``.exe`` — is
refused.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

import magic

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

#: extension → the MIME type the document is stored and served with.
STORED_TYPE: dict[str, str] = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "heic": "image/heic",
    "heif": "image/heif",
    "xlsx": XLSX,
    "docx": DOCX,
    "csv": "text/csv",
    "ofx": "application/x-ofx",
    "qfx": "application/vnd.intu.qfx",
    "qbo": "application/vnd.intu.qbo",
}

#: extension → libmagic results accepted for it (binary formats).
DETECTED: dict[str, frozenset[str]] = {
    "pdf": frozenset({"application/pdf"}),
    "png": frozenset({"image/png"}),
    "jpg": frozenset({"image/jpeg"}),
    "jpeg": frozenset({"image/jpeg"}),
    "tif": frozenset({"image/tiff"}),
    "tiff": frozenset({"image/tiff"}),
    "heic": frozenset({"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}),
    "heif": frozenset({"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}),
}

#: Office Open XML: what libmagic may say for the package, and the part that must be inside.
OFFICE: dict[str, tuple[frozenset[str], str]] = {
    "xlsx": (frozenset({XLSX, "application/zip", "application/octet-stream"}), "xl/"),
    "docx": (frozenset({DOCX, "application/zip", "application/octet-stream"}), "word/"),
}

TEXT_TYPES = frozenset({"csv", "ofx", "qfx", "qbo"})
TEXT_DETECTED = ("text/", "application/xml", "application/json", "application/csv")

ACCEPTED_EXTENSIONS: frozenset[str] = frozenset(STORED_TYPE)


def extension_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in (name or "") else ""


def is_accepted_name(name: str) -> bool:
    return extension_of(name) in ACCEPTED_EXTENSIONS


@dataclass(frozen=True)
class Detection:
    ok: bool
    stored_type: str  # MIME type the document keeps when ok
    detected: str  # what libmagic found


def detect(name: str, data: bytes) -> Detection:
    """Check ``data`` (the whole file, ≤ 25 MB) against the extension of ``name``."""
    extension = extension_of(name)
    detected = magic.from_buffer(data[:65536], mime=True) if data else "application/x-empty"
    stored = STORED_TYPE.get(extension, "")
    if not stored:
        return Detection(False, "", detected)
    if extension in DETECTED:
        return Detection(detected in DETECTED[extension], stored, detected)
    if extension in OFFICE:
        allowed, part = OFFICE[extension]
        return Detection(detected in allowed and _has_part(data, part), stored, detected)
    if extension in TEXT_TYPES:
        is_text = detected.startswith(TEXT_DETECTED) and b"\x00" not in data[:65536]
        return Detection(is_text, stored, detected)
    return Detection(False, stored, detected)  # pragma: no cover - every extension is mapped


def _has_part(data: bytes, prefix: str) -> bool:
    """An Office Open XML package: a ZIP with ``[Content_Types].xml`` and its main part folder."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            names = package.namelist()
    except (zipfile.BadZipFile, ValueError):
        return False
    return "[Content_Types].xml" in names and any(n.startswith(prefix) for n in names)
