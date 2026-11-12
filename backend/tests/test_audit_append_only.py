"""The database refuses UPDATE and DELETE on the audit log (A-04-T02).

Acceptance: an UPDATE (raw SQL) raises. Proven three ways: as the test database's owner (a
superuser, which ignores privileges — the trigger stops it), through the ORM's bulk ``update()``
and ``delete()`` (which skip the model's own refusal), and as ordinary roles: one with only the
application's privileges (refused by the revoked privilege) and one granted everything by mistake
(still refused by the trigger).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import DatabaseError, connection, transaction

from numo9.audit.models import AuditEvent
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def event() -> AuditEvent:
    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    stored: AuditEvent = AuditEvent.platform_events.create(
        organisation=org, action="tests.widget.updated", changes={"amount": ["1.00", "2.00"]}
    )
    return stored


def sql(statement: str, params: list[Any] | None = None) -> None:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)


def refused(statement: str, params: list[Any] | None = None) -> str:
    """Run a statement that must fail; return the database's message (savepoint rolled back)."""
    with pytest.raises(DatabaseError) as caught, transaction.atomic():
        sql(statement, params)
    return str(caught.value)


def unchanged(event: AuditEvent) -> None:
    stored = AuditEvent.platform_events.get(public_id=event.public_id)
    assert stored.action == "tests.widget.updated"
    assert stored.changes == {"amount": ["1.00", "2.00"]}


# ---- trigger --------------------------------------------------------------------------------


def test_raw_update_raises(event: AuditEvent) -> None:
    message = refused(
        "UPDATE audit_event SET changes = '{}'::jsonb WHERE public_id = %s", [event.public_id]
    )
    assert "append-only" in message and "UPDATE" in message
    unchanged(event)


def test_raw_delete_raises(event: AuditEvent) -> None:
    message = refused("DELETE FROM audit_event WHERE public_id = %s", [event.public_id])
    assert "append-only" in message and "DELETE" in message
    unchanged(event)


def test_orm_bulk_update_and_delete_raise(event: AuditEvent) -> None:
    rows = AuditEvent.platform_events.filter(public_id=event.public_id)
    with pytest.raises(DatabaseError), transaction.atomic():
        rows.update(action="tests.widget.deleted")
    with pytest.raises(DatabaseError), transaction.atomic():
        rows.delete()
    unchanged(event)


def test_insert_still_works(event: AuditEvent) -> None:
    sql(
        "INSERT INTO audit_event (created_at, public_id, organisation_id, actor_kind, "
        "actor_label, action, object_type, object_id, object_label, changes, meta, user_agent, "
        "request_id, prev_hash, hash) VALUES (now(), %s, %s, 'system', '', 'tests.raw', '', '', "
        "'', '{}', '{}', '', '', '', '')",
        [uuid.uuid4(), event.organisation_id],
    )
    assert AuditEvent.platform_events.filter(action="tests.raw").count() == 1


# ---- privileges -----------------------------------------------------------------------------


def test_owner_privileges_exclude_update_delete_truncate() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.privilege_type FROM pg_class c, aclexplode(c.relacl) a "
            "WHERE c.relname = 'audit_event' AND a.grantee = c.relowner"
        )
        privileges = {row[0] for row in cursor.fetchall()}
    assert {"INSERT", "SELECT"} <= privileges
    assert not privileges & {"UPDATE", "DELETE", "TRUNCATE"}


@pytest.fixture
def ordinary_role() -> Iterator[str]:
    """An ordinary role (no superuser) for the rest of this test's transaction."""
    role = f"numo9_audit_probe_{uuid.uuid4().hex[:8]}"
    sql(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
    sql(f"GRANT USAGE ON SCHEMA public TO {role}")
    yield role
    sql("RESET ROLE")


def test_role_with_application_privileges_is_refused_by_the_privilege(
    event: AuditEvent, ordinary_role: str
) -> None:
    sql(f"GRANT SELECT, INSERT ON audit_event TO {ordinary_role}")
    sql(f"SET LOCAL ROLE {ordinary_role}")
    message = refused("UPDATE audit_event SET action = 'x' WHERE public_id = %s", [event.public_id])
    assert "permission denied" in message
    message = refused("DELETE FROM audit_event WHERE public_id = %s", [event.public_id])
    assert "permission denied" in message
    sql("RESET ROLE")
    unchanged(event)


def test_role_granted_everything_is_still_refused_by_the_trigger(
    event: AuditEvent, ordinary_role: str
) -> None:
    sql(f"GRANT ALL ON audit_event TO {ordinary_role}")
    sql(f"SET LOCAL ROLE {ordinary_role}")
    message = refused("UPDATE audit_event SET action = 'x' WHERE public_id = %s", [event.public_id])
    assert "append-only" in message
    message = refused("DELETE FROM audit_event WHERE public_id = %s", [event.public_id])
    assert "append-only" in message
    sql("RESET ROLE")
    unchanged(event)
