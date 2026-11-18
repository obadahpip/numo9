"""Turn a plain PostgreSQL table into a partitioned parent, keeping everything (S-06, C-02-T03).

``rebuild_as_partitioned(cursor, table, "RANGE (created_at)", make_children)``:

1. records the table's primary key, unique and foreign-key constraints, indexes, row triggers,
   row-level security (flags and policies) and the sequences its columns own;
2. renames it aside and creates the parent with the same columns, defaults, NOT NULL and CHECK
   constraints (``LIKE … INCLUDING …``), then the same constraints and indexes **under the same
   names** (Django's migration state is unchanged);
3. lets ``make_children(cursor)`` create the partitions;
4. copies the rows (before triggers and forced RLS exist, so the copy itself is never refused),
   moves sequence ownership to the new columns and drops the old table;
5. recreates the triggers (cloned by PostgreSQL on every partition) and RLS on the parent **and on
   every partition** (a partition addressed directly is checked against its own policies), and
   names each partition's indexes after the parent's (``name_child_indexes``).

Privileges are the caller's (``audit_event`` revokes UPDATE/DELETE/TRUNCATE).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _rows(cursor: Any, sql: str, params: list[Any]) -> list[tuple[Any, ...]]:
    cursor.execute(sql, params)
    return [tuple(row) for row in cursor.fetchall()]


def is_partitioned(cursor: Any, table: str) -> bool:
    cursor.execute("SELECT relkind FROM pg_class WHERE oid = to_regclass(%s)", [f"public.{table}"])
    row = cursor.fetchone()
    return row is not None and row[0] == "p"


def children(cursor: Any, table: str) -> list[str]:
    return [
        str(row[0])
        for row in _rows(
            cursor,
            "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE i.inhparent = to_regclass(%s) ORDER BY c.relname",
            [f"public.{table}"],
        )
    ]


def name_child_indexes(cursor: Any, table: str, child: str) -> None:
    """Name a partition's indexes after the parent's (``<parent index>_<partition suffix>``), so a
    refusal names the constraint the code knows, e.g. ``ledger_line_no_unique_p06`` instead of
    PostgreSQL's generated ``ledger_journalline_p06_organisation_id_entry_id_line_no_key``."""
    suffix = child.removeprefix(f"{table}_")
    for index, parent_index in _rows(
        cursor,
        "SELECT ci.relname, pi.relname FROM pg_inherits h "
        "JOIN pg_class ci ON ci.oid = h.inhrelid JOIN pg_class pi ON pi.oid = h.inhparent "
        "JOIN pg_index x ON x.indexrelid = ci.oid "
        "WHERE x.indrelid = to_regclass(%s) AND pi.relkind = 'I'",
        [f"public.{child}"],
    ):
        wanted = f"{parent_index[: 62 - len(suffix)]}_{suffix}"
        if index != wanted:
            cursor.execute(f'ALTER INDEX "{index}" RENAME TO "{wanted}"')


def apply_rls(
    cursor: Any, table: str, rls: tuple[bool, bool], policies: list[tuple[Any, ...]]
) -> None:
    """Row-level security flags and policies (as read from ``pg_policies``) on ``table``."""
    enabled, forced = rls
    if not enabled:
        return
    cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    if forced:
        cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    for name, permissive, roles, command, qual, check in policies:
        sql = f'CREATE POLICY "{name}" ON "{table}" AS {permissive} FOR {command} '
        sql += "TO " + ", ".join("PUBLIC" if r == "public" else f'"{r}"' for r in roles)
        if qual is not None:
            sql += f" USING ({qual})"
        if check is not None:
            sql += f" WITH CHECK ({check})"
        cursor.execute(sql)


def rls_of(cursor: Any, table: str) -> tuple[tuple[bool, bool], list[tuple[Any, ...]]]:
    flags = _rows(
        cursor,
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = to_regclass(%s)",
        [f"public.{table}"],
    )[0]
    policies = _rows(
        cursor,
        "SELECT policyname, permissive, roles, cmd, qual, with_check FROM pg_policies "
        "WHERE schemaname = 'public' AND tablename = %s ORDER BY policyname",
        [table],
    )
    return (bool(flags[0]), bool(flags[1])), policies


def rebuild_as_partitioned(
    cursor: Any, table: str, partition_by: str, make_children: Callable[[Any], None]
) -> bool:
    """Rebuild ``table`` as a parent ``PARTITION BY <partition_by>``; False if it already is."""
    if is_partitioned(cursor, table):
        return False
    regclass = f"public.{table}"
    old = f"{table}_unpartitioned"
    indexes = _rows(
        cursor,
        "SELECT i.relname, pg_get_indexdef(i.oid) FROM pg_index x "
        "JOIN pg_class i ON i.oid = x.indexrelid "
        "LEFT JOIN pg_constraint c ON c.conindid = x.indexrelid AND c.conrelid = x.indrelid "
        "WHERE x.indrelid = to_regclass(%s) AND c.oid IS NULL ORDER BY i.relname",
        [regclass],
    )
    constraints = _rows(
        cursor,
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = to_regclass(%s) AND contype IN ('p', 'u', 'f') "
        "ORDER BY contype DESC, conname",  # primary key, unique, then foreign keys
        [regclass],
    )
    triggers = _rows(
        cursor,
        "SELECT tgname, pg_get_triggerdef(oid) FROM pg_trigger "
        "WHERE tgrelid = to_regclass(%s) AND NOT tgisinternal ORDER BY tgname",
        [regclass],
    )
    sequences = _rows(
        cursor,
        "SELECT s.relname, a.attname FROM pg_depend d "
        "JOIN pg_class s ON s.oid = d.objid AND s.relkind = 'S' "
        "JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid "
        "WHERE d.refobjid = to_regclass(%s) AND d.deptype = 'a'",
        [regclass],
    )
    rls, policies = rls_of(cursor, table)

    cursor.execute(f'ALTER TABLE "{table}" RENAME TO "{old}"')
    for name, _definition in constraints:
        cursor.execute(f'ALTER TABLE "{old}" DROP CONSTRAINT "{name}"')
    for name, _definition in indexes:
        cursor.execute(f'DROP INDEX "{name}"')
    for name, _definition in triggers:
        cursor.execute(f'DROP TRIGGER "{name}" ON "{old}"')
    for name, *_rest in policies:
        cursor.execute(f'DROP POLICY "{name}" ON "{old}"')

    cursor.execute(
        f'CREATE TABLE "{table}" (LIKE "{old}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS '
        f"INCLUDING STORAGE INCLUDING COMMENTS) PARTITION BY {partition_by}"
    )
    for name, definition in constraints:
        cursor.execute(f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" {definition}')
    for _name, definition in indexes:
        cursor.execute(definition.replace(f" ON public.{old} ", f" ON public.{table} "))
    make_children(cursor)

    cursor.execute(f'INSERT INTO "{table}" SELECT * FROM "{old}"')  # noqa: S608 — fixed names
    for sequence, column in sequences:
        cursor.execute(f'ALTER SEQUENCE "{sequence}" OWNED BY "{table}"."{column}"')
    cursor.execute(f'DROP TABLE "{old}"')

    for _name, definition in triggers:
        cursor.execute(definition.replace(f" ON public.{old} ", f" ON public.{table} "))
    apply_rls(cursor, table, rls, policies)
    for child in children(cursor, table):
        apply_rls(cursor, child, rls, policies)
        name_child_indexes(cursor, table, child)
    return True
