"""Demo seed for banking (F-01-T15, demo seed contract §1–§3).

The demo organisation gets a Chequing account (the template's 1010), Petty Cash (the template's
1000) and a Visa credit card (a new ledger account 21xx), with sample spend and receive money from
the seed document (``banking`` in ``demo_seed_v2.json``): a petty-cash float, a customer deposit,
warehouse rent, a software subscription, office supplies and a client lunch with a 50 % ITC —
all through the banking services, so the journals balance and the balances are the seed's
``expected_balances``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from numo9.demo.seeders import SeedContext, Seeder, register

from .services import attach_bank_account, create_bank_account
from .transactions import MoneyLine, MoneySpec, TaxPortion, record_bank_transaction


def seed_banking(ctx: SeedContext) -> None:
    section = ctx.seed.get("banking")
    if not section:
        return
    accounts = ctx.refs["accounts"]
    contacts = ctx.refs.get("contacts", {})
    made = {}
    for row in section["accounts"]:
        fields = {
            "type": row["type"],
            "display_name": row["name"],
            "institution": row.get("institution", ""),
            "account_last4": row.get("last4", ""),
            "user": None,
        }
        if row.get("ledger"):
            made[row["key"]] = attach_bank_account(accounts[row["ledger"]], **fields)
        else:
            made[row["key"]] = create_bank_account(ctx.organisation, **fields)
            accounts[made[row["key"]].gl_account.code] = made[row["key"]].gl_account
    for row in section["transactions"]:
        record_bank_transaction(
            MoneySpec(
                kind=row["kind"],
                bank_account=made[row["account"]],
                date=dt.date.fromisoformat(row["date"]),
                contact=contacts[row["contact"]] if row.get("contact") else None,
                reference=row.get("reference", ""),
                tax_mode=row.get("tax_mode", "exclusive"),
                lines=[
                    MoneyLine(
                        accounts[line["account"]],
                        Decimal(line["amount"]),
                        description=line.get("description", ""),
                        tax_code=line.get("tax_code", ""),
                        taxes=[
                            TaxPortion(
                                tax["role"], Decimal(tax["amount"]), tax.get("recoverable", True)
                            )
                            for tax in line.get("taxes", [])
                        ],
                    )
                    for line in row["lines"]
                ],
            ),
            user=None,
        )
    ctx.refs["bank_accounts"] = made


register(
    Seeder(
        "banking",
        seed_banking,
        after=("chart", "contacts", "opening_balances"),
        models=(
            "banking.BankAccount",
            "banking.BankTransaction",
            "banking.BankTransactionLine",
        ),
    )
)
