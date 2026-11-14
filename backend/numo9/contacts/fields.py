"""``ArrayField`` that a throw-away SQLite database can still create (B-01-T02).

Contact roles are a PostgreSQL array (``varchar[]``) with array constraints and lookups.
CI jobs that only start the app on SQLite (the security-header grader) run every migration;
SQLite has no array type, so there the column is created as plain ``text`` — the same approach as
``numo9.audit.pg.PostgresOnly`` and ``numo9.packages.pg.PostgresOnlyAddConstraint``. Contacts are
only stored on PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from django.contrib.postgres.fields import ArrayField


class PortableArrayField(ArrayField):  # type: ignore[type-arg]
    def db_type(self, connection: Any) -> str | None:
        if connection.vendor != "postgresql":
            return "text"
        return super().db_type(connection)

    def cast_db_type(self, connection: Any) -> str:
        if connection.vendor != "postgresql":
            return "text"
        return super().cast_db_type(connection)
