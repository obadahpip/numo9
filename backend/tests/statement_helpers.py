"""Helpers for the statement import tests (F-02)."""

from __future__ import annotations

from pathlib import Path

from numo9.banking.models import BankAccount, StatementImport

FIXTURES = Path(__file__).parent / "fixtures" / "statements"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def batch(bank: BankAccount, name: str = "statement.csv", **fields: object) -> StatementImport:
    """A pending import of ``bank`` (no stored file: the tests hand the source in)."""
    created: StatementImport = StatementImport.objects.create(
        organisation_id=bank.organisation_id, bank_account=bank, file_name=name, **fields
    )
    return created


def big_csv(lines: int, *, start_day: int = 1) -> bytes:
    """A generic-layout CSV (Date, Description, Amount) with ``lines`` distinct lines."""
    rows = ["Date,Description,Amount"]
    for n in range(lines):
        day = start_day + (n % 28)
        rows.append(
            f"2026-06-{day:02d},PURCHASE {n:06d} STORE #{n % 97},-{1 + n % 500}.{n % 100:02d}"
        )
    return ("\n".join(rows) + "\n").encode("utf-8")
