"""Read-replica routing for reporting queries (S-06-T10).

Reports (trial balances, aging, dashboards) can run on a read replica so they don't compete with
postings. Code marks such reads with ``using_replica()``::

    with using_replica():
        rows = list(JournalLine.objects.filter(...))

``ReplicaRouter`` (``DATABASE_ROUTERS``) sends **reads** inside the block to the ``replica``
alias when one is configured (``DATABASE_REPLICA_URL``, settings/database.py) and to ``default``
otherwise — until the replica server exists (Phase 5), it points to the primary and nothing
changes. Writes always go to ``default``; migrations run on ``default`` only. Reads inside an
open transaction on ``default`` stay there (they may need the transaction's own writes).

The tenancy GUC wrapper is installed on every PostgreSQL connection, the replica's too, so
row-level security applies to replica reads as well.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from django.conf import settings
from django.db import connections

DEFAULT = "default"
REPLICA = "replica"

_replica_reads: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "numo9_replica_reads", default=False
)


@contextmanager
def using_replica() -> Iterator[str]:
    """Route this block's reads to the replica (when configured); yields the alias used."""
    token = _replica_reads.set(True)
    try:
        yield read_alias()
    finally:
        _replica_reads.reset(token)


def replica_configured() -> bool:
    return REPLICA in settings.DATABASES


def read_alias() -> str:
    """Where a read goes now: ``replica`` inside ``using_replica()`` when there is one."""
    if not _replica_reads.get() or not replica_configured():
        return DEFAULT
    if connections[DEFAULT].in_atomic_block:
        return DEFAULT  # the transaction's own writes are only visible on the primary
    return REPLICA


class ReplicaRouter:
    def db_for_read(self, model: Any, **hints: Any) -> str | None:
        return read_alias()

    def db_for_write(self, model: Any, **hints: Any) -> str | None:
        return DEFAULT

    def allow_relation(self, obj1: Any, obj2: Any, **hints: Any) -> bool | None:
        return True  # the replica is a copy of the primary

    def allow_migrate(self, db: str, app_label: str, **hints: Any) -> bool | None:
        return db == DEFAULT
