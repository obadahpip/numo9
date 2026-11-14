"""Migration helper: constraints only PostgreSQL has (U-02-T03).

The price-overlap rule is a btree_gist exclusion constraint — a PostgreSQL feature.
``PostgresOnlyAddConstraint`` adds it on PostgreSQL and does nothing elsewhere (the migration
state still has it, so ``makemigrations --check`` stays clean), so a throw-away SQLite database
(CI jobs that only start the app, e.g. the security-header grader) can still be migrated — as
``numo9.audit.pg.PostgresOnly`` does for raw SQL.
"""

from __future__ import annotations

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import ProjectState


class PostgresOnlyAddConstraint(migrations.AddConstraint):
    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)
