"""Cheque printing (E-06-T07): one Letter page per cheque on **cheque-on-top laser stock** — the
cheque in the top third, then **two vouchers** (the payee's and the file copy) listing the bills
it pays. Sizes are in inches: 8.5 × 11 in, three panels of 3⅔ in.

This template doesn't extend ``documents/base.html``: pre-printed cheque stock has no margins
for a brand header and the MICR line must sit in the cheque's clear band, so the page has its
own geometry (Letter, no margin) — still rendered by ``numo9.documents.pdf.render_pdf`` (inline
CSS only, no network).

**The cheque** — the organisation's legal name and address; the cheque number; the date in the
Payments Canada format ``YYYY-MM-DD`` with its ``Y Y Y Y M M D D`` indicator (Standard 006);
*Pay to the order of* the payee's legal name and address; the amount in figures, padded with
asterisks (``**1,234.56``), and in words in the payee's language (``cheque_words``); the memo;
the signature line.

**The MICR line** (``micr_line``) — E-13B characters, in the order Canadian cheques use:
``⑈<serial>⑈ ⑆<transit>⑉<institution>⑆ <account>⑈`` — the cheque number (6 digits) between
on-us symbols, the 5-digit transit (branch) number and the 3-digit institution number between
transit symbols with the dash symbol between them, then the account number and an on-us
symbol. The symbols are Unicode's OCR characters (U+2446 transit, U+2448 on-us, U+2449 dash).
The line sits 3/16 in above the cheque's bottom edge, 5/16 in from its right edge, in a 5/8 in
clear band. It is printed with an E-13B font (``"MICR E-13B"``, ``"GnuMICR"``…, falling back to
a monospace font so a preview still shows it): **bank-readable MICR needs a licensed E-13B
font installed on the print host and magnetic toner** — Numo9 ships none (licence).

``print_cheques(cheques, user)`` renders the run and marks issued cheques **Printed**
(``cheques.change_status``). A cheque without the bank account's transit, institution and MICR
account numbers is refused (``purchases.cheque.micr_missing``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from numo9.documents.formatting import format_money
from numo9.documents.pdf import inline_only_fetcher, render_html, render_pdf
from numo9.sales.pdf import _issuer
from numo9.tenancy.context import org_context

from .cheque_words import amount_in_words
from .cheques import ChequeRefused, change_status
from .models import Cheque, ChequeSequence, ChequeStatus

TEMPLATE = "purchases/cheque.html"
TRANSIT = "⑆"  # ⑆ transit (routing) symbol
AMOUNT = "⑇"  # ⑇ amount symbol (encoded by the bank of first deposit, not printed by us)
ON_US = "⑈"  # ⑈ on-us symbol
DASH = "⑉"  # ⑉ dash symbol
#: Inches — the page and its three panels; the MICR line's place on the cheque.
PAGE = (8.5, 11.0)
PANEL_HEIGHT = 11.0 / 3
MICR_BOTTOM = 0.1875
MICR_RIGHT = 0.3125
CLEAR_BAND = 0.625


@dataclass(frozen=True)
class MicrLine:
    serial: str
    transit: str
    institution: str
    account: str

    @property
    def text(self) -> str:
        return (
            f"{ON_US}{self.serial}{ON_US} "
            f"{TRANSIT}{self.transit}{DASH}{self.institution}{TRANSIT} "
            f"{self.account}{ON_US}"
        )


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def micr_line(cheque: Cheque) -> MicrLine:
    """The cheque's MICR line (module docstring); refused when a number is missing."""
    bank = cheque.bank_account
    settings = ChequeSequence._base_manager.filter(bank_account=bank).first()
    transit = _digits(bank.transit_number)
    institution = _digits(bank.institution_number)
    account = _digits(settings.account_number if settings else "")
    if len(transit) != 5 or len(institution) != 3 or not 1 <= len(account) <= 12:
        raise ChequeRefused(
            _(
                "Enter the transit (5 digits), institution (3 digits) and account numbers of "
                "%(account)s to print its cheques."
            ),
            code="purchases.cheque.micr_missing",
            params={"account": str(bank)},
        )
    return MicrLine(f"{cheque.number:06d}", transit, institution, account)


def _payee(cheque: Cheque) -> dict[str, Any]:
    from numo9.contacts.models import AddressKind

    address = cheque.payee.addresses.filter(
        kind=AddressKind.BILLING, deleted_at__isnull=True
    ).first()
    return {
        "name": cheque.payee_name,
        "address_line": " ".join(x for x in (address.line1, address.line2) if x) if address else "",
        "city": address.city if address else "",
        "province": address.province if address else "",
        "postal_code": address.postal_code if address else "",
    }


def padded_amount(amount: Decimal, locale: str) -> str:
    """``**1,234.56`` — the figures padded with asterisks to 12 characters (no room to add a
    digit), without the currency sign (printed beside the box)."""
    figures = format_money(amount, locale).replace("$", "").replace("\xa0", " ").strip()
    return figures.rjust(12, "*")


def cheque_context(cheque: Cheque) -> dict[str, Any]:
    locale = cheque.payee.language or "en-ca"
    payments = list(
        cheque.payments.select_related("bill").order_by("bill__date", "bill__number", "pk")
    )
    lines = [
        {
            "bill": payment.bill.number,
            "supplier_invoice_no": payment.bill.supplier_invoice_no,
            "date": payment.bill.date,
            "amount": payment.settled,
            "discount": payment.discount,
            "paid": payment.amount,
        }
        for payment in payments
    ]
    micr = micr_line(cheque)
    return {
        "cheque": cheque,
        "number": str(cheque),
        "issuer": _issuer(cheque.organisation, cheque.date),
        "bank_name": cheque.bank_account.institution or cheque.bank_account.display_name,
        "payee": _payee(cheque),
        "date_text": cheque.date.isoformat(),
        "amount": cheque.amount,
        "amount_padded": padded_amount(cheque.amount, locale),
        "amount_words": amount_in_words(cheque.amount, locale),
        "currency": cheque.currency,
        "memo": cheque.memo,
        "micr": micr.text,
        "lines": lines,
        "discount_total": sum((Decimal(p.discount) for p in payments), Decimal("0")),
        "locale": locale,
        "panel_height": f"{PANEL_HEIGHT:.4f}in",
        "micr_bottom": f"{MICR_BOTTOM}in",
        "micr_right": f"{MICR_RIGHT}in",
        "clear_band": f"{CLEAR_BAND}in",
    }


def render_cheques_pdf(cheques: Iterable[Cheque]) -> bytes:
    """One page per cheque, in the order given, each in its payee's language (the pages are
    rendered one by one and joined into one PDF)."""
    rows = list(cheques)
    if not rows:
        raise ChequeRefused(_("Choose the cheques to print."), code="purchases.cheque.none")
    with org_context(rows[0].organisation):
        pages = [cheque_context(cheque) for cheque in rows]
    if len(pages) == 1:
        return render_pdf(TEMPLATE, {"pages": pages}, locale=pages[0]["locale"])
    from weasyprint import HTML

    documents = [
        HTML(
            string=render_html(TEMPLATE, {"pages": [page]}, locale=page["locale"]),
            url_fetcher=inline_only_fetcher(),
        ).render()
        for page in pages
    ]
    every = [p for document in documents for p in document.pages]
    pdf: bytes = documents[0].copy(every).write_pdf()
    return pdf


def render_cheque_pdf(cheque: Cheque) -> bytes:
    return render_cheques_pdf([cheque])


def print_cheques(cheques: Iterable[Cheque], user: Any = None) -> bytes:
    """Render the run, then mark the issued cheques Printed (a reprint of a printed cheque is
    allowed and changes nothing; void and cleared cheques are refused)."""
    rows = list(cheques)
    for cheque in rows:
        if cheque.status not in (ChequeStatus.ISSUED, ChequeStatus.PRINTED):
            raise ChequeRefused(
                _("Cheque %(number)s is %(status)s: it can't be printed."),
                code="purchases.cheque.not_printable",
                params={
                    "number": str(cheque),
                    "status": str(ChequeStatus(cheque.status).label).lower(),
                },
            )
    pdf = render_cheques_pdf(rows)
    for cheque in rows:
        if cheque.status == ChequeStatus.ISSUED:
            change_status(cheque, ChequeStatus.PRINTED, user)
    return pdf
