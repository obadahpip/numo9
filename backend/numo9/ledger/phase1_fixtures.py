"""Phase 1 fixtures (C-03-T16): the REFINED teardown journals and negative-cash scenarios.

``load()`` (``manage.py load_phase1_fixtures``, ``make fixtures-phase1``) — idempotent:

1. **REFINED Interiors Inc.** — the Xero teardown organisation (docs/xero_teardown.md §5.8): Petty
   Cash 1000 and the three expense accounts its journals use, and the two posted manual journals
   that drove Petty Cash to −994.17:

   - Journal 1, 3 Jun 2026, "Ontario Corporation": Dr 5590 Business Fees & Licenses 300.00,
     Dr 5515 Advertising & Promotions 26.99 + 89.10 + 1.13 / Cr 1000 Petty Cash 417.22;
   - Journal 2, 15 Jun 2026, "Las Vegas Trade Show": Dr 5920 Travel 576.95 / Cr 1000 576.95.

   They are loaded as history (system postings, the way an import brings them in — the cash guard
   stops people, C-03-T08), so the organisation starts exactly where the teardown found it.

2. **Negative cash scenarios** (``SCENARIOS``): journals to try in REFINED and the outcome the
   cash guard must give — each one names the account, the projected balance and its day.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import SUBTYPE_TYPE, Account, AccountSubtype, JournalEntry
from .services import post_journal
from .validation import JournalSpec, LineSpec

ORG_NAME = "REFINED Interiors Inc."

ACCOUNTS = (
    ("1000", "Petty Cash", AccountSubtype.BANK),
    ("1010", "Chequing", AccountSubtype.BANK),
    ("4000", "Sales", AccountSubtype.REVENUE),
    ("5515", "Advertising & Promotions", AccountSubtype.OPERATING_EXPENSE),
    ("5590", "Business Fees & Licenses", AccountSubtype.OPERATING_EXPENSE),
    ("5920", "Travel", AccountSubtype.OPERATING_EXPENSE),
)

#: (date, narration, [(code, debit, credit)]) — the teardown's two journals.
TEARDOWN_JOURNALS = (
    (
        dt.date(2026, 6, 3),
        "Ontario Corporation",
        (
            ("5590", "300.00", "0"),
            ("5515", "26.99", "0"),
            ("5515", "89.10", "0"),
            ("5515", "1.13", "0"),
            ("1000", "0", "417.22"),
        ),
    ),
    (
        dt.date(2026, 6, 15),
        "Las Vegas Trade Show",
        (("5920", "576.95", "0"), ("1000", "0", "576.95")),
    ),
)


@dataclass(frozen=True)
class Scenario:
    key: str
    description: str
    date: dt.date
    lines: tuple[tuple[str, str, str], ...]
    #: The guard's answer: (account code, lowest balance, its day) per account going below zero.
    expect: tuple[tuple[str, str, dt.date], ...]


SCENARIOS = (
    Scenario(
        "teardown_journal_1",
        "Journal 1 entered a second time (a duplicate): Petty Cash lowest after journal 2",
        dt.date(2026, 6, 3),
        TEARDOWN_JOURNALS[0][2],
        (("1000", "-1411.39", dt.date(2026, 6, 15)),),
    ),
    Scenario(
        "another_spend",
        "A 50.00 office expense today from Petty Cash already at −994.17",
        dt.date(2026, 10, 26),
        (("5515", "50.00", "0"), ("1000", "0", "50.00")),
        (("1000", "-1044.17", dt.date(2026, 10, 26)),),
    ),
    Scenario(
        "top_up",
        "Money in: 1,000.00 into Petty Cash — never a shortfall",
        dt.date(2026, 10, 26),
        (("1000", "1000.00", "0"), ("4000", "0", "1000.00")),
        (),
    ),
    Scenario(
        "two_banks",
        "Rent of 1,500.00 paid 1,000.00 from Chequing (funded) and 500.00 from Petty Cash",
        dt.date(2026, 10, 26),
        (("5590", "1500.00", "0"), ("1010", "0", "1000.00"), ("1000", "0", "500.00")),
        (("1000", "-1494.17", dt.date(2026, 10, 26)),),
    ),
)

#: Chequing is funded so the two-banks scenario has one account going negative only.
CHEQUING_FUNDING = (dt.date(2026, 6, 1), Decimal("5000.00"))


def _accounts(organisation: Organisation) -> dict[str, Account]:
    found = {a.code: a for a in Account.objects.filter(code__in=[c for c, _, _ in ACCOUNTS])}
    for code, name, subtype in ACCOUNTS:
        if code not in found:
            account = Account(
                organisation=organisation,
                code=code,
                name_i18n={"en-ca": name},
                type=SUBTYPE_TYPE[subtype],
                subtype=subtype,
            )
            account.save()
            found[code] = account
    return found


def spec_of(
    accounts: dict[str, Account],
    date: dt.date,
    narration: str,
    lines: tuple[tuple[str, str, str], ...],
) -> JournalSpec:
    return JournalSpec(
        date=date,
        narration=narration,
        lines=tuple(
            LineSpec(accounts[code], debit=Decimal(debit), credit=Decimal(credit))
            for code, debit, credit in lines
        ),
    )


def load() -> Organisation:
    """REFINED with its chart and teardown journals (once), funded Chequing; the organisation."""
    organisation = Organisation.objects.filter(name=ORG_NAME).order_by("pk").first()
    if organisation is None:
        organisation = Organisation.objects.create(name=ORG_NAME, time_zone="America/Toronto")
    with org_context(organisation), transaction.atomic():
        accounts = _accounts(organisation)
        if not JournalEntry.objects.filter(
            narration__in=[j[1] for j in TEARDOWN_JOURNALS]
        ).exists():
            day, amount = CHEQUING_FUNDING
            post_journal(
                spec_of(
                    accounts,
                    day,
                    "Opening deposit",
                    (("1010", str(amount), "0"), ("4000", "0", str(amount))),
                ),
                user=None,
            )
            for date, narration, lines in TEARDOWN_JOURNALS:
                post_journal(spec_of(accounts, date, narration, lines), user=None)
    return organisation
