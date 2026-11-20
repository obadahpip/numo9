"""``manage.py seed_search --docs 1000000`` — a search index of a million documents (A-09-T10).

Performance fixture for the search API budget (p95 < 150 ms, ``tools/perf/k6/search.js``): one
organisation, "Search Seed Bakery Inc.", owned by ``--email`` (default
``seed-search@numo9.test``), with ``--docs`` documents spread over contacts, accounts, journals
and files — Canadian-style names (accents included), account codes, journal numbers, amounts and
narrations — written straight into the index in batches by PostgreSQL (``generate_series``, the
search vector computed the same way as the registry's). The documents point at no record: this is
an index benchmark, not someone's books; ``reindex_search`` would remove them.

The owner gets an unusable password unless ``--password`` is given (then the email address is
verified so k6 can sign in). Dev and staging only: refuses with ``DEBUG`` off unless ``--force``.
"""

from __future__ import annotations

import time
from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction

from numo9.accounts.models import User
from numo9.search.models import SearchDocument
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole

ORG_NAME = "Search Seed Bakery Inc."
BATCH = 100_000
GIN_INDEXES = ("search_doc_vector_idx", "search_doc_title_trgm_idx", "search_doc_code_trgm_idx")

FIRST = [
    "Maple",
    "Cedar",
    "Northern",
    "Érable",
    "Pinecrest",
    "Laurentian",
    "Prairie",
    "Harbour",
    "Rideau",
    "Fraser",
    "Muskoka",
    "Algonquin",
    "Saint-Laurent",
    "Okanagan",
    "Bluewater",
    "Granville",
    "Château",
    "Huron",
    "Kootenay",
    "Gatineau",
    "Acadia",
    "Niagara",
    "Yukon",
    "Beaumont",
    "Trembley",
    "Côté",
    "Patel",
    "Nguyen",
    "Singh",
    "MacLeod",
]
SECOND = [
    "Roofing",
    "Bakery",
    "Dental",
    "Supply",
    "Plumbing",
    "Logistics",
    "Rénovations",
    "Café",
    "Consulting",
    "Hardware",
    "Landscaping",
    "Electric",
    "Print",
    "Fitness",
    "Auto",
    "Foods",
    "Design",
    "Pharmacy",
    "Studio",
    "Builders",
]
SUFFIX = ["Ltd.", "Inc.", "Co.", "Corp.", "Ltée", "& Sons", "Group", "Enterprises"]
NARRATION = [
    "rent",
    "payroll",
    "accrual",
    "depreciation",
    "insurance",
    "GST/HST",
    "reclass",
    "utilities",
    "loan interest",
    "bank fees",
    "inventory count",
    "year-end adjustment",
]

_SQL = """
WITH n AS (SELECT g AS i FROM generate_series(%(start)s, %(stop)s) g),
d AS (
  SELECT i,
    (ARRAY['contacts.contact','ledger.account','ledger.journalentry','files.document'])
      [1 + i %% 4] AS t,
    (%(first)s::text[])[1 + (i / 4 * 7) %% %(nf)s]
      || ' ' || (%(second)s::text[])[1 + (i / 4 * 13) %% %(ns)s]
      || ' ' || (%(suffix)s::text[])[1 + (i / 4 * 3) %% %(nx)s] AS name,
    (%(narration)s::text[])[1 + (i / 4) %% %(nn)s] AS narration
  FROM n
)
INSERT INTO search_searchdocument (
  public_id, created_at, updated_at, organisation_id, object_type, object_id, title, subtitle,
  code, body, amount, date, url, permission_key, feature_key, search_vector
)
SELECT gen_random_uuid(), now(), now(), %(org)s, t, 'seed-' || i,
  CASE t WHEN 'ledger.account' THEN name || ' expense'
         WHEN 'ledger.journalentry' THEN 'MJ-' || lpad(i::text, 7, '0') || ' · ' || narration
         WHEN 'files.document' THEN lower(replace(name, ' ', '-')) || '-' || i || '.pdf'
         ELSE name || ' ' || i END,
  CASE t WHEN 'contacts.contact' THEN 'Customer' WHEN 'ledger.account' THEN 'Expense'
         WHEN 'ledger.journalentry' THEN 'Journal' ELSE 'Document' END,
  CASE t WHEN 'ledger.account' THEN (1000 + i %% 9000)::text
         WHEN 'ledger.journalentry' THEN 'MJ-' || lpad(i::text, 7, '0') ELSE '' END,
  CASE t WHEN 'ledger.journalentry' THEN narration || ' for ' || name ELSE '' END,
  CASE t WHEN 'ledger.journalentry' THEN ((i * 37) %% 500000) / 100.0 END,
  CASE t WHEN 'ledger.journalentry' THEN DATE '2024-01-01' + (i %% 1000) END,
  '/o/' || %(public)s || '/seed/' || i,
  CASE t WHEN 'contacts.contact' THEN 'contacts.contacts.view'
         WHEN 'files.document' THEN 'documents.file.view' ELSE 'accounting.journals.view' END,
  CASE t WHEN 'contacts.contact' THEN 'accounting.contacts.read'
         WHEN 'files.document' THEN 'accounting.documents.read'
         ELSE 'accounting.journals.read' END,
  NULL
FROM d
"""

_VECTORS = """
UPDATE search_searchdocument SET search_vector =
    setweight(to_tsvector('simple', unaccent(title)), 'A')
    || setweight(to_tsvector('simple', unaccent(code || ' ' || subtitle)), 'B')
    || setweight(to_tsvector('simple', unaccent(body)), 'C')
WHERE organisation_id = %(org)s AND search_vector IS NULL AND object_id LIKE 'seed-%%'
"""


class Command(BaseCommand):
    help = "Seed one organisation's search index with many documents (performance fixture)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--docs", type=int, default=1_000_000)
        parser.add_argument("--email", default="seed-search@numo9.test")
        parser.add_argument("--password", default="")
        parser.add_argument("--force", action="store_true", help="Run with DEBUG off")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not options["force"]:
            raise CommandError("Dev and staging only: pass --force to seed with DEBUG off.")
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQL only.")
        started = time.perf_counter()
        organisation = self._organisation(options["email"], options["password"])
        total = options["docs"]
        with org_context(organisation):
            have = SearchDocument.objects.filter(object_id__startswith="seed-").count()
        params: dict[str, Any] = {
            "org": organisation.pk,
            "public": str(organisation.public_id),
            "first": FIRST,
            "second": SECOND,
            "suffix": SUFFIX,
            "narration": NARRATION,
            "nf": len(FIRST),
            "ns": len(SECOND),
            "nx": len(SUFFIX),
            "nn": len(NARRATION),
        }
        for start in range(have + 1, total + 1, BATCH):
            stop = min(total, start + BATCH - 1)
            with transaction.atomic(), org_context(organisation), connection.cursor() as cursor:
                cursor.execute(_SQL, {**params, "start": start, "stop": stop})
                cursor.execute(_VECTORS, params)
            self.stdout.write(f"  {stop:,} / {total:,}")
        with connection.cursor() as cursor:
            # Bulk inserts land in the GIN indexes' pending lists: merge them now (as VACUUM would)
            # so the benchmark measures the indexes, not the backlog.
            for name in GIN_INDEXES:
                cursor.execute("SELECT gin_clean_pending_list(%s::regclass)", [name])
            cursor.execute("ANALYZE search_searchdocument")
        self.stdout.write(
            f"{ORG_NAME} ({organisation.public_id}): {total:,} documents "
            f"in {time.perf_counter() - started:.0f} s"
        )

    def _organisation(self, email: str, password: str) -> Organisation:
        organisation = Organisation.objects.filter(name=ORG_NAME).order_by("pk").first()
        if organisation is None:
            organisation = Organisation.objects.create(name=ORG_NAME)
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email, name="Search Seed Owner")
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
