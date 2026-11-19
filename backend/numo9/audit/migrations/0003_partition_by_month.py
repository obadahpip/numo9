"""``audit_event`` becomes a parent partitioned by month on ``created_at`` (S-06-T03, ADR-0005).

Rows, column defaults, constraint and index names, the ``id`` sequence, the append-only trigger and
privileges are kept (``numo9.audit.partitions.convert_to_partitioned``). With pg_partman installed
in the database the parent is registered with it; otherwise the same monthly children are created
with plain DDL. PostgreSQL only; the reverse migration is not supported (it would have to delete
from an append-only table).
"""

from typing import Any

from django.db import migrations


def forwards(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    from numo9.audit.partitions import convert_to_partitioned

    with schema_editor.connection.cursor() as cursor:
        convert_to_partitioned(cursor)


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_append_only")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop, elidable=False)]
