"""A-01-T12 — PostgreSQL row-level security: with app.current_org unset, raw SQL on an RLS table
returns no rows; with it set (transaction-locally, by the execute wrapper) only that
organisation's rows are visible or writable. Proven as an ordinary database role — superusers
bypass RLS."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from django.db import DatabaseError, connection, transaction

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from numo9.tenancy.rls import GUC, POLICY, EnableOrgRLS
from tests.testapp.models import Gadget, Widget

postgres_only = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="row-level security is PostgreSQL-only"
)
pytestmark = [pytest.mark.tenant_isolation]


def sql(query: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        return list(cursor.fetchall()) if cursor.description else []


@pytest.fixture
def orgs() -> tuple[Organisation, Organisation]:
    a = Organisation.objects.create(name="Maple Bakery")
    b = Organisation.objects.create(name="Birch Garage")
    for org, labels in ((a, ["a1", "a2"]), (b, ["b1"])):
        with org_context(org):
            for label in labels:
                Widget.objects.create(label=label)
                Gadget.objects.create(label=label)
    return a, b


@pytest.fixture
def app_role(orgs: tuple[Organisation, Organisation]) -> Iterator[None]:
    """Switch this test's transaction to an ordinary role (no superuser, no BYPASSRLS)."""
    role = f"numo9_rls_probe_{uuid.uuid4().hex[:8]}"
    sql(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
    sql(f"GRANT USAGE ON SCHEMA public TO {role}")
    sql(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
    sql(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
    sql(f"SET LOCAL ROLE {role}")
    yield
    sql("RESET ROLE")


def labels(table: str) -> list[str]:
    return sorted(row[0] for row in sql(f"SELECT label FROM {table}"))  # noqa: S608


@postgres_only
@pytest.mark.django_db
def test_migration_enabled_and_forced_rls_on_the_widget_table() -> None:
    flags = sql(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
        ["testapp_widget"],
    )
    assert flags == [(True, True)]
    policies = sql("SELECT policyname FROM pg_policies WHERE tablename = 'testapp_widget'")
    assert policies == [(POLICY,)]


@postgres_only
@pytest.mark.django_db
def test_raw_sql_without_guc_returns_no_rows(app_role: None) -> None:
    assert sql("SELECT current_setting(%s, true)", [GUC])[0][0] in ("", None)
    assert sql("SELECT count(*) FROM testapp_widget") == [(0,)]
    assert labels("testapp_gadget") == ["a1", "a2", "b1"]  # table without RLS


@postgres_only
@pytest.mark.django_db
def test_raw_sql_sees_only_the_active_organisation(
    orgs: tuple[Organisation, Organisation], app_role: None
) -> None:
    a, b = orgs
    with org_context(a):
        assert labels("testapp_widget") == ["a1", "a2"]
    with org_context(b):
        assert labels("testapp_widget") == ["b1"]
    assert labels("testapp_widget") == []


@postgres_only
@pytest.mark.django_db
def test_unscoped_orm_query_is_still_limited_by_rls(
    orgs: tuple[Organisation, Organisation], app_role: None
) -> None:
    a, _ = orgs
    reason = "test: RLS under unscoped()"
    with org_context(a):
        assert sorted(Widget.objects.unscoped(reason=reason).values_list("label", flat=True)) == [
            "a1",
            "a2",
        ]
        assert Gadget.objects.unscoped(reason=reason).count() == 3  # table without RLS
    assert Widget.objects.unscoped(reason=reason).count() == 0


@postgres_only
@pytest.mark.django_db
def test_writes_to_another_organisation_are_refused(
    orgs: tuple[Organisation, Organisation], app_role: None
) -> None:
    a, b = orgs
    with org_context(a):
        updated = sql("UPDATE testapp_widget SET label = label || '!' RETURNING label")
        assert sorted(row[0] for row in updated) == ["a1!", "a2!"]
        with pytest.raises(DatabaseError, match="row-level security"), transaction.atomic():
            sql(
                "INSERT INTO testapp_widget (organisation_id, public_id, label, created_at,"
                " updated_at) VALUES (%s, %s, 'x', now(), now())",
                [b.pk, uuid.uuid4()],
            )
        assert sql("DELETE FROM testapp_widget WHERE organisation_id = %s", [b.pk]) == []
    with org_context(b):
        assert labels("testapp_widget") == ["b1"]  # untouched


@postgres_only
@pytest.mark.django_db
def test_guc_follows_the_context_inside_a_transaction(
    orgs: tuple[Organisation, Organisation],
) -> None:
    a, b = orgs
    current = "SELECT current_setting('app.current_org', true)"
    with transaction.atomic():
        with org_context(a):
            assert sql(current) == [(str(a.pk),)]
            try:
                with transaction.atomic(), org_context(b):
                    assert sql(current) == [(str(b.pk),)]
                    raise RuntimeError
            except RuntimeError:
                pass
            assert sql(current) == [(str(a.pk),)]  # savepoint rollback cannot leave b behind
        assert sql(current)[0][0] in ("", None)


@postgres_only
@pytest.mark.django_db(transaction=True)
def test_guc_in_autocommit_is_per_statement() -> None:
    org = Organisation.objects.create(name="Autocommit Org")
    current = "SELECT current_setting('app.current_org', true)"
    assert not connection.in_atomic_block
    with org_context(org):
        assert sql(current) == [(str(org.pk),)]
    assert sql(current)[0][0] in ("", None)  # transaction-local: nothing left on the connection


@postgres_only
@pytest.mark.django_db
def test_operation_is_reversible() -> None:
    op = EnableOrgRLS("testapp_gadget")
    flags = "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s"
    with connection.schema_editor() as editor:
        op.database_forwards("testapp", editor, None, None)  # type: ignore[arg-type]
    assert sql(flags, ["testapp_gadget"]) == [(True, True)]
    with connection.schema_editor() as editor:
        op.database_backwards("testapp", editor, None, None)  # type: ignore[arg-type]
    assert sql(flags, ["testapp_gadget"]) == [(False, False)]
    assert sql("SELECT 1 FROM pg_policies WHERE tablename = 'testapp_gadget'") == []


def test_operation_is_a_no_op_on_other_databases() -> None:
    executed: list[str] = []
    editor = SimpleNamespace(connection=SimpleNamespace(vendor="sqlite"), execute=executed.append)
    EnableOrgRLS("testapp_widget").database_forwards("testapp", editor, None, None)  # type: ignore[arg-type]
    assert executed == []
    assert EnableOrgRLS("t").deconstruct() == ("numo9.tenancy.rls.EnableOrgRLS", ["t"], {})
