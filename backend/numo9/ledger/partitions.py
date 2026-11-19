"""``ledger_journalline`` hash-partitioned by organisation, 16 partitions (C-02-T03, ADR-0003 §5).

Children ``ledger_journalline_p00`` … ``p15`` (``FOR VALUES WITH (MODULUS 16, REMAINDER n)``).
Every query is per organisation (scoped manager + RLS), so it reads exactly one partition; no
partition maintenance is needed (nothing is pre-created by date). The append-only trigger and the
organisation RLS policy apply on the parent and on every partition.
"""

from __future__ import annotations

from typing import Any

from numo9.partitioning import rebuild_as_partitioned

TABLE = "ledger_journalline"
PARTITIONS = 16


def partition_name(remainder: int) -> str:
    return f"{TABLE}_p{remainder:02d}"


def create_children(cursor: Any) -> None:
    for remainder in range(PARTITIONS):
        cursor.execute(
            f'CREATE TABLE "{partition_name(remainder)}" PARTITION OF "{TABLE}" '
            f"FOR VALUES WITH (MODULUS {PARTITIONS}, REMAINDER {remainder})"
        )


def convert_to_partitioned(cursor: Any) -> bool:
    """Rebuild the line table as the hash-partitioned parent, keeping its rows; False if done."""
    return rebuild_as_partitioned(cursor, TABLE, "HASH (organisation_id)", create_children)
