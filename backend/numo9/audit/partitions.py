"""Monthly partitions of ``audit_event`` (S-06-T03, T04; ADR-0005 §1, §3).

``audit_event`` is a parent ``PARTITION BY RANGE (created_at)`` with one child per calendar month
(UTC) named ``audit_event_pYYYYMMDD`` — pg_partman's naming — and ``audit_event_default`` for
anything outside the created months. Both ways of managing it produce the same children:

- **pg_partman installed** in the database (``CREATE EXTENSION pg_partman``, a server decision;
  never created by Numo9): the parent is registered with ``partman.create_parent`` and
  ``partman.run_maintenance`` creates the months ahead;
- **otherwise** ``create_month`` runs the same DDL itself.

Every child is append-only like the parent: the parent's row trigger is cloned on each child and
``UPDATE``, ``DELETE``, ``TRUNCATE`` are revoked on each child here (privileges on a child are
checked when it is addressed directly).

``ensure_partitions`` (daily beat job, S-06-T04) keeps the current month through month + 3 in
place and reports what is missing.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

from django.db import connection, transaction

from numo9.partitioning import name_child_indexes, rebuild_as_partitioned

logger = logging.getLogger(__name__)

TABLE = "audit_event"
DEFAULT_PARTITION = f"{TABLE}_default"
#: Months kept ready after the current one (ADR-0005 §3).
MONTHS_AHEAD = 3
#: Transaction advisory lock serialising partition DDL ("AUDP").
LOCK_KEY = 0x41554450


def month_start(day: dt.date | dt.datetime) -> dt.date:
    return dt.date(day.year, day.month, 1)


def add_months(month: dt.date, count: int) -> dt.date:
    index = month.year * 12 + month.month - 1 + count
    return dt.date(index // 12, index % 12 + 1, 1)


def partition_name(month: dt.date) -> str:
    return f"{TABLE}_p{month:%Y%m%d}"


def _bound(month: dt.date) -> str:
    return f"{month:%Y-%m-%d} 00:00:00+00"


def has_partman(cursor: Any) -> bool:
    """Is pg_partman installed in this database (not merely available on the server)?"""
    cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_partman'")
    return cursor.fetchone() is not None


def _partman_schema(cursor: Any) -> str:
    cursor.execute(
        "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace "
        "WHERE e.extname = 'pg_partman'"
    )
    return str(cursor.fetchone()[0])


def is_partitioned(cursor: Any, table: str = TABLE) -> bool:
    cursor.execute(
        "SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass(%s)", [f"public.{table}"]
    )
    row = cursor.fetchone()
    return row is not None and row[0] == "p"


def partitions(cursor: Any, table: str = TABLE) -> list[str]:
    """Children of the parent, by name."""
    cursor.execute(
        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
        "WHERE i.inhparent = to_regclass(%s) ORDER BY c.relname",
        [f"public.{table}"],
    )
    return [row[0] for row in cursor.fetchall()]


def lock_down(cursor: Any, child: str) -> None:
    """Append-only privileges on one child (the trigger is cloned from the parent); its indexes
    named after the parent's."""
    name_child_indexes(cursor, TABLE, child)
    cursor.execute(f'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE "{child}" FROM PUBLIC')
    cursor.execute(f'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE "{child}" FROM CURRENT_USER')


def create_default(cursor: Any) -> None:
    cursor.execute(
        f'CREATE TABLE IF NOT EXISTS "{DEFAULT_PARTITION}" PARTITION OF "{TABLE}" DEFAULT'
    )
    lock_down(cursor, DEFAULT_PARTITION)


def create_month(cursor: Any, month: dt.date) -> bool:
    """Create the month's child (plain DDL); False when it already existed."""
    name = partition_name(month)
    if name in partitions(cursor):
        return False
    cursor.execute(
        f'CREATE TABLE "{name}" PARTITION OF "{TABLE}" '
        f"FOR VALUES FROM ('{_bound(month)}') TO ('{_bound(add_months(month, 1))}')"
    )
    lock_down(cursor, name)
    return True


def register_with_partman(cursor: Any, first_month: dt.date) -> None:
    """Hand the (empty) parent to pg_partman: monthly, ``MONTHS_AHEAD`` premade, default child."""
    schema = _partman_schema(cursor)
    cursor.execute(
        f"SELECT {schema}.create_parent(p_parent_table => %s, p_control => 'created_at', "
        "p_interval => '1 month', p_premake => %s, p_start_partition => %s, "
        "p_default_table => true)",
        [f"public.{TABLE}", MONTHS_AHEAD, _bound(first_month)],
    )
    for child in partitions(cursor):
        lock_down(cursor, child)


# ---- migration (S-06-T03) -----------------------------------------------------------------------


def convert_to_partitioned(cursor: Any, now: dt.datetime | None = None) -> None:
    """Turn a plain ``audit_event`` into the monthly-partitioned parent, keeping its rows.

    Same columns, defaults, constraint and index names (Django's state is unchanged), same
    sequence for ``id`` and the append-only trigger (``numo9.partitioning``); UPDATE, DELETE and
    TRUNCATE revoked on the parent and every child.
    """
    if is_partitioned(cursor):
        return
    now = now or dt.datetime.now(dt.UTC)
    cursor.execute(f"SELECT min(created_at) FROM {TABLE}")  # noqa: S608 — fixed table name
    oldest = cursor.fetchone()[0]
    first = month_start(oldest if oldest is not None and oldest < now else now)

    def make_children(cursor: Any) -> None:
        if has_partman(cursor):
            register_with_partman(cursor, first)
            return
        create_default(cursor)
        month = first
        while month <= add_months(month_start(now), MONTHS_AHEAD):
            create_month(cursor, month)
            month = add_months(month, 1)

    rebuild_as_partitioned(cursor, TABLE, "RANGE (created_at)", make_children)
    cursor.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON TABLE {TABLE} FROM PUBLIC")
    cursor.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON TABLE {TABLE} FROM CURRENT_USER")


# ---- maintenance (S-06-T04) ---------------------------------------------------------------------


@dataclass
class PartitionReport:
    created: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    default_rows: int = 0
    engine: str = "native"

    @property
    def ok(self) -> bool:
        return not self.missing and self.default_rows == 0


def ensure_partitions(now: dt.datetime | None = None, ahead: int = MONTHS_AHEAD) -> PartitionReport:
    """Create the current month through month + ``ahead``; report what's missing (alarm)."""
    now = now or dt.datetime.now(dt.UTC)
    report = PartitionReport()
    if connection.vendor != "postgresql":
        return report
    current = month_start(now)
    wanted = [add_months(current, n) for n in range(ahead + 1)]
    with transaction.atomic(), connection.cursor() as cursor:
        if not is_partitioned(cursor):
            report.missing = [partition_name(month) for month in wanted]
        else:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])
            before = set(partitions(cursor))
            if has_partman(cursor):
                report.engine = "pg_partman"
                schema = _partman_schema(cursor)
                cursor.execute(f"SELECT {schema}.run_maintenance(%s)", [f"public.{TABLE}"])
                for child in set(partitions(cursor)) - before:
                    lock_down(cursor, child)
            for month in wanted:  # also the native path; fills any gap pg_partman left
                try:
                    with transaction.atomic():
                        create_month(cursor, month)
                except Exception:  # e.g. rows of that month already sit in the default
                    logger.exception("audit partition %s could not be created", month)
            after = set(partitions(cursor))
            report.created = sorted(after - before)
            report.missing = [partition_name(m) for m in wanted if partition_name(m) not in after]
            if DEFAULT_PARTITION in after:
                cursor.execute(f'SELECT count(*) FROM "{DEFAULT_PARTITION}"')  # noqa: S608
                report.default_rows = int(cursor.fetchone()[0])
    if not report.ok:
        logger.error(
            "audit_event partitions need attention: missing=%s default_rows=%s",
            report.missing,
            report.default_rows,
        )
    return report
