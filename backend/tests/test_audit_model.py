"""AuditEvent table (A-04-T01).

Acceptance: the migration applies — the ``audit_event`` table exists with every column the plan
lists and is partition-ready (primary key includes ``created_at``; no other unique constraint;
nothing references it).
"""

from __future__ import annotations

import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from numo9.accounts.models import User
from numo9.audit.models import ActorKind, AuditEvent, AuditImmutable
from numo9.tenancy.context import TenantContextMissing, org_context
from numo9.tenancy.models import Organisation, Practice

pytestmark = pytest.mark.django_db

PLAN_COLUMNS = {
    "organisation_id",
    "actor_user_id",
    "actor_kind",
    "impersonator_id",
    "action",
    "object_type",
    "object_id",
    "changes",
    "ip",
    "user_agent",
    "request_id",
    "batch_id",
    "created_at",
    "prev_hash",
    "hash",
}


def _org(name: str = "Maple Leaf Supply Ltd.") -> Organisation:
    return Organisation.objects.create(name=name)


def _event(org: Organisation | None, **fields: object) -> AuditEvent:
    values: dict[str, object] = {"action": "tests.widget.updated", "organisation": org}
    values.update(fields)
    event: AuditEvent = AuditEvent.platform_events.create(**values)
    return event


def _columns() -> dict[str, tuple[str, str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'audit_event'"
        )
        return {name: (kind, nullable) for name, kind, nullable in cursor.fetchall()}


# ---- the migration ---------------------------------------------------------------------------


def test_table_has_every_planned_column() -> None:
    columns = _columns()
    assert set(columns) >= PLAN_COLUMNS
    assert columns["changes"][0] == "jsonb"
    assert columns["meta"][0] == "jsonb"
    assert columns["ip"][0] == "inet"
    assert columns["created_at"] == ("timestamp with time zone", "NO")
    # Platform and practice events have no organisation.
    assert columns["organisation_id"][1] == "YES"


def test_primary_key_is_created_at_and_id_from_the_sequence() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.attname FROM pg_index i JOIN pg_attribute a "
            "ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = 'audit_event'::regclass AND i.indisprimary "
            "ORDER BY array_position(i.indkey, a.attnum)"
        )
        assert [row[0] for row in cursor.fetchall()] == ["created_at", "id"]
        cursor.execute("SELECT pg_get_serial_sequence('audit_event', 'id')")
        assert cursor.fetchone()[0] == "public.audit_event_id_seq"


def test_partition_ready_no_unique_constraint_without_created_at_and_no_references() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT i.indexrelid::regclass::text FROM pg_index i "
            "WHERE i.indrelid = 'audit_event'::regclass AND i.indisunique AND NOT EXISTS ("
            "  SELECT 1 FROM pg_attribute a WHERE a.attrelid = i.indrelid "
            "  AND a.attnum = ANY(i.indkey) AND a.attname = 'created_at')"
        )
        assert cursor.fetchall() == []
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE contype = 'f' "
            "AND confrelid = 'audit_event'::regclass"
        )
        assert cursor.fetchall() == []


# ---- rows ------------------------------------------------------------------------------------


def test_event_gets_increasing_ids_a_public_id_and_its_time() -> None:
    org = _org()
    before = timezone.now()
    first, second = _event(org), _event(org)
    assert isinstance(first.id, int) and second.id > first.id
    assert isinstance(first.public_id, uuid.UUID) and first.public_id != second.public_id
    assert before <= first.created_at <= timezone.now()
    stored = AuditEvent.platform_events.get(public_id=first.public_id)
    assert stored.pk == (first.created_at, first.id)


def test_every_field_round_trips() -> None:
    org = _org()
    user = User.objects.create_user("ines@example.com", name="Inès Tremblay")
    batch = uuid.uuid4()
    event = _event(
        org,
        actor_kind=ActorKind.USER,
        actor_user=user,
        actor_label="Inès Tremblay (ines@example.com)",
        object_type="tests.Widget",
        object_id=str(uuid.uuid4()),
        object_label="Widget A",
        changes={"amount": ["100.00", "120.00"]},
        meta={"source": "test"},
        ip="203.0.113.7",
        user_agent="Mozilla/5.0",
        request_id="req-1",
        batch_id=batch,
    )
    stored = AuditEvent.platform_events.get(public_id=event.public_id)
    assert stored.changes == {"amount": ["100.00", "120.00"]}
    assert stored.actor_user == user and stored.batch_id == batch and stored.ip == "203.0.113.7"


def test_platform_and_practice_events_have_no_organisation() -> None:
    practice = Practice.objects.create(name="Lakeshore CPA")
    platform = _event(None, action="auth.login.failed")
    in_practice = _event(None, practice=practice, action="tenancy.invitation.created")
    assert platform.organisation_id is None and in_practice.practice == practice


def test_impersonation_must_name_both_people() -> None:
    org = _org()
    with pytest.raises(IntegrityError), transaction.atomic():
        _event(org, actor_kind=ActorKind.IMPERSONATION)


def test_unknown_actor_kind_is_refused() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        _event(_org(), actor_kind="robot")


# ---- tenancy ---------------------------------------------------------------------------------


def test_objects_is_organisation_scoped() -> None:
    org1, org2 = _org("North Ltd."), _org("South Ltd.")
    mine = _event(org1)
    _event(org2)
    _event(None)
    with pytest.raises(TenantContextMissing):
        list(AuditEvent.objects.all())
    with org_context(org1):
        assert list(AuditEvent.objects.values_list("public_id", flat=True)) == [mine.public_id]


# ---- the model refuses changes (the database does too, A-04-T02) ------------------------------


def test_saved_event_cannot_be_saved_again_or_deleted() -> None:
    event = _event(_org())
    event.action = "tests.widget.deleted"
    with pytest.raises(AuditImmutable):
        event.save()
    with pytest.raises(AuditImmutable):
        event.delete()
    with pytest.raises(AuditImmutable):
        event.soft_delete()
    assert AuditEvent.platform_events.get(public_id=event.public_id).action == (
        "tests.widget.updated"
    )
