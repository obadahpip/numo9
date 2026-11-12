"""View a record as of a date: its state rebuilt from the audit log (A-04-T11) [EXTRA].

The record's events up to the moment asked for are replayed oldest first: each event's
``changes`` sets every field it names to the event's *new* value; ``…deleted`` marks the record
deleted and ``…restored`` undoes that. What comes out is what the record held at that moment as
far as the log recorded it:

- ``exists`` — the record had been created (its first event is on or before the moment) and was
  not deleted then;
- ``complete`` — the replay started from the record's creation event, so every field is known
  (records that existed before their model was audited only show the fields changed since);
- masked fields (SIN, bank details) stay hidden — the log never had their values.

A date (``YYYY-MM-DD``) means the end of that day in the organisation's time zone; a date-time is
taken as given.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from django.db.models import QuerySet

from .batch import SUMMARY_ACTION
from .models import AuditEvent
from .presenter import field_label


@dataclass
class Reconstruction:
    at: dt.datetime
    exists: bool = False
    deleted: bool = False
    complete: bool = False
    events: int = 0
    last_event: AuditEvent | None = None
    state: dict[str, Any] = field(default_factory=dict)

    def fields(self, object_type: str) -> list[dict[str, Any]]:
        rows = []
        for name, value in sorted(self.state.items()):
            masked = isinstance(value, dict) and value.get("masked") is True
            rows.append(
                {
                    "field": name,
                    "label": field_label(object_type, name),
                    "value": value,
                    "masked": masked,
                }
            )
        return rows


def reconstruct(events: QuerySet[AuditEvent], at: dt.datetime) -> Reconstruction:
    """Replay a record's events (any order given; replayed oldest first) up to ``at``."""
    result = Reconstruction(at=at)
    created_seen = False
    for event in events.filter(created_at__lte=at).order_by("created_at", "id").iterator():
        if event.action == SUMMARY_ACTION:
            continue
        verb = event.action.rsplit(".", 1)[-1]
        result.events += 1
        result.last_event = event
        if verb == "created":
            created_seen = True
            result.deleted = False
        for name, pair in (event.changes or {}).items():
            if isinstance(pair, list) and len(pair) == 2:
                result.state[name] = pair[1]
        if verb == "deleted":
            result.deleted = True
        elif verb == "restored":
            result.deleted = False
    result.complete = created_seen
    result.exists = result.events > 0 and not result.deleted
    return result
