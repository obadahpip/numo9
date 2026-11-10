"""A-10-T16 — document template baseline (WeasyPrint): Letter 8.5 × 11 in, 1 in margins,
Canadian sample data, brand header (gap-43)."""

from __future__ import annotations

import datetime as dt
import io
import json
from decimal import Decimal
from pathlib import Path

import pypdf
import pytest
from django.core.management import call_command

from numo9.documents.formatting import format_date, format_money
from numo9.documents.pdf import LETTER_POINTS, MARGIN_INCHES, render_html, render_pdf
from numo9.documents.sample_data import sample_context

TOKENS = Path(__file__).resolve().parents[2] / "packages" / "ui" / "tokens" / "tokens.json"
POINTS_PER_INCH = 72.0


def _reader(pdf: bytes) -> pypdf.PdfReader:
    return pypdf.PdfReader(io.BytesIO(pdf))


@pytest.fixture(scope="module")
def sample_pdf() -> bytes:
    return render_pdf("documents/sample.html", sample_context())


def _text_origins(page: pypdf.PageObject) -> list[tuple[float, float, str]]:
    origins: list[tuple[float, float, str]] = []

    def visit(text: str, cm: list[float], tm: list[float], *_: object) -> None:
        if text.strip():
            # Text space → user space: x = tm.x * cm.a + cm.e (no rotation/skew in our PDFs).
            x = tm[4] * cm[0] + cm[4]
            y = tm[5] * cm[3] + cm[5]
            origins.append((x, y, text.strip()))

    page.extract_text(visitor_text=visit)
    return origins


@pytest.mark.gap("gap-43")
def test_rendered_pdf_is_letter_size(sample_pdf: bytes) -> None:
    reader = _reader(sample_pdf)
    assert len(reader.pages) >= 1
    for page in reader.pages:
        box = page.mediabox
        assert (float(box.width), float(box.height)) == LETTER_POINTS  # 8.5 × 11 in


@pytest.mark.gap("gap-43")
def test_content_stays_inside_one_inch_margins(sample_pdf: bytes) -> None:
    page = _reader(sample_pdf).pages[0]
    width, height = LETTER_POINTS
    margin = MARGIN_INCHES * POINTS_PER_INCH
    origins = _text_origins(page)
    assert origins
    body = [o for o in origins if "Prepared with Numo9" not in o[2] and "Page" not in o[2]]
    for x, y, text in body:
        assert margin - 0.5 <= x <= width - margin, text
        assert margin <= y <= height - margin, text
    # Content starts at the 1 in margin (left edge of the brand mark, top of the header).
    assert min(x for x, _, _ in body) == pytest.approx(margin, abs=12)
    assert max(y for _, y, _ in body) == pytest.approx(height - margin, abs=24)


@pytest.mark.gap("gap-43")
def test_sample_data_is_canadian(sample_pdf: bytes) -> None:
    text = _reader(sample_pdf).pages[0].extract_text()
    for expected in (
        "NUMO9",
        "Numbers build a brighter tomorrow",
        "Toronto ON",
        "M5V 2T6",
        "GST/HST registration: 123456789RT0001",
        "HST 13 % (ON)",
        "26 Oct 2026",
        "$1,412.50",
        "Page 1 of 1",
    ):
        assert expected in text
    for banned in ("VAT", "ZIP", "Auckland", "NZ$", "Wellington"):
        assert banned not in text


def test_french_document() -> None:
    text = _reader(render_pdf("documents/sample.html", sample_context(), locale="fr-ca"))
    content = text.pages[0].extract_text()
    assert "26 oct. 2026" in content
    assert "1 412,50 $" in content or "1 412,50 $" in content
    assert "Page 1 de 1" in content


def test_page_geometry_is_fixed_in_the_base_template() -> None:
    html = render_html("documents/sample.html", sample_context())
    assert "size: letter;" in html
    assert "margin: 1in;" in html
    assert "cm" not in html.split("<style>")[1].split("</style>")[0].replace("cmyk", "")


def test_brand_header_uses_the_design_tokens() -> None:
    tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    yellow = tokens["color"]["brand"]["yellow"]["$value"].upper()
    black = tokens["color"]["brand"]["black"]["$value"].upper()
    html = render_html("documents/sample.html", sample_context()).upper()
    assert f"BACKGROUND: {yellow}" in html
    assert f"COLOR: {black}" in html


def test_external_resources_are_refused() -> None:
    from weasyprint import HTML

    from numo9.documents.pdf import inline_only_fetcher

    fetcher = inline_only_fetcher()
    for url in ("file:///etc/passwd", "https://example.com/logo.png", "ftp://example.com/x"):
        with pytest.raises(ValueError, match="disallowed protocol"):
            fetcher.fetch(url)
    assert fetcher.fetch("data:text/plain,ok").read() == b"ok"
    # An <img> pointing outside is skipped; the document still renders.
    pdf = HTML(string='<p>x</p><img src="file:///etc/passwd">', url_fetcher=fetcher).write_pdf()
    assert pdf is not None and pdf.startswith(b"%PDF")


@pytest.mark.parametrize(
    ("amount", "locale", "expected"),
    [
        (Decimal("1234.56"), "en-ca", "$1,234.56"),
        (Decimal("1234.56"), "fr-ca", "1 234,56 $"),
        (Decimal("-0.004"), "en-ca", "$0.00"),
        (Decimal("-1250"), "en-ca", "-$1,250.00"),
        ("0.005", "en-ca", "$0.01"),
        (0, "fr-ca", "0,00 $"),
    ],
)
def test_format_money(amount: Decimal | str | int, locale: str, expected: str) -> None:
    assert format_money(amount, locale) == expected


def test_format_date() -> None:
    assert format_date(dt.date(2026, 10, 26), "en-ca") == "26 Oct 2026"
    assert format_date(dt.date(2026, 10, 26), "fr-ca") == "26 oct. 2026"
    assert format_date(dt.date(2026, 2, 1), "fr_CA") == "1 févr. 2026"
    assert format_date(dt.date(2026, 2, 1), None) == "1 Feb 2026"


def test_render_sample_document_command(tmp_path: Path) -> None:
    out = tmp_path / "sample.pdf"
    call_command("render_sample_document", "--out", str(out), stdout=io.StringIO())
    reader = pypdf.PdfReader(str(out))
    assert (float(reader.pages[0].mediabox.width), float(reader.pages[0].mediabox.height)) == (
        LETTER_POINTS
    )
