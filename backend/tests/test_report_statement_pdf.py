"""K-02-T14 — statement PDF templates: Letter (8.5 × 11 in), 1 in margins, the display name and
the legal name over the statement's title, snapshot-tested.

Acceptance (snapshots approved): the profit and loss and the balance sheet print on the statement
template — "REFINED" (display name) and "Refined Interiors Inc." (legal name) centred over the
title and the date, every row and figure of the screen, the overdraft reclassification note
(K-02-T04) as a full-width line — and the extracted text equals the stored snapshot
(``NUMO9_UPDATE_SNAPSHOTS=1`` rewrites it after review). Every page is Letter and the text stays
inside the 1 in margins; other reports keep the generic report template.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import re
from pathlib import Path
from typing import Any

import pypdf
import pytest

from numo9.documents.pdf import LETTER_POINTS, MARGIN_INCHES, render_html
from numo9.ledger.services import post_journal
from numo9.orgsettings.service import get_settings
from numo9.reports.engine import registry
from numo9.reports.exports import render_pdf
from numo9.reports.header import header_for
from numo9.tenancy.context import org_context
from tests.journal_helpers import pay
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 8, 1)
SNAPSHOTS = Path(__file__).parent / "snapshots"
POINTS_PER_INCH = 72


@pytest.fixture
def books() -> dict[str, Any]:
    books = report_books()
    org = books["org"]
    with org_context(org):
        settings = get_settings(org)
        settings.display_name = "REFINED"
        settings.legal_name = "Refined Interiors Inc."
        settings.save()
        # Petty Cash overdrawn on the balance date: reclassified (K-02-T04).
        post_journal(
            pay(books["office"], books["petty"], "994.17", dt.date(2026, 6, 15)), user=None
        )
    return books


def body(org: Any, report_id: str, params: dict[str, Any]) -> dict[str, Any]:
    report = registry.get(report_id)
    result = report.run(org, params)
    data = result.as_dict()
    data["header"] = header_for(org, report, result.params, today=TODAY).as_dict()
    return data


def pdf_text(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
    raw = "\n".join(page.extract_text() for page in reader.pages)
    return "\n".join(
        line.rstrip() for line in re.sub(r"[ \t]+", " ", raw).splitlines() if line.strip()
    )


def heading(text: str) -> list[str]:
    """The statement heading: the four lines from the display name on (after the brand bar)."""
    lines = text.splitlines()
    start = lines.index("REFINED")
    return lines[start : start + 4]


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\xa0", " "))


def matches_snapshot(text: str, name: str) -> None:
    snapshot = SNAPSHOTS / name
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not snapshot.exists():
        snapshot.write_text(text + "\n", encoding="utf-8")
    assert squeezed(text) == squeezed(snapshot.read_text(encoding="utf-8"))


def _origins(page: Any) -> list[tuple[float, float, str]]:
    found: list[tuple[float, float, str]] = []

    def visit(text: str, cm: Any, tm: Any, *_: Any) -> None:
        if text.strip():
            found.append((tm[4] * cm[0] + cm[4], tm[5] * cm[3] + cm[5], text.strip()))

    page.extract_text(visitor_text=visit)
    return found


def inside_margins(pdf: bytes) -> None:
    width, height = LETTER_POINTS
    margin = MARGIN_INCHES * POINTS_PER_INCH
    for page in pypdf.PdfReader(io.BytesIO(pdf)).pages:
        origins = _origins(page)
        body_text = [o for o in origins if "Prepared with Numo9" not in o[2] and "Page" not in o[2]]
        assert body_text
        for x, y, text in body_text:
            assert margin - 0.5 <= x <= width - margin, text
            assert margin <= y <= height - margin, text


def test_balance_sheet_pdf(books: dict[str, Any]) -> None:
    data = body(books["org"], "balance_sheet", {"as_of": "2026-06-30"})
    html = render_html("reports/statement.html", {"header": data["header"]})
    assert "statement-head" in html
    pdf = render_pdf(data)
    text = pdf_text(pdf)
    assert heading(text) == [
        "REFINED",
        "Refined Interiors Inc.",
        "Balance sheet",
        "As at 30 Jun 2026",
    ]
    for expected in (
        "Bank overdraft — Petty Cash",
        "$994.17",
        "Overdrawn bank and cash accounts are presented as current liabilities (ASPE 1510).",
        "Total liabilities and equity",
    ):
        assert squeezed(expected) in squeezed(text), expected
    for row in data["rows"] + data["totals"]:
        assert squeezed(row["label"]) in squeezed(text), row["label"]
    inside_margins(pdf)
    matches_snapshot(text, "statement_balance_sheet_pdf.txt")


def test_profit_and_loss_pdf(books: dict[str, Any]) -> None:
    data = body(
        books["org"], "profit_and_loss", {"date_from": "2026-05-01", "date_to": "2026-07-31"}
    )
    pdf = render_pdf(data)
    text = pdf_text(pdf)
    assert heading(text) == [
        "REFINED",
        "Refined Interiors Inc.",
        "Profit and loss",
        "1 May 2026 to 31 Jul 2026",
    ]
    assert "Net income" in text
    inside_margins(pdf)
    matches_snapshot(text, "statement_profit_and_loss_pdf.txt")


def test_other_reports_keep_the_report_template(books: dict[str, Any]) -> None:
    data = body(books["org"], "trial_balance", {"as_of": "2026-06-30"})
    text = pdf_text(render_pdf(data))
    lines = text.splitlines()
    # the report template: the title, then the names (no centred statement heading)
    assert lines.index("Trial balance") < lines.index("REFINED")
