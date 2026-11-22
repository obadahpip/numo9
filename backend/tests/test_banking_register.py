"""F-01-T11 — account register: running balance per line, filters, CSV / XLSX export.

Acceptance: the running balance of the last row equals the ledger balance; a journal posted
straight to the account shows too; filters (date, contact, amount, status) keep true balances; a
voided spend shows its reversal; CSV and XLSX download the same rows.
"""

from __future__ import annotations

import datetime as dt
import io
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.banking.balances import ledger_balance
from numo9.banking.models import BankTransactionKind
from numo9.banking.register import RegisterFilters, register
from numo9.banking.services import create_bank_account
from numo9.banking.transactions import (
    MoneyLine,
    MoneySpec,
    record_bank_transaction,
    void_bank_transaction,
)
from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.journal_helpers import pay, people

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    with org_context(org):
        found = {
            "org": org,
            "bank": bank,
            "office": Account.objects.filter(subtype="operating_expense").order_by("code").first(),
            "sales": Account.objects.filter(subtype="revenue").order_by("code").first(),
            "staples": contact(org, "Staples"),
        }
    return found


def _money(b: dict[str, Any], kind: str, amount: str, day: int, **extra: Any) -> Any:
    account = b["office"] if kind == BankTransactionKind.SPEND else b["sales"]
    return record_bank_transaction(
        MoneySpec(kind, b["bank"], dt.date(2026, 6, day), [MoneyLine(account, D(amount))], **extra),
        user=None,
    )


def _history(b: dict[str, Any]) -> Any:
    _money(b, BankTransactionKind.RECEIVE, "1000.00", 1)
    spent = _money(
        b, BankTransactionKind.SPEND, "200.00", 5, contact=b["staples"], reference="INV-77"
    )
    with org_context(b["org"]):
        post_journal(
            pay(b["office"], b["bank"].gl_account, "50.00", dt.date(2026, 6, 7)), user=None
        )
    _money(b, BankTransactionKind.SPEND, "30.00", 9)
    return spent


def test_last_running_balance_equals_ledger_balance(books: dict[str, Any]) -> None:
    _history(books)
    rows = register(books["bank"])
    assert [(r["received"], r["spent"], r["balance"]) for r in rows] == [
        (D("1000.00"), D("0.00"), D("1000.00")),
        (D("0.00"), D("200.00"), D("800.00")),
        (D("0.00"), D("50.00"), D("750.00")),
        (D("0.00"), D("30.00"), D("720.00")),
    ]
    assert rows[-1]["balance"] == ledger_balance(books["bank"])
    assert rows[1]["reference"] == "INV-77" and rows[1]["contact"]["name"] == "Staples"
    assert rows[2]["transaction"] is None and rows[2]["journal"]["number"]


def test_filters_keep_true_balances(books: dict[str, Any]) -> None:
    _history(books)
    bank = books["bank"]
    by_date = register(bank, RegisterFilters(date_from=dt.date(2026, 6, 6)))
    assert [r["balance"] for r in by_date] == [D("750.00"), D("720.00")]
    by_contact = register(bank, RegisterFilters(contact=str(books["staples"].public_id)))
    assert [r["balance"] for r in by_contact] == [D("800.00")]
    by_amount = register(bank, RegisterFilters(amount_min=D("40"), amount_max=D("500")))
    assert [r["spent"] for r in by_amount] == [D("200.00"), D("50.00")]


def test_voided_spend_shows_with_its_reversal(books: dict[str, Any]) -> None:
    spent = _history(books)
    void_bank_transaction(spent, user=None)
    rows = register(books["bank"])
    assert rows[-1]["balance"] == ledger_balance(books["bank"]) == D("920.00")
    assert [r["status"] for r in register(books["bank"], RegisterFilters(status="reversed"))] == [
        "reversed"
    ]
    assert sum(1 for r in rows if r["voided"]) == 2  # the spend and its reversal


def test_api_json_csv_and_xlsx(books: dict[str, Any]) -> None:
    _history(books)
    org, bank = books["org"], books["bank"]
    client = Client()
    client.force_login(people(org)["owner"])
    base = f"/api/v1/o/{org.public_id}/bank-accounts/{bank.public_id}/register"
    body = client.get(base).json()
    assert body["results"][-1]["balance"] == body["account"]["ledger_balance"] == "720.00"
    assert client.get(f"{base}?amount_min=abc").status_code == 400
    filtered = client.get(f"{base}?date_from=2026-06-06&status=posted").json()["results"]
    assert [r["balance"] for r in filtered] == ["750.00", "720.00"]
    csv_file = client.get(f"{base}?export=csv")
    assert csv_file["Content-Type"].startswith("text/csv")
    text = csv_file.content.decode("utf-8-sig").splitlines()
    assert text[0].startswith("Date,Journal,Contact") and text[-1].endswith("720.00,posted")
    xlsx = client.get(f"{base}?export=xlsx")
    from openpyxl import load_workbook

    sheet = load_workbook(io.BytesIO(xlsx.content)).active
    assert sheet.max_row == 5 and sheet.cell(5, 8).value == 720.0
