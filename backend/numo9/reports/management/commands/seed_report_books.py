"""K-01-T17 — the performance fixture of the report engine: one organisation with a 100,000-line
general ledger over the last 12 months, and an owner k6 can sign in as.

    python manage.py seed_report_books --lines 100000 --password "$SEED_PASSWORD"

10 lines an entry (five balanced pairs across 40 accounts: assets, liabilities, revenue and
expenses), dated over the 365 days before today, inserted with ``generate_series`` the way the
engine writes them (entries as drafts, their lines, then posted with consecutive numbers — the
append-only trigger allows exactly that). Idempotent: an organisation that already has its lines
is left as it is. Dev and staging only: refuses with ``DEBUG`` off unless ``--force``.
"""

from __future__ import annotations

import time
from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction

from numo9.accounts.models import User
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole

ORG_NAME = "Report Seed Interiors Inc."
LINES_PER_ENTRY = 10
SUBTYPES = ("current_asset", "current_liability", "revenue", "operating_expense")

INSERT_ENTRIES = """
INSERT INTO ledger_journalentry (public_id, organisation_id, created_at, updated_at, date, type,
    status, source_type, source_id, narration, book_scope)
SELECT md5(%(seed)s || n)::uuid, %(org)s, now(), now(), CURRENT_DATE - 364 + (n %% 365),
       'manual', 'draft', '', '', 'Report seed entry ' || n, 'both'
FROM generate_series(1, %(entries)s) AS n
"""

INSERT_LINES = """
INSERT INTO ledger_journalline (organisation_id, entry_id, line_no, account_id, debit, credit,
    book, tracking, description, tax_code, created_at, updated_at)
SELECT e.organisation_id, e.id, l.line_no,
       (%(accounts)s::bigint[])[1 + ((e.id * 7 + l.line_no * 13) %% %(account_count)s)],
       CASE WHEN l.line_no %% 2 = 1 THEN amount ELSE 0 END,
       CASE WHEN l.line_no %% 2 = 0 THEN amount ELSE 0 END,
       'both', '{}'::jsonb, '', '', now(), now()
FROM ledger_journalentry e
CROSS JOIN generate_series(1, %(per_entry)s) AS l(line_no)
CROSS JOIN LATERAL (
    SELECT ((e.id * 31 + ((l.line_no + 1) / 2) * 17) %% 500000 + 1) / 100.0 AS amount
) a
WHERE e.organisation_id = %(org)s AND e.status = 'draft'
"""

POST_ENTRIES = """
UPDATE ledger_journalentry e
   SET status = 'posted', number = n.number, posted_at = now()
  FROM (SELECT id, row_number() OVER (ORDER BY id) AS number
          FROM ledger_journalentry WHERE organisation_id = %(org)s) n
 WHERE e.id = n.id
"""


class Command(BaseCommand):
    help = "Seed one organisation with a large posted ledger (report engine performance fixture)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--lines", type=int, default=100_000)
        parser.add_argument("--email", default="seed-reports@numo9.test")
        parser.add_argument("--password", default="")
        parser.add_argument("--force", action="store_true", help="Run with DEBUG off")

    def handle(self, *args: Any, **options: Any) -> None:
        from numo9.ledger.models import SUBTYPE_TYPE, Account, JournalEntry, JournalSequence

        if not settings.DEBUG and not options["force"]:
            raise CommandError("Dev and staging only: pass --force to seed with DEBUG off.")
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQL only.")
        started = time.perf_counter()
        organisation = self._organisation(options["email"], options["password"])
        entries = max(1, options["lines"] // LINES_PER_ENTRY)
        with org_context(organisation):
            if JournalEntry.objects.exists():
                self.stdout.write(f"{ORG_NAME} ({organisation.public_id}): already seeded")
                return
            with transaction.atomic():
                accounts = []
                for n in range(40):
                    subtype = SUBTYPES[n % len(SUBTYPES)]
                    item = Account(
                        organisation=organisation,
                        code=f"{7000 + n}",
                        name_i18n={"en-ca": f"Seed account {n}"},
                        type=SUBTYPE_TYPE[subtype],
                        subtype=subtype,
                    )
                    item.save()
                    accounts.append(item)
                params: dict[str, Any] = {
                    "org": organisation.pk,
                    "seed": f"report-seed-{organisation.pk}-",
                    "entries": entries,
                    "per_entry": LINES_PER_ENTRY,
                    "accounts": [item.pk for item in accounts],
                    "account_count": len(accounts),
                }
                with connection.cursor() as cursor:
                    cursor.execute(INSERT_ENTRIES, params)
                    cursor.execute("ANALYZE ledger_journalentry")
                    cursor.execute(INSERT_LINES, params)
                    cursor.execute(POST_ENTRIES, params)
                JournalSequence.objects.update_or_create(
                    organisation=organisation, defaults={"next_number": entries + 1}
                )
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE ledger_journalentry")
            cursor.execute("ANALYZE ledger_journalline")
        self.stdout.write(
            f"{ORG_NAME} ({organisation.public_id}): {entries * LINES_PER_ENTRY:,} lines "
            f"in {time.perf_counter() - started:.0f} s"
        )

    def _organisation(self, email: str, password: str) -> Organisation:
        organisation = Organisation.objects.filter(name=ORG_NAME).order_by("pk").first()
        if organisation is None:
            organisation = Organisation.objects.create(name=ORG_NAME)
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email, name="Report Seed Owner")
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
            EmailAddress.objects.update_or_create(
                user=user, email=email, defaults={"verified": True, "primary": True}
            )
        OrganisationMember.objects.get_or_create(
            organisation=organisation, user=user, defaults={"role": OrganisationRole.OWNER}
        )
        return organisation
