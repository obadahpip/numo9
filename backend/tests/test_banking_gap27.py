"""F-01-T16 — gap-27 functional test (backend half), through the real API and services: a new
organisation → add a chequing account → spend money with **no** import, feed, statement or
reconciliation → the Balance Sheet shows it.

Xero locks the bank module behind a plan and still let REFINED run with no bank at all
(docs/xero_teardown.md §5.1). Here, a trial organisation created by its owner (``POST
/api/v1/organisations``, the trial package — no plan upgrade) gets its chart from the Canadian
template (C-01; the set-up step has no API yet), then everything is the API the screens use:
``POST bank-accounts`` (Chequing, a current-asset bank account in the 10xx range, usable at once,
reconciliation tracking off), ``POST bank-transactions`` (the owner's opening deposit, then spend
money of 113.00 including HST on office supplies), and ``GET reports/balance-sheet/run``: the
chequing account at 4,887.00 among the current assets, the input tax credit 13.00, the sheet in
balance — while the organisation has no statement line, no import and no reconciliation.
The browser half is frontend/e2e/gap-27.spec.ts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.apps import apps
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
TODAY = "2026-06-15"


def _rows(sheet: dict[str, Any]) -> dict[str, str]:
    """Label → first value of every row and total of a report run."""
    return {
        row["label"]: (row["values"] or [""])[0]
        for row in [*sheet["rows"], *sheet.get("totals", [])]
    }


def _statement_or_reconciliation_rows(org: Organisation) -> int:
    """Rows of any statement-import or reconciliation model that exists (F-02/F-04 add them)."""
    total = 0
    with org_context(org):
        for model in apps.get_app_config("banking").get_models():
            name = model.__name__.lower()
            if any(word in name for word in ("statement", "import", "reconcil", "feed")):
                total += model._base_manager.filter(organisation=org).count()
    return total


@pytest.mark.gap("gap-27")
def test_new_org_spends_from_new_chequing_with_no_import_and_balance_sheet_shows_it() -> None:
    owner = User.objects.create_user("dana@refined.ca", name="Dana Lee")
    client = APIClient()
    client.force_authenticate(owner)

    created = client.post(
        "/api/v1/organisations", {"name": "Refined Interiors Inc."}, format="json"
    )
    assert created.status_code == 201, created.content
    org = Organisation.objects.get(public_id=created.json()["id"])
    assert org.status == "trial"  # no plan upgrade
    with org_context(org):
        settings = get_settings(org)
        settings.physical_province = "ON"
        settings.save()
    load_template(org, "ON", actor=owner)
    base = f"/api/v1/o/{org.public_id}/"

    # 1. Add a chequing account: four fields, usable at once.
    assert client.get(f"{base}bank-accounts?status=active").json()["results"] == []
    made = client.post(
        f"{base}bank-accounts",
        {"type": "chequing", "display_name": "TD Business Chequing", "institution": "TD"},
        format="json",
    )
    assert made.status_code == 201, made.content
    bank = made.json()
    assert bank["ledger_balance"] == "0.00" and bank["is_reconciled_tracking"] is False
    assert bank["ledger_account"]["code"].startswith("10")
    with org_context(org):
        equity = Account.objects.filter(subtype="share_capital").order_by("code").first()
        office = (
            Account.objects.filter(type="expense", default_tax_key="purchase.ON.standard")
            .order_by("code")
            .first()
        )
    assert equity is not None and office is not None

    # 2. The owner's deposit, then spend money 113.00 including HST — no feed, no import.
    deposit = client.post(
        f"{base}bank-transactions",
        {
            "kind": "receive",
            "bank_account": bank["id"],
            "date": "2026-06-01",
            "tax_mode": "no_tax",
            "reference": "Owner's deposit",
            "lines": [{"account": str(equity.public_id), "amount": "5000.00"}],
        },
        format="json",
    )
    assert deposit.status_code == 201, deposit.content
    spend = client.post(
        f"{base}bank-transactions",
        {
            "kind": "spend",
            "bank_account": bank["id"],
            "date": TODAY,
            "tax_mode": "inclusive",
            "reference": "Staples",
            "lines": [
                {
                    "account": str(office.public_id),
                    "amount": "113.00",
                    "tax_code": "purchase.ON.standard",
                    "description": "Printer paper",
                }
            ],
        },
        format="json",
    )
    assert spend.status_code == 201, spend.content
    listed = client.get(f"{base}bank-accounts?status=active").json()["results"]
    assert [(a["display_name"], a["ledger_balance"]) for a in listed] == [
        ("TD Business Chequing", "4887.00")
    ]
    assert _statement_or_reconciliation_rows(org) == 0

    # 3. The Balance Sheet shows it.
    run = client.get(f"{base}reports/balance-sheet/run", {"as_of": TODAY})
    assert run.status_code == 200, run.content
    rows = _rows(run.json())
    chequing = f"{bank['ledger_account']['code']} · TD Business Chequing"
    assert Decimal(rows[chequing]) == Decimal("4887.00"), rows
    itc = [label for label, value in rows.items() if value and Decimal(value) == Decimal("13.00")]
    assert itc, rows  # the recoverable HST is an asset (input tax credit)
    assert Decimal(rows["Total assets"]) == Decimal("4900.00"), rows
