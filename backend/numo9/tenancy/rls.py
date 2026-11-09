"""PostgreSQL row-level security for organisation-owned tables (A-01-T12).

Defence in depth under ``OrgScopedManager``: even raw SQL, a forgotten filter or an
``unscoped()`` query cannot read or write another organisation's rows in an RLS table.

Two parts:

1. ``EnableOrgRLS(table)`` — migration operation that enables and **forces** RLS on a table with
   an ``organisation_id`` column and adds the policy ``org_isolation``: a row is visible and
   writable only when ``organisation_id`` equals the ``app.current_org`` setting. With the
   setting empty (no organisation active) the table returns no rows. No-op on other databases.
2. ``set_current_org_guc`` — database execute wrapper (installed on every connection by
   ``TenancyConfig.ready``) that sets ``app.current_org`` to ``current_org()``
   transaction-locally (``set_config(..., true)``) before every statement. Inside a transaction
   it is set again before each statement, so savepoint rollbacks or a change of organisation
   mid-transaction can never leave a stale value; outside a transaction the statement runs in a
   short transaction together with the setting.

Deployment requirement: PostgreSQL superusers and roles with ``BYPASSRLS`` ignore all policies.
The application must connect as an ordinary role (set up with the server, S-02-T04/T06); the
tests prove the policies with such a role. Cross-organisation platform jobs that must read RLS
tables run under a separate role with ``BYPASSRLS``.

Tables get RLS in their own migration as they are created. The five sensitive tables the plan
targets are the contact (B-01), employee with SIN/bank details (M-01), bank account and bank
transaction (F), and journal line (C-02) tables; each of those tasks adds ``EnableOrgRLS``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import ProjectState

from .context import current_org

GUC = "app.current_org"
POLICY = "org_isolation"
# Transaction-control statements run as they are (e.g. ROLLBACK TO SAVEPOINT after an error).
_TRANSACTION_CONTROL = ("SAVEPOINT", "RELEASE", "ROLLBACK", "COMMIT", "BEGIN", "START")


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class EnableOrgRLS(migrations.operations.base.Operation):
    reversible = True
    reduces_to_sql = True

    def __init__(self, table: str) -> None:
        self.table = table

    def deconstruct(self) -> tuple[str, list[Any], dict[str, Any]]:
        return (f"{type(self).__module__}.{type(self).__name__}", [self.table], {})

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        pass  # no change to the model state

    def _run(self, schema_editor: BaseDatabaseSchemaEditor, statements: list[str]) -> None:
        if schema_editor.connection.vendor != "postgresql":
            return
        for sql in statements:
            schema_editor.execute(sql)

    def forward_sql(self) -> list[str]:
        t = _quote(self.table)
        condition = f"organisation_id = NULLIF(current_setting('{GUC}', true), '')::bigint"
        return [
            f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY",
            f"CREATE POLICY {POLICY} ON {t} USING ({condition}) WITH CHECK ({condition})",
        ]

    def backward_sql(self) -> list[str]:
        t = _quote(self.table)
        return [
            f"DROP POLICY IF EXISTS {POLICY} ON {t}",
            f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY",
            f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY",
        ]

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        self._run(schema_editor, self.forward_sql())

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        self._run(schema_editor, self.backward_sql())

    def describe(self) -> str:
        return f"Enable organisation row-level security on {self.table}"

    @property
    def migration_name_fragment(self) -> str:
        return f"rls_{self.table}"


def set_current_org_guc(
    execute: Callable[..., Any], sql: str, params: Any, many: bool, context: dict[str, Any]
) -> Any:
    """Execute wrapper: run every statement with ``app.current_org`` = the active organisation."""
    connection = context["connection"]
    if sql.lstrip()[:16].upper().startswith(_TRANSACTION_CONTROL):
        return execute(sql, params, many, context)
    organisation = current_org()
    value = str(organisation.pk) if organisation is not None else ""
    raw_cursor = context["cursor"].cursor

    def set_guc() -> None:
        raw_cursor.execute("SELECT set_config(%s, %s, true)", [GUC, value])

    if connection.in_atomic_block:
        set_guc()
        return execute(sql, params, many, context)
    if not value:
        return execute(sql, params, many, context)  # fresh transaction: setting is empty
    with transaction.atomic(using=connection.alias):
        set_guc()
        return execute(sql, params, many, context)


def install_guc_wrapper(sender: Any, connection: Any, **kwargs: Any) -> None:
    """``connection_created`` receiver: add the wrapper to PostgreSQL connections."""
    if connection.vendor == "postgresql" and set_current_org_guc not in connection.execute_wrappers:
        connection.execute_wrappers.append(set_current_org_guc)
