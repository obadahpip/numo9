"""Hash chain per organisation: a changed, removed or inserted audit row is detected (A-04-T05).

Every organisation's events form one chain, in ``id`` order; platform and practice events (no
organisation) form the platform chain. Each event stores

    prev_hash = the hash of the chain's previous event (GENESIS for the first)
    hash      = SHA-256( prev_hash + "\\n" + canonical JSON of the event's content )

The canonical JSON (``payload()``) covers everything the log shows — id, public id, time,
organisation, practice, actor kind, user, impersonator, label, action, record, changes, meta,
IP, device, request id, batch — with sorted keys and fixed formats, so the same row always gives
the same bytes.

**Writing** (``seal()``, called by ``record()`` inside the caller's transaction): a
transaction-scoped PostgreSQL advisory lock on the chain makes concurrent writers of one
organisation take turns; under the lock the next ``id`` is drawn from the sequence and the tail's
hash read, so ids and links follow the order in which the events commit. The lock is held until
the transaction ends (other organisations are never blocked).

**Checking** (``verify()``, ``manage.py audit_verify``): every chain is walked in ``id`` order;
an event whose hash does not match its content (changed row), whose ``prev_hash`` is not the
previous event's hash (a row removed or inserted before it) is reported. Deleting the newest
events of a chain cannot be seen from the chain alone — compare the reported head (count and last
hash) with an earlier run's output, which the scheduled check keeps (S-04).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from django.db import connection
from django.db.models import Q

from .context import normalise_ip
from .models import ID_SEQUENCE, AuditEvent

GENESIS = "0" * 64
#: First key of the advisory lock ("AUDT"); the second is the organisation's pk (0: platform).
LOCK_NAMESPACE = 0x41554454
PAYLOAD_VERSION = 1


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).isoformat(timespec="microseconds")


def _public(obj: Any) -> str | None:
    public_id = getattr(obj, "public_id", None)
    return str(public_id) if public_id is not None else None


def payload(event: AuditEvent) -> dict[str, Any]:
    """The hashed content of an event (stable across save and reload)."""
    return {
        "v": PAYLOAD_VERSION,
        "id": event.id,
        "public_id": str(event.public_id),
        "created_at": _iso(event.created_at),
        "organisation": _public(event.organisation) if event.organisation_id else None,
        "practice": _public(event.practice) if event.practice_id else None,
        "actor_kind": event.actor_kind,
        "actor_user": _public(event.actor_user) if event.actor_user_id else None,
        "impersonator": _public(event.impersonator) if event.impersonator_id else None,
        "actor_label": event.actor_label,
        "action": event.action,
        "object_type": event.object_type,
        "object_id": event.object_id,
        "object_label": event.object_label,
        "changes": event.changes,
        "meta": event.meta,
        "ip": normalise_ip(event.ip),
        "user_agent": event.user_agent,
        "request_id": event.request_id,
        "batch_id": str(event.batch_id) if event.batch_id else None,
    }


def canonical(content: dict[str, Any]) -> bytes:
    return json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def compute_hash(prev_hash: str, content: dict[str, Any]) -> str:
    return hashlib.sha256(prev_hash.encode("ascii") + b"\n" + canonical(content)).hexdigest()


def _chain(organisation_id: int | None) -> Q:
    return Q(organisation_id=organisation_id) if organisation_id else Q(organisation__isnull=True)


def seal(event: AuditEvent) -> None:
    """Give an unsaved event its id, ``prev_hash`` and ``hash`` (inside a transaction)."""
    if not connection.in_atomic_block:
        raise RuntimeError("seal() must run inside a transaction (record() opens one).")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)", [LOCK_NAMESPACE, event.organisation_id or 0]
        )
        cursor.execute("SELECT nextval(%s)", [ID_SEQUENCE])
        (event.id,) = cursor.fetchone()
    tail = (
        AuditEvent.platform_events.filter(_chain(event.organisation_id))
        .order_by("-id")
        .values_list("hash", flat=True)
        .first()
    )
    event.prev_hash = tail or GENESIS
    event.hash = compute_hash(event.prev_hash, payload(event))


# ---- verification -------------------------------------------------------------------------------


@dataclass
class Problem:
    event_id: int
    public_id: str
    reason: str  # "hash" (content changed) | "link" (previous event missing or inserted)


@dataclass
class ChainReport:
    organisation: str  # public id, or "platform"
    name: str
    events: int = 0
    head: str = GENESIS
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_chain(organisation_id: int | None, *, name: str, label: str) -> ChainReport:
    report = ChainReport(organisation=label, name=name)
    previous = GENESIS
    rows = (
        AuditEvent.platform_events.filter(_chain(organisation_id))
        .select_related("organisation", "practice", "actor_user", "impersonator")
        .order_by("id")
    )
    for event in rows.iterator(chunk_size=2000):
        report.events += 1
        if event.prev_hash != previous:
            report.problems.append(Problem(event.id, str(event.public_id), "link"))
        if compute_hash(event.prev_hash, payload(event)) != event.hash:
            report.problems.append(Problem(event.id, str(event.public_id), "hash"))
        previous = event.hash
    report.head = previous
    return report


def chains(organisation_public_id: str | None = None) -> Iterator[tuple[int | None, str, str]]:
    """(organisation pk or None, name, label) of the chains to check."""
    from numo9.tenancy.models import Organisation

    if organisation_public_id is None:
        yield None, "Platform and practice events", "platform"
    orgs = Organisation.objects.order_by("pk")
    if organisation_public_id is not None:
        orgs = orgs.filter(public_id=organisation_public_id)
    for org in orgs.only("pk", "public_id", "name"):
        yield org.pk, org.name, str(org.public_id)


def verify(organisation_public_id: str | None = None) -> list[ChainReport]:
    return [
        verify_chain(pk, name=name, label=label)
        for pk, name, label in chains(organisation_public_id)
    ]
