"""C-02-T03 — journal lines hash-partitioned by organisation, 16 partitions (ADR-0003 §5).

Acceptance: inserts route to partitions. ``ledger_journalline`` is ``PARTITION BY HASH
(organisation_id)`` with ``ledger_journalline_p00`` … ``p15``; all of one organisation's lines land
in one partition — the one PostgreSQL's hash picks for it — and different organisations spread
over several; the append-only trigger and the organisation RLS policy hold on a partition
addressed directly, not only on the parent; the trial balance query reads one partition.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from numo9.ledger import partitions
from numo9.ledger.models import JournalEntry, JournalLine, JournalStatus
from numo9.partitioning import children
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

D = Decimal


def _post(org: Organisation, amount: str = "100.00") -> JournalEntry:
    with org_context(org):
        cash = account(org, "1000", "Chequing", subtype="bank", gifi_id="1001")
        sales = account(org, "4000", "Sales", subtype="revenue", gifi_id="8000")
        entry = JournalEntry(organisation=org, date=dt.date(2026, 3, 31), narration="Cash sale")
        entry.save()
        JournalLine(entry=entry, account=cash, line_no=1, debit=D(amount)).save()
        JournalLine(entry=entry, account=sales, line_no=2, credit=D(amount)).save()
        JournalEntry.objects.filter(pk=entry.pk).update(
            status=JournalStatus.POSTED, number=1, posted_at=timezone.now()
        )
    return entry


def _homes(org: Organisation) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT tableoid::regclass::text FROM ledger_journalline "
            "WHERE organisation_id = %s",
            [org.pk],
        )
        return {row[0] for row in cursor.fetchall()}


def _hash_home(org: Organisation) -> str:
    """The partition PostgreSQL's own hash function assigns the organisation to."""
    with connection.cursor() as cursor:
        for remainder in range(partitions.PARTITIONS):
            cursor.execute(
                "SELECT satisfies_hash_partition("
                "'ledger_journalline'::regclass, %s, %s, %s::bigint)",
                [partitions.PARTITIONS, remainder, org.pk],
            )
            if cursor.fetchone()[0]:
                return partitions.partition_name(remainder)
    raise AssertionError("no partition")


def test_parent_is_hash_partitioned_into_sixteen() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_partkeydef('ledger_journalline'::regclass)")
        assert cursor.fetchone()[0] == "HASH (organisation_id)"
        names = [f"ledger_journalline_p{n:02d}" for n in range(16)]
        assert children(cursor, partitions.TABLE) == names


def test_an_organisations_lines_land_in_its_hash_partition() -> None:
    orgs = [Organisation.objects.create(name=f"Client {n} Inc.") for n in range(12)]
    for org in orgs:
        _post(org)
    homes = {org.pk: _homes(org) for org in orgs}
    for org in orgs:
        assert homes[org.pk] == {_hash_home(org)}, org.name  # one partition, the hashed one
    assert len({next(iter(h)) for h in homes.values()}) > 3  # spread over partitions


def test_append_only_holds_on_a_partition_addressed_directly() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    _post(org)
    (child,) = _homes(org)
    with (
        pytest.raises(DatabaseError, match="is posted"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            f'UPDATE "{child}" SET debit = 1 WHERE organisation_id = %s',  # noqa: S608 — table name
            [org.pk],
        )


def test_rls_holds_on_a_partition_addressed_directly() -> None:
    mine = Organisation.objects.create(name="Maple Bakery Inc.")
    theirs = Organisation.objects.create(name="Birch Holdings Inc.")
    _post(mine)
    _post(theirs)
    (child,) = _homes(theirs)
    role = f"numo9_part_probe_{uuid.uuid4().hex[:8]}"
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
        cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            with org_context(mine):
                cursor.execute(
                    f'SELECT count(*) FROM "{child}" WHERE organisation_id = %s',  # noqa: S608
                    [theirs.pk],
                )
                assert cursor.fetchone()[0] == 0  # another organisation's partition rows: hidden
                cursor.execute("SELECT count(*) FROM ledger_journalline")
                assert cursor.fetchone()[0] == 2  # my own two lines, through the parent
        finally:
            cursor.execute("RESET ROLE")


def test_a_per_organisation_query_reads_one_partition() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    _post(org)
    with connection.cursor() as cursor:
        cursor.execute(
            "EXPLAIN SELECT account_id, sum(debit) - sum(credit) FROM ledger_journalline "
            "WHERE organisation_id = %s GROUP BY account_id",
            [org.pk],
        )
        plan = "\n".join(row[0] for row in cursor.fetchall())
    scanned = set(re.findall(r" on (ledger_journalline_p\d\d) ", plan))
    assert scanned == {_hash_home(org)}, plan


def test_converting_twice_is_a_no_op() -> None:
    with connection.cursor() as cursor:
        assert partitions.convert_to_partitioned(cursor) is False
