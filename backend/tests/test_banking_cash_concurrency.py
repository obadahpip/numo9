"""F-07-T05 — concurrency safety: ``select_for_update`` on the bank account row during the
negative-balance check and the post.

Acceptance: two concurrent spends can't both pass a BLOCK — Petty Cash holds 100.00, two people
spend 80.00 from it at the same moment (threads, each in its own transaction, started together
and held inside the check so they overlap): exactly one posts, the other is blocked, and the
float ends at 20.00, never −60.00 — for spend money and for manual journals (where nothing else
serialises the two: without the lock both post, checked by removing it). The rows really are
locked: a second transaction can't take the lock while a posting holds it.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from decimal import Decimal
from typing import Any

import pytest
from django.db import OperationalError, connection, transaction

from numo9.banking import projector
from numo9.banking.balances import ledger_balance
from numo9.banking.models import BankAccount, BankTransaction, BankTransactionKind, TaxMode
from numo9.banking.services import create_bank_account
from numo9.banking.transactions import MoneyLine, MoneySpec, record_bank_transaction
from numo9.ledger.models import Account
from numo9.ledger.policy import NegativeBalanceBlocked
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

D = Decimal
DAY = dt.date(2026, 6, 15)


def _setup() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    who = people(org)
    petty = create_bank_account(org, type="cash", display_name="Petty Cash")
    with org_context(org):
        office = Account.objects.filter(subtype="operating_expense").order_by("code")[0]
        sales = Account.objects.filter(subtype="revenue").order_by("code")[0]
    record_bank_transaction(
        MoneySpec(
            BankTransactionKind.RECEIVE,
            petty,
            DAY,
            [MoneyLine(sales, D("100.00"))],
            tax_mode=TaxMode.NO_TAX,
        ),
        user=None,
    )
    return {"org": org, "petty": petty, "office": office, **who}


def _journal(books: dict[str, Any], amount: str) -> Any:
    """A manual journal crediting Petty Cash: nothing is written before the check (the spend's
    header is audited first, and the audit chain already queues two spends), so only the row
    lock keeps two of them apart."""
    from numo9.ledger.services import post_journal
    from numo9.ledger.validation import JournalSpec, LineSpec

    with org_context(books["org"]):
        return post_journal(
            JournalSpec(
                date=DAY,
                lines=(
                    LineSpec(books["office"], debit=D(amount)),
                    LineSpec(books["petty"].gl_account, credit=D(amount)),
                ),
            ),
            user=books["owner"],
        )


def _spend(books: dict[str, Any], amount: str) -> Any:
    return record_bank_transaction(
        MoneySpec(
            BankTransactionKind.SPEND,
            books["petty"],
            DAY,
            [MoneyLine(books["office"], D(amount))],
            tax_mode=TaxMode.NO_TAX,
        ),
        user=books["owner"],
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("post", [_spend, _journal], ids=["spend", "journal"])
def test_two_concurrent_spends_cannot_both_pass_a_block(
    monkeypatch: pytest.MonkeyPatch, post: Any
) -> None:
    books = _setup()
    real = projector.minimum_running_balance

    def slow(*args: Any, **kwargs: Any) -> Any:
        found = real(*args, **kwargs)
        time.sleep(0.5)  # hold the check open: without the row lock both would see 100.00
        return found

    monkeypatch.setattr(projector, "minimum_running_balance", slow)
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt() -> None:
        try:
            barrier.wait()
            post(books, "80.00")
            outcomes.append("posted")
        except NegativeBalanceBlocked:
            outcomes.append("blocked")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["blocked", "posted"]
    assert ledger_balance(books["petty"]) == D("20.00")
    with org_context(books["org"]):
        assert BankTransaction.objects.filter(kind="spend").count() == (post is _spend)


@pytest.mark.django_db(transaction=True)
def test_the_bank_account_row_is_locked_during_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    books = _setup()
    real = projector.minimum_running_balance
    inside = threading.Event()
    release = threading.Event()
    seen: list[str] = []

    def held(*args: Any, **kwargs: Any) -> Any:
        inside.set()
        release.wait(5)
        return real(*args, **kwargs)

    monkeypatch.setattr(projector, "minimum_running_balance", held)

    def posting() -> None:
        try:
            _spend(books, "10.00")
        finally:
            connection.close()

    def probe() -> None:
        inside.wait(5)
        try:
            with org_context(books["org"]), transaction.atomic():
                list(
                    BankAccount._base_manager.select_for_update(nowait=True).filter(
                        pk=books["petty"].pk
                    )
                )
            seen.append("free")
        except OperationalError:
            seen.append("locked")
        finally:
            release.set()
            connection.close()

    threads = [threading.Thread(target=posting), threading.Thread(target=probe)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen == ["locked"]
