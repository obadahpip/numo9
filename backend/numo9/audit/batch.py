"""Bulk operations as one audit batch (A-04-T06).

A bulk edit, an import, a recode of 500 lines or a bulk action over 200 organisations writes one
event per record **and** one summary event, all carrying the same ``batch_id`` — so the log can
show the operation as one line ("Recode 500 lines — 500 changes") that opens into its rows, and
one batch can be exported or undone as a whole (C-07).

    with audit_batch("Recode transactions", meta={"rule": rule.public_id}) as batch:
        for line in lines:
            line.account = new_account
            line.save()                       # each event gets batch.id
    # → summary event "audit.batch" with the counts

Inside the block every ``record()`` (directly or through ``AuditedModel``) gets the batch id.
When the block ends the summary is written: action ``audit.batch``, record ``audit.Batch`` /
the batch id / the label, ``meta`` = ``{"events": n, "actions": {action: n}, "types": [...],
"status": "completed" | "failed", …}``. A block that fails writes the summary with
``status: "failed"`` when its events were committed on their own (a job that commits row by row);
inside one transaction the events and the summary roll back together. Nested blocks join the
outer batch (one id, one summary).
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

logger = logging.getLogger("numo9.audit")

SUMMARY_ACTION = "audit.batch"
SUMMARY_TYPE = "audit.Batch"


@dataclass
class Batch:
    label: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    events: int = 0
    actions: Counter[str] = field(default_factory=Counter)
    types: set[str] = field(default_factory=set)

    def count(self, action: str, object_type: str) -> None:
        self.events += 1
        self.actions[action] += 1
        if object_type:
            self.types.add(object_type)


_current: ContextVar[Batch | None] = ContextVar("numo9_audit_batch", default=None)


def current_batch() -> Batch | None:
    return _current.get()


@contextmanager
def audit_batch(
    label: str,
    *,
    organisation: Organisation | None = None,
    meta: Mapping[str, Any] | None = None,
) -> Iterator[Batch]:
    """Group every event written in the block under one batch id + a summary event."""
    outer = _current.get()
    if outer is not None:
        yield outer  # nested: part of the outer operation
        return
    if not label or not label.strip():
        raise ValueError("An audit batch needs a label people can read, e.g. 'Bulk edit'.")
    batch = Batch(label=label.strip()[:300])
    token = _current.set(batch)
    status = "failed"
    try:
        yield batch
        status = "completed"
    finally:
        _current.reset(token)
        if status == "completed" or batch.events:
            _summary(batch, status, organisation, meta)


def _summary(
    batch: Batch, status: str, organisation: Organisation | None, meta: Mapping[str, Any] | None
) -> None:
    from .service import record

    try:
        record(
            SUMMARY_ACTION,
            organisation=organisation if organisation is not None else current_org(),
            object_type=SUMMARY_TYPE,
            object_id=str(batch.id),
            object_label=batch.label,
            meta={
                **dict(meta or {}),
                "events": batch.events,
                "actions": dict(sorted(batch.actions.items())),
                "types": sorted(batch.types),
                "status": status,
            },
            batch_id=batch.id,
        )
    except Exception:
        if status == "completed":
            raise
        # A failed block's own error is the one that matters (its transaction may be broken).
        logger.warning("audit batch summary not written", extra={"batch_id": str(batch.id)})
