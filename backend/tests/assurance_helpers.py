"""Exceptions engine (K-09) test helpers: ``refined()`` — a REFINED-like organisation as the Xero
teardown found it (docs/xero_teardown.md §5.4, §5.8, §6.11, §10.A):

- chart: 1000 Petty Cash (bank), 2900 Shareholder Loan, 3000 Share capital, 5515 Advertising &
  Promotions, 5590 Business Fees & Licenses, 5920 Travel — every account defaulting to the
  exempt purchase code, none mapped to GIFI;
- journal 1, dated 3 Jun 2026, **posted on 15 Jun 2026**: Dr 5590 300.00, Dr 5515 26.99 + 89.10 +
  1.13 / Cr 1000 417.22; journal 2, 15 Jun 2026: Dr 5920 576.95 / Cr 1000 576.95 — both manual,
  every line coded ``purchase.exempt``, no contact, no attachment (Petty Cash −994.17);
- a GST/HST (RT) registration without a Business Number registration, no lock date;
- a conversion at 1 Jan 2025 with no opening balances;
- the owner, Dana Lee, with user-management rights, last signed in on 26 Jul 2026 (four months
  before ``TODAY``).

The journals are posted as history (system postings, the way an import brings them in — the
cash guard stops people) with the clock set to their posting day.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any
from unittest import mock

from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

#: "Now" of the teardown: 26 Nov 2026, 10:00 in Toronto.
NOW = dt.datetime(2026, 11, 26, 15, 0, tzinfo=dt.UTC)
TODAY = dt.date(2026, 11, 26)
#: Both journals were posted on 15 Jun 2026 (a Monday), 10:00 in Toronto.
POSTED_AT = dt.datetime(2026, 6, 15, 14, 0, tzinfo=dt.UTC)
EXEMPT = "purchase.exempt"

ACCOUNTS = (
    ("1000", "Petty Cash", "bank"),
    ("2900", "Shareholder Loan", "non_current_liability"),
    ("3000", "Share capital", "share_capital"),
    ("4000", "Sales", "revenue"),
    ("5515", "Advertising & Promotions", "operating_expense"),
    ("5590", "Business Fees & Licenses", "operating_expense"),
    ("5920", "Travel", "operating_expense"),
)


def at(moment: dt.datetime) -> Any:
    """The clock (``timezone.now``) set to ``moment``."""
    return mock.patch("django.utils.timezone.now", return_value=moment)


def post(
    accounts: dict[str, Any],
    date: dt.date,
    narration: str,
    lines: tuple[tuple[str, str, str], ...],
    *,
    when: dt.datetime = POSTED_AT,
    tax_code: str = EXEMPT,
    user: Any = None,
    **fields: Any,
) -> Any:
    """Post a journal at ``when``; lines are ``(code, debit, credit)``."""
    spec = JournalSpec(
        date=date,
        narration=narration,
        lines=tuple(
            LineSpec(
                accounts[code],
                debit=Decimal(debit),
                credit=Decimal(credit),
                tax_code=tax_code if accounts[code].type == "expense" else "",
                contact=fields.get("contact") if accounts[code].type == "expense" else None,
            )
            for code, debit, credit in lines
        ),
        **{k: v for k, v in fields.items() if k != "contact"},
    )
    with at(when):
        return post_journal(spec, user=user)


def refined(
    *, registration: bool = True, conversion: bool = True, owner: bool = True
) -> dict[str, Any]:
    from numo9.tax.seed import ensure_tax_table

    org = Organisation.objects.create(name="REFINED Interiors Inc.", time_zone="America/Toronto")
    books: dict[str, Any] = {"org": org}
    with org_context(org):
        accounts = {
            code: account(org, code, name, subtype=subtype, default_tax_key=EXEMPT)
            if subtype == "operating_expense"
            else account(org, code, name, subtype=subtype)
            for code, name, subtype in ACCOUNTS
        }
        ensure_tax_table(org)
        books["accounts"] = accounts
        books["journal1"] = post(
            accounts,
            dt.date(2026, 6, 3),
            "Ontario Corporation",
            (
                ("5590", "300.00", "0"),
                ("5515", "26.99", "0"),
                ("5515", "89.10", "0"),
                ("5515", "1.13", "0"),
                ("1000", "0", "417.22"),
            ),
        )
        books["journal2"] = post(
            accounts,
            dt.date(2026, 6, 15),
            "Las Vegas Trade Show",
            (("5920", "576.95", "0"), ("1000", "0", "576.95")),
        )
        if registration:
            from numo9.orgsettings.models import TaxRegistration

            reg = TaxRegistration(
                organisation=org,
                type="rt",
                number="123456782RT0001",
                effective_from=dt.date(2025, 1, 1),
            )
            reg.full_clean()
            reg.save()
            books["registration"] = reg
        if conversion:
            from numo9.conversion.services import start_conversion

            books["conversion"] = start_conversion(org, dt.date(2025, 1, 1), user=None)
        if owner:
            from numo9.accounts.models import User
            from numo9.tenancy.models import OrganisationMember

            dana = User.objects.create_user(f"dana+{org.pk}@refined.ca", name="Dana Lee")
            User.objects.filter(pk=dana.pk).update(
                last_login=dt.datetime(2026, 7, 26, 14, tzinfo=dt.UTC)
            )
            dana.refresh_from_db()
            member = OrganisationMember.objects.create(organisation=org, user=dana, role="owner")
            OrganisationMember.objects.filter(pk=member.pk).update(
                created_at=dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
            )
            books["owner"] = dana
    return books
