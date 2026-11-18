"""Practice fixture generator (S-06-T08): one practice, N client organisations, M lines each.

``make_practice_fixture(orgs=2000, lines=500)`` builds what V-01's directory and the S-06 k6
baselines run against: a practice with an admin, ``orgs`` client organisations assigned to it
(full service), each with a small chart, a few contacts and ``lines`` posted journal lines (pairs
of balanced lines, dated over the last year, numbers 1..n gap-free, in both books).

Organisations are created through the ORM so the seeding signals run (contact terms, entitlement
caches, the workspace directory rows); the journal lines are inserted with ``generate_series`` the
way the engine writes them (entries as drafts, their lines, then Posted with consecutive numbers —
the append-only trigger allows exactly that), so 2,000 organisations x 500 lines take minutes, not
hours. Deterministic: the same ``seed`` gives the same names and amounts.

For a scratch or staging database only: ``assert_scratch()`` refuses unless DEBUG is on or
``NUMO9_ALLOW_FIXTURES=1`` is set, and the command asks for ``--scratch`` too.
"""

from __future__ import annotations

import datetime as dt
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone

from numo9.contacts.models import Contact
from numo9.ledger.models import SUBTYPE_TYPE, Account, JournalSequence
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    AssignmentRole,
    Organisation,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)

PREFIX = "Fixture"
LINES_PER_ENTRY = 2

CHART: tuple[tuple[str, str, str], ...] = (
    ("1000", "Cash on hand", "current_asset"),
    ("1200", "Accounts receivable", "current_asset"),
    ("2000", "Accounts payable", "current_liability"),
    ("2100", "Accrued liabilities", "current_liability"),
    ("4000", "Sales", "revenue"),
    ("5000", "Cost of goods sold", "cost_of_sales"),
    ("6000", "Rent", "operating_expense"),
    ("6100", "Office supplies", "operating_expense"),
)

TRADES = ("Bakery", "Plumbing", "Dental", "Landscaping", "Consulting", "Café", "Auto", "Studio")
PLACES = ("Maple", "Birch", "Cedar", "Spruce", "Willow", "Aspen", "Pine", "Oak", "Elm", "Alder")
FORMS = ("Ltd.", "Inc.", "Co.", "Corp.")

INSERT_ENTRIES = """
INSERT INTO ledger_journalentry (public_id, organisation_id, created_at, updated_at, date, type,
    status, source_type, source_id, narration, book_scope)
SELECT md5(%(seed)s || n)::uuid, %(org)s, now(), now(), %(start)s::date + (n %% 365),
       'manual', 'draft', '', '', 'Fixture entry ' || n, 'both'
FROM generate_series(1, %(entries)s) AS n
"""

INSERT_LINES = """
INSERT INTO ledger_journalline (organisation_id, entry_id, line_no, account_id, debit, credit,
    book, tracking, description, tax_code, created_at, updated_at)
SELECT e.organisation_id, e.id, l.line_no,
       (%(accounts)s::bigint[])[1 + ((e.id * 7 + l.line_no * 13) %% %(account_count)s)],
       CASE WHEN l.line_no = 1 THEN a.amount ELSE 0 END,
       CASE WHEN l.line_no = 2 THEN a.amount ELSE 0 END,
       'both', '{}'::jsonb, '', '', now(), now()
FROM ledger_journalentry e
CROSS JOIN generate_series(1, 2) AS l(line_no)
CROSS JOIN LATERAL (SELECT ((e.id * 31 + %(salt)s) %% 500000 + 1) / 100.0 AS amount) a
WHERE e.organisation_id = %(org)s
"""

POST_ENTRIES = """
UPDATE ledger_journalentry e
   SET status = 'posted', number = n.number, posted_at = now()
  FROM (SELECT id, row_number() OVER (ORDER BY id) AS number
          FROM ledger_journalentry WHERE organisation_id = %(org)s) n
 WHERE e.id = n.id
"""


class FixtureRefused(RuntimeError):
    """Not a scratch database: the generator never writes fixture data there."""


def assert_scratch() -> None:
    if settings.DEBUG or os.environ.get("NUMO9_ALLOW_FIXTURES") == "1":
        return
    raise FixtureRefused(
        "Fixture data goes into a scratch or staging database only: set NUMO9_ALLOW_FIXTURES=1."
    )


@dataclass
class FixtureReport:
    practice: Practice | None = None
    organisations: list[int] = field(default_factory=list)
    lines: int = 0
    contacts: int = 0
    seconds: float = 0.0


def org_name(rng: random.Random, n: int) -> str:
    return f"{PREFIX} {rng.choice(PLACES)} {rng.choice(TRADES)} {n:05d} {rng.choice(FORMS)}"


def _chart(organisation: Organisation) -> list[Account]:
    made = []
    for code, name, subtype in CHART:
        item = Account(
            organisation=organisation,
            code=code,
            name_i18n={"en-ca": name},
            type=SUBTYPE_TYPE[subtype],
            subtype=subtype,
        )
        item.save()
        made.append(item)
    return made


def _lines(organisation: Organisation, accounts: list[Account], lines: int, seed: int) -> int:
    entries = lines // LINES_PER_ENTRY
    if entries <= 0:
        return 0
    params: dict[str, Any] = {
        "org": organisation.pk,
        "seed": f"fixture-{seed}-{organisation.pk}-",
        "entries": entries,
        "start": timezone.localdate() - dt.timedelta(days=365),
        "accounts": [a.pk for a in accounts],
        "account_count": len(accounts),
        "salt": seed % 1000,
    }
    with connection.cursor() as cursor:
        cursor.execute(INSERT_ENTRIES, params)
        cursor.execute(INSERT_LINES, params)
        cursor.execute(POST_ENTRIES, params)
    JournalSequence(organisation=organisation, next_number=entries + 1).save()
    return entries * LINES_PER_ENTRY


def _contacts(organisation: Organisation, rng: random.Random, count: int) -> int:
    for n in range(count):
        roles = ["customer"] if n % 3 else ["supplier"]
        Contact(
            organisation=organisation,
            display_name=f"{rng.choice(PLACES)} {rng.choice(TRADES)} {n + 1} {rng.choice(FORMS)}",
            roles=roles,
        ).save()
    return count


def _admin(practice: Practice, email: str) -> None:
    user_model = get_user_model()
    user = user_model.objects.filter(email=email).first()
    if user is None:
        user = user_model.objects.create_user(email=email, password=None)
    PracticeMember.objects.get_or_create(
        practice=practice, user=user, defaults={"role": PracticeRole.PRACTICE_ADMIN}
    )


def make_practice_fixture(
    *,
    orgs: int,
    lines: int,
    contacts: int = 5,
    seed: int = 1,
    practice_name: str = f"{PREFIX} Practice LLP",
    admin_email: str = "fixture-admin@example.com",
    progress: Callable[[int, int], None] | None = None,
) -> FixtureReport:
    """Build (or extend) the fixture practice with ``orgs`` new organisations."""
    assert_scratch()
    started = time.perf_counter()
    rng = random.Random(seed)  # noqa: S311 — fixture names, not secrets
    report = FixtureReport()
    practice, _ = Practice.objects.get_or_create(name=practice_name)
    report.practice = practice
    _admin(practice, admin_email)
    first = PracticeAssignment.objects.filter(practice=practice).count() + 1
    for n in range(first, first + orgs):
        with transaction.atomic():
            organisation = Organisation.objects.create(name=org_name(rng, n))
            PracticeAssignment.objects.create(
                practice=practice, organisation=organisation, role=AssignmentRole.FULL_SERVICE
            )
            with org_context(organisation):
                accounts = _chart(organisation)
                report.lines += _lines(organisation, accounts, lines, seed)
                report.contacts += _contacts(organisation, rng, contacts)
        report.organisations.append(organisation.pk)
        if progress is not None:
            progress(n - first + 1, orgs)
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE ledger_journalentry")
        cursor.execute("ANALYZE ledger_journalline")
    report.seconds = time.perf_counter() - started
    return report
