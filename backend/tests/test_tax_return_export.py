"""G-03-T13 — the return's PDF (WeasyPrint, Letter, 1-inch margins) and CSV: the same lines,
labels and amounts as the worksheet screen (the API's ``lines``); the PDF matches its stored
snapshot."""

from __future__ import annotations

import csv
import io
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.test import Client

from numo9.tax import returns
from numo9.tax.return_export import render_pdf
from numo9.tenancy.context import org_context
from tests.tax_report_helpers import june_books
from tests.test_report_exports import pdf_text, squeezed

pytestmark = pytest.mark.django_db
SNAPSHOT = Path(__file__).parent / "snapshots" / "gst_hst_return_pdf.txt"


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = june_books()
    with org_context(books["org"]):
        tax_return = returns.prepare(books["period"], books["owner"])
    client = Client()
    client.force_login(books["owner"])
    url = f"/api/v1/o/{books['org'].public_id}/tax/returns/{tax_return.public_id}"
    return {**books, "return": tax_return, "client": client, "url": url}


def _screen(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    answer = ctx["client"].get(ctx["url"])
    assert answer.status_code == 200
    lines: list[dict[str, Any]] = answer.json()["lines"]
    return lines


def test_csv_lines_equal_the_screen(ctx: dict[str, Any]) -> None:
    body = ctx["client"].get(f"{ctx['url']}/csv").content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(body)))
    assert rows[0] == ["Line", "Description", "Amount"]
    assert rows[1:] == [[r["line"], r["label"], r["amount"]] for r in _screen(ctx)]
    assert {r[0]: r[2] for r in rows[1:]}["109"] == "66.50"


def test_pdf_lines_equal_the_screen_and_the_snapshot(ctx: dict[str, Any]) -> None:
    with org_context(ctx["org"]):
        text = pdf_text(render_pdf(ctx["return"]))  # pdf_text checks every page is Letter
    flat = squeezed(text)
    for row in _screen(ctx):
        amount = f"${Decimal(row['amount']):,.2f}"
        assert squeezed(f"{row['line']}{row['label']}{amount}") in flat, row
    assert "123456782RT0001" in flat
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text + "\n", encoding="utf-8")
    assert flat == squeezed(SNAPSHOT.read_text(encoding="utf-8"))


def test_the_french_export_uses_the_cra_labels(ctx: dict[str, Any]) -> None:
    """G-03-T16 — the CRA's French line labels in the French CSV and PDF."""
    import csv as csvlib

    from numo9.tax.return_export import render_csv

    with org_context(ctx["org"]):
        body = render_csv(ctx["return"], "fr-ca").decode("utf-8-sig")
        text = squeezed(pdf_text(render_pdf(ctx["return"], "fr-ca")))
    rows = list(csvlib.reader(io.StringIO(body)))
    assert rows[0] == ["Ligne", "Description", "Montant"]
    labels = {r[0]: r[1] for r in rows[1:]}
    assert labels["103"] == "TPS/TVH perçue ou à percevoir"
    assert labels["109"] == "Taxe nette" and labels["115"] == "Paiement joint"
    for expected in ("Déclarationde TPS/TVH", "Méthodenormale", "Brouillon", "Taxenette"):
        assert squeezed(expected) in text, expected
