"""D-02-T10 — quote PDF on the template baseline (gap-43): Letter pages, number, date and valid
until, the tax column and tax per component, optional lines and alternatives marked (the ones
not chosen greyed and out of the total), the deposit; the text matches the fixture snapshot."""

from __future__ import annotations

import io
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdf
import pytest

from numo9.documents.pdf import LETTER_POINTS
from numo9.sales.pdf import render_quote_pdf
from tests.quote_helpers import quote
from tests.test_invoice_pdf import books, normalised, squeezed, text_of  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db
SNAPSHOT = Path(__file__).parent / "snapshots" / "quote_pdf.txt"
HST = "sales.ON.standard"


@pytest.mark.gap("gap-43")
def test_quote_pdf_matches_the_snapshot(books: dict[str, Any]) -> None:  # noqa: F811
    item = quote(
        books,
        [
            {"description": "Kitchen cabinets", "quantity": "1", "price": "8000", "tax": HST},
            {
                "description": "Under-cabinet lighting",
                "price": "600",
                "tax": HST,
                "is_optional": True,
            },
            {
                "description": "Quartz counter",
                "price": "3000",
                "tax": HST,
                "alternative_group": "A",
            },
            {
                "description": "Granite counter",
                "price": "2500",
                "tax": HST,
                "alternative_group": "A",
                "selected": False,
            },
        ],
        title="Kitchen renovation",
        summary="Supply and install, 6 weeks.",
        deposit_type="percent",
        deposit_value=Decimal("25"),
    )
    pdf = render_quote_pdf(item)
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
    text = normalised(text_of(pdf))
    for expected in (
        "Quote number QU-0001",
        "Valid until",
        "Kitchen renovation",
        "Under-cabinet lighting\n(optional)",
        "Granite counter (option A)",
        "Total tax",
        "$11,000.00",  # subtotal of the counted lines
        "$12,430.00",  # total
        "$3,107.50",  # 25 % deposit
    ):
        assert expected in text, expected
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text + "\n", encoding="utf-8")
    assert squeezed(text) == squeezed(SNAPSHOT.read_text(encoding="utf-8"))
