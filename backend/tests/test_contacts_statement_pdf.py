"""B-02-T05 — Statement PDF template (WeasyPrint, Letter, inch margins, EN/FR keys).

Acceptance: the snapshot matches the fixture — the text of the rendered PDF (outstanding and
activity, English and French) equals its snapshot file (``tests/snapshots/statements/``;
``NUMO9_UPDATE_SNAPSHOTS=1`` rewrites them, a template change is reviewed as a snapshot diff).
Also: every page is Letter (8.5 × 11 in) with content inside the 1 in margins; the aging buckets
add up to the amount due; the activity statement starts from its opening balance.
"""

from __future__ import annotations

import io
import os
from decimal import Decimal
from pathlib import Path

import pypdf
import pytest

from numo9.contacts.statements import (
    StatementKind,
    render_statement_html,
    render_statement_pdf,
    sample_statement,
)
from numo9.documents.pdf import LETTER_POINTS, MARGIN_INCHES

SNAPSHOTS = Path(__file__).parent / "snapshots" / "statements"


def _text(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() for page in reader.pages)


def _assert_snapshot(name: str, content: str) -> None:
    path = SNAPSHOTS / name
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") == "1" or not path.exists():
        if os.environ.get("CI") and not path.exists():
            raise AssertionError(f"missing snapshot {path}: run with NUMO9_UPDATE_SNAPSHOTS=1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    assert content == path.read_text(encoding="utf-8"), f"{name} differs from its snapshot"


@pytest.mark.parametrize("kind", list(StatementKind))
@pytest.mark.parametrize("locale", ["en-ca", "fr-ca"])
def test_statement_text_matches_snapshot(kind: StatementKind, locale: str) -> None:
    text = _text(render_statement_pdf(sample_statement(kind), locale=locale))
    _assert_snapshot(f"{kind.value}.{locale}.txt", text)


def test_letter_page_and_one_inch_margins() -> None:
    reader = pypdf.PdfReader(io.BytesIO(render_statement_pdf(sample_statement())))
    margin = MARGIN_INCHES * 72
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
        origins: list[tuple[float, float, str]] = []

        def visit(
            text: str,
            cm: list[float],
            tm: list[float],
            *_: object,
            found: list[tuple[float, float, str]] = origins,
        ) -> None:
            if text.strip():
                found.append((tm[4] * cm[0] + cm[4], tm[5] * cm[3] + cm[5], text))

        page.extract_text(visitor_text=visit)
        body = [o for o in origins if "Prepared with Numo9" not in o[2] and "Page" not in o[2]]
        assert body
        for x, y, text in body:
            assert margin - 0.5 <= x <= LETTER_POINTS[0] - margin, text
            assert margin <= y <= LETTER_POINTS[1] - margin, text


def test_outstanding_content_and_aging() -> None:
    statement = sample_statement(StatementKind.OUTSTANDING)
    assert sum(statement.aging.values(), Decimal("0")) == statement.amount_due == Decimal("3729.00")
    assert statement.aging["days_61_90"] == Decimal("1130.00")  # due Sep 19: 72 days on Nov 30
    assert statement.aging["days_1_30"] == Decimal("2825.00")
    text = _text(render_statement_pdf(statement))
    for expected in (
        "Statement of outstanding items",
        "Cedar Roofing Co.",
        "As at",
        "30 Nov 2026",
        "OVER 90 DAYS",
        "Amount due (CAD)",
        "$3,729.00",
        "Page 1 of 1",
    ):
        assert expected in text, expected


def test_activity_starts_from_opening_balance() -> None:
    statement = sample_statement(StatementKind.ACTIVITY)
    assert statement.opening_balance + statement.total() == statement.amount_due
    html = render_statement_html(statement, locale="fr-ca")
    assert "Solde d’ouverture" in html or "Solde d'ouverture" in html
    assert "Relevé des opérations" in html
