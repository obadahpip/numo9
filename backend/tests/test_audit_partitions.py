"""S-06-T03 — ``audit_event`` partitioned by month (ADR-0005 §1).

Acceptance: inserts route to the correct partition. The parent is ``PARTITION BY RANGE
(created_at)`` with monthly children ``audit_event_pYYYYMMDD`` from the oldest event's month
through month + 3 and a default child; an event lands in its month's child (the default only
outside them); every child is append-only like the parent (trigger and privileges); the model,
the service and the hash chain are unchanged.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import DatabaseError, connection, transaction
from freezegun import freeze_time

from numo9.audit import partitions
from numo9.audit.models import AuditEvent
from numo9.audit.service import record

pytestmark = pytest.mark.django_db


def _where(event: AuditEvent) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tableoid::regclass::text FROM audit_event WHERE created_at = %s AND id = %s",
            [event.created_at, event.id],
        )
        return str(cursor.fetchone()[0])


def _latest() -> AuditEvent:
    event = AuditEvent.platform_events.order_by("-id").first()
    assert event is not None
    return event


def test_parent_is_partitioned_by_month_with_three_months_ahead_and_a_default() -> None:
    month = partitions.month_start(dt.datetime.now(dt.UTC))
    with connection.cursor() as cursor:
        assert partitions.is_partitioned(cursor)
        cursor.execute(
            "SELECT pg_get_partkeydef('audit_event'::regclass)",
        )
        assert cursor.fetchone()[0] == "RANGE (created_at)"
        children = partitions.partitions(cursor)
    assert partitions.DEFAULT_PARTITION in children
    for ahead in range(partitions.MONTHS_AHEAD + 1):
        assert partitions.partition_name(partitions.add_months(month, ahead)) in children


def test_an_event_lands_in_its_months_partition() -> None:
    record("test.partition.now", organisation=None, object_type="test", object_id="1")
    event = _latest()
    assert _where(event) == partitions.partition_name(partitions.month_start(event.created_at))


def test_an_event_two_months_ahead_lands_in_that_months_partition() -> None:
    later = partitions.add_months(partitions.month_start(dt.datetime.now(dt.UTC)), 2)
    with freeze_time(dt.datetime(later.year, later.month, 15, 12, tzinfo=dt.UTC)):
        record("test.partition.later", organisation=None, object_type="test", object_id="2")
    assert _where(_latest()) == partitions.partition_name(later)


def test_an_event_beyond_the_created_months_lands_in_the_default_partition() -> None:
    with freeze_time("2099-06-15T12:00:00Z"):
        record("test.partition.far", organisation=None, object_type="test", object_id="3")
    assert _where(_latest()) == partitions.DEFAULT_PARTITION


@pytest.mark.parametrize("statement", ["UPDATE {t} SET action = 'x'", "DELETE FROM {t}"])
def test_every_partition_is_append_only(statement: str) -> None:
    record("test.partition.locked", organisation=None, object_type="test", object_id="4")
    child = _where(_latest())
    with (
        pytest.raises(DatabaseError, match="append-only"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(statement.format(t=f'"{child}"'))


def test_update_delete_truncate_are_revoked_on_every_child() -> None:
    with connection.cursor() as cursor:
        children = partitions.partitions(cursor)
        cursor.execute(
            "SELECT c.relname, a.privilege_type FROM pg_class c, aclexplode(c.relacl) a "
            "WHERE c.relname = ANY(%s) AND a.grantee = c.relowner",
            [children],
        )
        owner_privileges: dict[str, set[str]] = {}
        for name, privilege in cursor.fetchall():
            owner_privileges.setdefault(name, set()).add(privilege)
    assert set(owner_privileges) == set(children)  # every child has an explicit ACL
    for name, privileges in owner_privileges.items():
        assert {"INSERT", "SELECT"} <= privileges, name
        assert not privileges & {"UPDATE", "DELETE", "TRUNCATE"}, name


def test_creating_a_month_twice_is_harmless() -> None:
    month = partitions.add_months(partitions.month_start(dt.datetime.now(dt.UTC)), 1)
    with connection.cursor() as cursor:
        assert partitions.create_month(cursor, month) is False
        partitions.convert_to_partitioned(cursor)  # already partitioned: a no-op
        assert partitions.is_partitioned(cursor)
