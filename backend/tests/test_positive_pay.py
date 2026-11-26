"""E-06-T10 — positive-pay export: the register's cheques of a bank account dated in the range,
issues and voids, in number order; the generic CSV (headers) and the bank presets (no header,
date formats, amounts in cents, codes, padded numbers, payee length); the export matches the
register; refused without the MICR account number, for an unknown preset or reversed dates;
audited."""

from __future__ import annotations

import csv
import datetime as dt
import io
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.purchases import cheques, positive_pay
from numo9.purchases.models import ChequeSequence, ChequeStatus
from numo9.tenancy.context import org_context
from tests.payment_helpers import payment_books

pytestmark = pytest.mark.django_db
D = Decimal
JUNE = (dt.date(2026, 6, 1), dt.date(2026, 6, 30))


@pytest.fixture
def books() -> dict[str, Any]:
    books = payment_books()
    bank = books["bank"]
    with org_context(books["org"]):
        bank.transit_number, bank.institution_number = "12345", "003"
        bank.save()
        cheques.set_next_number(bank, 501)
        row = ChequeSequence.objects.get(bank_account=bank)
        row.account_number = "1234567"
        row.save()
    supplier, other = books["supplier"], books["other"]
    books["c1"] = cheques.issue(bank, supplier, D("1234.56"), dt.date(2026, 6, 5))
    books["c2"] = cheques.issue(bank, other, D("80.00"), dt.date(2026, 6, 12))
    books["c3"] = cheques.issue(bank, supplier, D("15.10"), dt.date(2026, 6, 20))
    cheques.change_status(books["c2"], ChequeStatus.VOID, reason="Wrong amount")
    cheques.change_status(books["c3"], ChequeStatus.PRINTED)
    cheques.issue(bank, supplier, D("9.99"), dt.date(2026, 7, 2))  # outside the range
    return books


def parsed(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("utf-8"))))


def test_generic_csv_matches_the_register(books: dict[str, Any]) -> None:
    made = positive_pay.export(books["bank"], "generic", *JUNE, user=books["owner"])
    assert made.name == "positive-pay-generic-4567-20260601-20260630.csv"
    assert parsed(made.content) == [
        ["account", "number", "date", "amount", "payee", "status"],
        ["1234567", "501", "2026-06-05", "1234.56", "Cedar Supply Co.", "Issued"],
        ["1234567", "502", "2026-06-12", "80.00", "Maple Hardware Ltd", "Void"],
        ["1234567", "503", "2026-06-20", "15.10", "Cedar Supply Co.", "Issued"],
    ]
    with org_context(books["org"]):
        register = list(
            books["bank"]
            .cheques.filter(date__range=JUNE)
            .order_by("number")
            .values_list("number", "amount", "status")
        )
        event = AuditEvent.objects.get(action="purchases.cheque.positive_pay_exported")
    assert [(r.number, r.amount, r.kind) for r in made.rows] == [
        (n, a, "void" if s == ChequeStatus.VOID else "issue") for n, a, s in register
    ]
    assert event.meta == {
        "preset": "generic",
        "from": "2026-06-01",
        "to": "2026-06-30",
        "cheques": 3,
        "issued": 2,
        "voided": 1,
    }


@pytest.mark.parametrize(
    ("preset", "first"),
    [
        ("rbc", ["1234567", "0000000501", "1234.56", "20260605", "Cedar Supply Co.", "I"]),
        ("td", ["12345", "1234567", "501", "06/05/2026", "1234.56", "I", "Cedar Supply Co."]),
        ("bmo", ["1234567", "00000501", "20260605", "123456", "I", "Cedar Supply Co."]),
        ("scotiabank", ["12345", "1234567", "501", "1234.56", "2026-06-05", "O"]),
        (
            "desjardins",
            ["003", "12345", "1234567", "501", "20260605", "1234.56", "E", "Cedar Supply Co."],
        ),
    ],
)
def test_bank_presets(books: dict[str, Any], preset: str, first: list[str]) -> None:
    rows = parsed(positive_pay.export(books["bank"], preset, *JUNE).content)
    assert rows[0] == first and len(rows) == 3
    chosen = positive_pay.PRESETS[preset]
    assert rows[1][chosen.columns.index("status")] == chosen.void_code


def test_cibc_has_a_header_and_cents(books: dict[str, Any]) -> None:
    rows = parsed(positive_pay.export(books["bank"], "cibc", *JUNE).content)
    assert rows[0] == ["account", "number", "amount", "date", "status", "payee"]
    assert rows[1][2] == "123456" and rows[3][2] == "1510"


def test_refusals(books: dict[str, Any]) -> None:
    with pytest.raises(cheques.ChequeRefused) as unknown:
        positive_pay.export(books["bank"], "nope", *JUNE)
    assert unknown.value.code == "purchases.positive_pay.preset"
    with pytest.raises(cheques.ChequeRefused) as backwards:
        positive_pay.export(books["bank"], "generic", JUNE[1], JUNE[0])
    assert backwards.value.code == "purchases.positive_pay.dates"
    with org_context(books["org"]):
        ChequeSequence.objects.filter(bank_account=books["bank"]).update(account_number="")
    with pytest.raises(cheques.ChequeRefused) as missing:
        positive_pay.export(books["bank"], "generic", *JUNE)
    assert missing.value.code == "purchases.positive_pay.account_missing"


def test_empty_range_has_only_the_header(books: dict[str, Any]) -> None:
    made = positive_pay.export(books["bank"], "generic", dt.date(2025, 1, 1), dt.date(2025, 1, 31))
    assert parsed(made.content) == [["account", "number", "date", "amount", "payee", "status"]]
