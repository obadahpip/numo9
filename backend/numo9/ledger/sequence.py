"""Gap-free journal numbers (C-02-T05, ADR-0003 §4).

``allocate_journal_number(organisation)`` returns the organisation's next journal number. It must
run inside the transaction that posts the entry (``transaction.atomic()``; the engine, C-02-T08):

1. ``UPDATE ledger_journalsequence SET next_number = next_number + 1 WHERE organisation_id = %s
   RETURNING next_number - 1`` — one statement: read and increment under the row lock;
2. the lock is held until the posting transaction commits or rolls back, so concurrent postings
   of the same organisation take numbers one after another, and a rolled-back posting releases
   its number to the next one: numbers are consecutive, with no gaps and no duplicates;
3. the organisation's first posting creates its sequence row (``INSERT … ON CONFLICT DO
   NOTHING``, safe when two first postings race) and takes number 1.

No session state and no PostgreSQL ``SEQUENCE`` (not transactional — a rollback would leave a gap),
so it works behind PgBouncer in transaction mode (S-06-T01).
"""

from __future__ import annotations

import uuid

from django.db import connection, transaction
from django.utils import timezone

from numo9.tenancy.models import Organisation

from .models import JournalSequence

UPDATE_SQL = (
    "UPDATE ledger_journalsequence SET next_number = next_number + 1, updated_at = %s "
    "WHERE organisation_id = %s RETURNING next_number - 1"
)
INSERT_SQL = (
    "INSERT INTO ledger_journalsequence "
    "(organisation_id, public_id, next_number, prefix, padding, created_at, updated_at) "
    "VALUES (%s, %s, 1, %s, %s, %s, %s) ON CONFLICT (organisation_id) DO NOTHING"
)


class SequenceOutsideTransaction(RuntimeError):
    """A journal number taken outside the posting transaction could never be given back."""


def allocate_journal_number(organisation: Organisation) -> int:
    """The organisation's next journal number, inside the caller's transaction."""
    if not transaction.get_connection().in_atomic_block:
        raise SequenceOutsideTransaction(
            "allocate_journal_number() must run inside the posting transaction."
        )
    now = timezone.now()
    with connection.cursor() as cursor:
        cursor.execute(UPDATE_SQL, [now, organisation.pk])
        row = cursor.fetchone()
        if row is None:
            defaults = JournalSequence()
            cursor.execute(
                INSERT_SQL,
                [organisation.pk, uuid.uuid4(), defaults.prefix, defaults.padding, now, now],
            )
            cursor.execute(UPDATE_SQL, [now, organisation.pk])
            row = cursor.fetchone()
    if row is None:  # pragma: no cover - the insert above guarantees the row
        raise RuntimeError("journal sequence row missing")
    return int(row[0])


def format_journal_number(organisation: Organisation, number: int | None) -> str:
    """``JE-000042`` (the organisation's prefix and padding), or "" for a draft."""
    if number is None:
        return ""
    sequence = (
        JournalSequence._base_manager.filter(organisation=organisation)
        .only("prefix", "padding")
        .first()
    ) or JournalSequence()
    return sequence.format(number)
