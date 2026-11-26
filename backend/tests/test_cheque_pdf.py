"""E-06-T07 — cheque print PDF: Letter (8.5 × 11 in) pages, the cheque on top and two vouchers
listing the bills paid; the amount in figures (asterisk-padded) and in words (English, Canadian
French); the MICR line in E-13B order (on-us serial, transit-dash-institution, account); the
text matches the snapshot; one page per cheque in its payee's language; printing marks the
cheques Printed; missing bank numbers refused."""

from __future__ import annotations

import io
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdf
import pytest

from numo9.contacts.models import Address, AddressKind
from numo9.documents.pdf import LETTER_POINTS, render_html
from numo9.purchases import cheque_pdf, cheques
from numo9.purchases.cheque_words import amount_in_words
from numo9.purchases.models import ChequeSequence, ChequeStatus
from numo9.tenancy.context import org_context
from tests.payment_helpers import add_payment, batch, payment_books, posted_bill

pytestmark = pytest.mark.django_db
D = Decimal
SNAPSHOT = Path(__file__).parent / "snapshots" / "cheque_pdf.txt"


@pytest.fixture
def books() -> dict[str, Any]:
    books = payment_books()
    org = books["org"]
    with org_context(org):
        bank = books["bank"]
        bank.transit_number, bank.institution_number = "12345", "003"
        bank.save()
        cheques.set_next_number(bank, 1001)
        ChequeSequence.objects.filter(bank_account=bank).update()
        row = ChequeSequence.objects.get(bank_account=bank)
        row.account_number = "1234567"
        row.save()
        from numo9.orgsettings.service import get_settings

        settings = get_settings(org)
        settings.legal_name = "Refined Interiors Inc."
        settings.physical_line1 = "200 King Street West, Suite 1200"
        settings.physical_city, settings.physical_province = "Toronto", "ON"
        settings.physical_postal_code = "M5V 2T6"
        settings.save()
    made = batch(books)
    one = add_payment(made, posted_bill(books, "1000.00", "CS-1001"), "980.00", discount="20.00")
    two = add_payment(made, posted_bill(books, "254.56", "CS-1002"), "254.56")
    books["cheque"] = cheques.issue(
        books["bank"],
        books["supplier"],
        D("1234.56"),
        made.payment_date,
        payments=[one, two],
        batch=made,
        memo="June invoices",
    )
    return books


def text_of(pdf: bytes, pages: int = 1) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == pages
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
    raw = "\n".join(page.extract_text() for page in reader.pages)
    return "\n".join(
        line.rstrip() for line in re.sub(r"[ \t]+", " ", raw).splitlines() if line.strip()
    )


def without_micr(text: str) -> str:
    """The text without the MICR line (its glyphs depend on the E-13B font installed)."""
    return "\n".join(line for line in text.splitlines() if "1234567" not in line)


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\xa0", " "))


def test_micr_line_in_canadian_order(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        line = cheque_pdf.micr_line(books["cheque"])
    assert line.text == "⑈001001⑈ ⑆12345⑉003⑆ 1234567⑈"
    html = render_html(cheque_pdf.TEMPLATE, {"pages": [cheque_context(books)]})
    assert line.text in html
    assert "size: 8.5in 11in; margin: 0;" in html
    assert "bottom: 0.1875in; right: 0.3125in;" in html  # 3/16 in up, 5/16 in from the right
    assert '"MICR E-13B"' in html


def cheque_context(books: dict[str, Any]) -> dict[str, Any]:
    with org_context(books["org"]):
        return cheque_pdf.cheque_context(books["cheque"])


def test_cheque_pdf_matches_the_snapshot(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        text = text_of(cheque_pdf.render_cheque_pdf(books["cheque"]))
    for expected in (
        "Refined Interiors Inc.",
        "001001",
        "Pay to the order of",
        "Cedar Supply Co.",
        "One thousand two hundred thirty-four and 56/100 dollars",
        "$ ****1,234.56",
        "Memo: June invoices",
        "Authorized signature",
        "Remittance — keep for your records",
        "File copy",
        "BILL-0001",
        "CS-1001",
        "$20.00",
        "$980.00",
    ):
        assert expected in text, expected
    assert text.count("Cheque 001001") == 2  # both vouchers
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(without_micr(text) + "\n", encoding="utf-8")
    assert squeezed(without_micr(text)) == squeezed(SNAPSHOT.read_text(encoding="utf-8"))


def test_print_run_one_page_per_cheque_in_the_payees_language(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        books["other"].language = "fr-ca"
        books["other"].save()
        Address(
            organisation=books["org"],
            contact=books["other"],
            kind=AddressKind.BILLING,
            country="CA",
            province="QC",
            city="Montréal",
        ).save()
    made = batch(books)
    pay = add_payment(made, posted_bill(books, "80.00", "M-1", supplier="other"), "80.00")
    french = cheques.issue(
        books["bank"], books["other"], D("80.00"), made.payment_date, payments=[pay]
    )
    with org_context(books["org"]):
        pdf = cheque_pdf.print_cheques([books["cheque"], french], books["owner"])
        text = text_of(pdf, pages=2)
        assert "Quatre-vingts et 00/100 dollars" in text
        assert "Payez à l’ordre de" in text or "Payez à l'ordre de" in text
        statuses = set(
            type(french)
            .objects.filter(pk__in=[french.pk, books["cheque"].pk])
            .values_list("status", flat=True)
        )
    assert statuses == {ChequeStatus.PRINTED}


def test_void_cheques_are_not_printed_and_missing_numbers_refused(books: dict[str, Any]) -> None:
    void = cheques.change_status(books["cheque"], ChequeStatus.VOID, reason="Misfeed")
    with pytest.raises(cheques.ChequeRefused) as refused, org_context(books["org"]):
        cheque_pdf.print_cheques([void])
    assert refused.value.code == "purchases.cheque.not_printable"
    with org_context(books["org"]):
        ChequeSequence.objects.filter(bank_account=books["bank"]).update(account_number="")
        again = cheques.issue(books["bank"], books["supplier"], D("5"), void.date)
        with pytest.raises(cheques.ChequeRefused) as missing:
            cheque_pdf.render_cheque_pdf(again)
    assert missing.value.code == "purchases.cheque.micr_missing"


@pytest.mark.parametrize(
    ("amount", "locale", "words"),
    [
        ("0.05", "en-ca", "Zero and 05/100 dollars"),
        ("21", "en-ca", "Twenty-one and 00/100 dollars"),
        ("100", "en-ca", "One hundred and 00/100 dollars"),
        ("1000000.01", "en-ca", "One million and 01/100 dollars"),
        (
            "987654321.99",
            "en-ca",
            "Nine hundred eighty-seven million six hundred fifty-four "
            "thousand three hundred twenty-one and 99/100 dollars",
        ),
        ("21", "fr-ca", "Vingt et un et 00/100 dollars"),
        ("71", "fr-ca", "Soixante et onze et 00/100 dollars"),
        ("80", "fr-ca", "Quatre-vingts et 00/100 dollars"),
        ("81", "fr-ca", "Quatre-vingt-un et 00/100 dollars"),
        ("91", "fr-ca", "Quatre-vingt-onze et 00/100 dollars"),
        ("200", "fr-ca", "Deux cents et 00/100 dollars"),
        ("201", "fr-ca", "Deux cent un et 00/100 dollars"),
        ("1000", "fr-ca", "Mille et 00/100 dollars"),
        ("80000", "fr-ca", "Quatre-vingt mille et 00/100 dollars"),
        ("200000", "fr-ca", "Deux cent mille et 00/100 dollars"),
        ("1234.56", "fr-ca", "Mille deux cent trente-quatre et 56/100 dollars"),
        ("2000000", "fr-ca", "Deux millions et 00/100 dollars"),
    ],
)
def test_amount_in_words(amount: str, locale: str, words: str) -> None:
    assert amount_in_words(D(amount), locale) == words


def test_amount_in_words_range() -> None:
    with pytest.raises(ValueError):
        amount_in_words(D("1000000000"))
    assert cheque_pdf.padded_amount(D("1234.56"), "en-ca") == "****1,234.56"
