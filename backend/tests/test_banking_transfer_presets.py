"""F-06-T05 — transfer presets pre-fill the accounts by bank-account type.

Acceptance: "Fund petty cash" gives chequing → cash and "Pay credit card" chequing → credit
card; savings stands in when there is no chequing; archived accounts are skipped; a missing type
leaves that side empty; the preset's pair posts as a transfer.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.banking.lifecycle import archive_bank_account
from numo9.banking.services import create_bank_account
from numo9.banking.transfer_presets import PRESETS, resolve_preset
from numo9.banking.transfers import record_transfer
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def _names(org: Organisation, key: str) -> tuple[str | None, str | None]:
    with org_context(org):
        found = resolve_preset(key)
    return (
        found.from_account.display_name if found.from_account else None,
        found.to_account.display_name if found.to_account else None,
    )


def test_presets_prefill_by_type(org: Organisation) -> None:
    create_bank_account(org, type="savings", display_name="A Savings")
    create_bank_account(org, type="chequing", display_name="TD Chequing")
    create_bank_account(org, type="cash", display_name="Petty Cash")
    create_bank_account(org, type="credit_card", display_name="TD Visa")
    assert _names(org, "fund_petty_cash") == ("TD Chequing", "Petty Cash")
    assert _names(org, "pay_credit_card") == ("TD Chequing", "TD Visa")
    assert [str(p.label) for p in PRESETS.values()] == ["Fund petty cash", "Pay credit card"]


def test_savings_stands_in_archived_skipped_missing_left_empty(org: Organisation) -> None:
    old = create_bank_account(org, type="chequing", display_name="Old Chequing")
    archive_bank_account(old)
    create_bank_account(org, type="savings", display_name="RBC Savings")
    create_bank_account(org, type="cash", display_name="Petty Cash")
    assert _names(org, "fund_petty_cash") == ("RBC Savings", "Petty Cash")
    assert _names(org, "pay_credit_card") == ("RBC Savings", None)


def test_preset_pair_posts(org: Organisation) -> None:
    create_bank_account(org, type="chequing", display_name="TD Chequing")
    create_bank_account(org, type="cash", display_name="Petty Cash")
    with org_context(org):
        found = resolve_preset("fund_petty_cash")
    assert found.from_account is not None and found.to_account is not None
    transfer = record_transfer(
        found.from_account, found.to_account, date=dt.date(2026, 6, 1), amount="1000.00"
    )
    assert transfer.journal_entry is not None
