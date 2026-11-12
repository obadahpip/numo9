"""The audit log query: one object for the viewer, the API and the exports (A-04-T07, T08).

``AuditQuery.from_params(request.query_params, organisation)`` reads the filters of the global
viewer; ``query.events()`` is the queryset every consumer pages through — the screen (cursor
pages), the CSV/XLSX/PDF exports (all rows) — so an export always holds exactly the rows the
screen shows for the same filters.

Filters (query parameters; repeat a parameter or separate values with commas for several):

- ``from`` / ``to`` — dates ``YYYY-MM-DD`` in the organisation's time zone, both included.
  **Default: the last 90 days** (today and the 89 days before it); one bound alone keeps the
  other's default (``from`` alone runs to today; ``to`` alone starts 89 days before it);
- ``user`` — user public ids (the actor), or ``system`` for system events;
- ``type`` — record types (model labels, e.g. ``testapp.AuditedInvoice``);
- ``action`` — full actions (``role.created``) or verbs (``created``, ``updated``, ``deleted``,
  ``restored``) matching every record type;
- ``object_type`` + ``object_id`` — one record;
- ``batch`` — one bulk operation (A-04-T06);
- ``q`` — text in the record's name, the actor's name or the action.

Order: newest first (``created_at``, then ``id``). **Cursor pagination**: ``cursor`` is an opaque
token for "events older than the last one shown" (keyset on ``(created_at, id)``), so a page is as
fast on the millionth row as on the first and rows written meanwhile never shift a page.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import uuid
import zoneinfo
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.models import DEFAULT_TIME_ZONE, Organisation

from .models import ActorKind, AuditEvent

DEFAULT_DAYS = 90
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
VERBS: frozenset[str] = frozenset({"created", "updated", "deleted", "restored"})
SYSTEM_USER = "system"


def _values(params: Mapping[str, Any], name: str) -> list[str]:
    getlist = getattr(params, "getlist", None)
    raw = getlist(name) if callable(getlist) else [params.get(name)] if params.get(name) else []
    values: list[str] = []
    for item in raw:
        values.extend(v.strip() for v in str(item).split(",") if v.strip())
    return values


def _date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        raise api_error(errors.AUDIT_BAD_DATE) from None


def time_zone_of(organisation: Organisation | None) -> zoneinfo.ZoneInfo:
    name = getattr(organisation, "time_zone", "") or DEFAULT_TIME_ZONE
    try:
        return zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return zoneinfo.ZoneInfo(DEFAULT_TIME_ZONE)


def encode_cursor(event: AuditEvent) -> str:
    raw = json.dumps({"t": event.created_at.isoformat(), "i": event.id}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(token: str) -> tuple[dt.datetime, int]:
    try:
        padded = token + "=" * (-len(token) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        at = dt.datetime.fromisoformat(data["t"])
        if at.tzinfo is None:
            raise ValueError("naive")
        return at, int(data["i"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise api_error(errors.AUDIT_BAD_CURSOR) from None


@dataclass(frozen=True)
class AuditQuery:
    date_from: dt.date
    date_to: dt.date
    time_zone: zoneinfo.ZoneInfo
    default_range: bool = True
    users: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    object_type: str = ""
    object_id: str = ""
    batch: uuid.UUID | None = None
    text: str = ""
    #: Platform log only: one organisation (public id), or None for every event.
    organisation_id: uuid.UUID | None = None
    #: Exports: events written up to this moment only (not the export's own event).
    until: dt.datetime | None = None

    # ---- building ----------------------------------------------------------------------------

    @classmethod
    def from_params(
        cls,
        params: Mapping[str, Any],
        organisation: Organisation | None,
        *,
        today: dt.date | None = None,
        platform: bool = False,
    ) -> AuditQuery:
        tz = time_zone_of(organisation)
        today = today or timezone.now().astimezone(tz).date()
        date_from, date_to = _date(params.get("from")), _date(params.get("to"))
        default_range = date_from is None and date_to is None
        span = dt.timedelta(days=DEFAULT_DAYS - 1)
        if date_to is None:
            date_to = today if date_from is None or date_from <= today else date_from
        if date_from is None:
            date_from = date_to - span
        if date_from > date_to:
            raise api_error(errors.AUDIT_DATE_ORDER)
        users = tuple(_values(params, "user"))
        for user in users:
            if user != SYSTEM_USER:
                _uuid(user, "user")
        batch = params.get("batch") or None
        org_filter = params.get("organisation") if platform else None
        return cls(
            date_from=date_from,
            date_to=date_to,
            time_zone=tz,
            default_range=default_range,
            users=users,
            types=tuple(_values(params, "type")),
            actions=tuple(_values(params, "action")),
            object_type=str(params.get("object_type") or "").strip(),
            object_id=str(params.get("object_id") or "").strip(),
            batch=_uuid(batch, "batch") if batch else None,
            text=str(params.get("q") or "").strip()[:100],
            organisation_id=_uuid(org_filter, "organisation") if org_filter else None,
        )

    # ---- running -----------------------------------------------------------------------------

    @property
    def starts_at(self) -> dt.datetime:
        return dt.datetime.combine(self.date_from, dt.time.min, tzinfo=self.time_zone)

    @property
    def ends_before(self) -> dt.datetime:
        next_day = self.date_to + dt.timedelta(days=1)
        return dt.datetime.combine(next_day, dt.time.min, tzinfo=self.time_zone)

    def apply(self, events: QuerySet[AuditEvent]) -> QuerySet[AuditEvent]:
        """The filtered, newest-first events (``events``: an organisation's, or every one)."""
        events = events.filter(created_at__gte=self.starts_at, created_at__lt=self.ends_before)
        if self.until is not None:
            events = events.filter(created_at__lte=self.until)
        if self.organisation_id is not None:
            events = events.filter(organisation__public_id=self.organisation_id)
        if self.users:
            who = Q()
            ids = [u for u in self.users if u != SYSTEM_USER]
            if ids:
                who |= Q(actor_user__public_id__in=ids)
            if SYSTEM_USER in self.users:
                who |= Q(actor_kind=ActorKind.SYSTEM, actor_user__isnull=True)
            events = events.filter(who)
        if self.types:
            events = events.filter(object_type__in=self.types)
        if self.actions:
            what = Q()
            for action in self.actions:
                what |= Q(action__endswith=f".{action}") if action in VERBS else Q(action=action)
            events = events.filter(what)
        if self.object_type:
            events = events.filter(object_type=self.object_type)
        if self.object_id:
            events = events.filter(object_id=self.object_id)
        if self.batch is not None:
            events = events.filter(batch_id=self.batch)
        if self.text:
            events = events.filter(
                Q(object_label__icontains=self.text)
                | Q(actor_label__icontains=self.text)
                | Q(action__icontains=self.text)
            )
        return events.order_by("-created_at", "-id")

    def describe(self) -> dict[str, Any]:
        """The range and filters as applied (shown above the list and in exports)."""
        return {
            "from": self.date_from.isoformat(),
            "to": self.date_to.isoformat(),
            "default": self.default_range,
            "time_zone": self.time_zone.key,
            "user": list(self.users),
            "type": list(self.types),
            "action": list(self.actions),
            "object_type": self.object_type,
            "object_id": self.object_id,
            "batch": str(self.batch) if self.batch else None,
            "q": self.text,
        }


def _uuid(value: Any, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value).strip())
    except ValueError:
        raise api_error(errors.AUDIT_BAD_FILTER, name=name) from None


def after_cursor(events: QuerySet[AuditEvent], token: str | None) -> QuerySet[AuditEvent]:
    """Events older than the cursor's (keyset on ``(created_at, id)``, newest first)."""
    if not token:
        return events
    at, event_id = decode_cursor(token)
    return events.filter(Q(created_at__lt=at) | Q(created_at=at, id__lt=event_id))


def page(
    events: QuerySet[AuditEvent], token: str | None, limit: int
) -> tuple[list[AuditEvent], str | None]:
    rows = list(after_cursor(events, token)[: limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, (encode_cursor(rows[-1]) if more and rows else None)


def limit_of(params: Mapping[str, Any]) -> int:
    raw = params.get("limit")
    if raw in (None, ""):
        return DEFAULT_LIMIT
    try:
        value = int(str(raw))
    except ValueError:
        value = 0
    if not 1 <= value <= MAX_LIMIT:
        raise api_error(errors.AUDIT_BAD_LIMIT, max=MAX_LIMIT)
    return value


def loose_distinct(column: str, organisation: Organisation) -> list[Any]:
    """Distinct non-empty values of an indexed column in an organisation's events, fast on
    millions of rows (a "loose index scan": one index probe per distinct value)."""
    from django.db import connection

    allowed = {"object_type", "actor_user_id"}
    if column not in allowed:
        raise ValueError(column)
    sql = f"""
        WITH RECURSIVE seen(v) AS (
            SELECT min({column}) FROM audit_event WHERE organisation_id = %(org)s
            UNION ALL
            SELECT (SELECT min({column}) FROM audit_event
                    WHERE organisation_id = %(org)s AND {column} > seen.v)
            FROM seen WHERE seen.v IS NOT NULL
        )
        SELECT v FROM seen WHERE v IS NOT NULL
    """  # noqa: S608 — column from the allow-list above
    with connection.cursor() as cursor:
        cursor.execute(sql, {"org": organisation.pk})
        return [row[0] for row in cursor.fetchall() if row[0] not in ("", None)]


def iter_all(events: QuerySet[AuditEvent], *, chunk: int = 2000) -> Iterable[AuditEvent]:
    """Every row of a query, newest first, in keyset chunks (exports)."""
    token: str | None = None
    while True:
        rows, token = page(events, token, chunk)
        yield from rows
        if token is None:
            return
