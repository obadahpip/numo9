"""``ledger_journalline`` becomes a parent hash-partitioned by organisation into 16 partitions
(C-02-T03, ADR-0003 §5).

Rows, defaults, constraint and index names, the ``id`` sequence, the append-only trigger and the
organisation RLS policy are kept (``numo9.partitioning``); the trigger and the policy apply to every
partition. PostgreSQL only; not reversible (a reverse would rebuild the table again, which no
release needs).
"""

from typing import Any

from django.db import migrations


def forwards(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    from numo9.ledger.partitions import convert_to_partitioned

    with schema_editor.connection.cursor() as cursor:
        convert_to_partitioned(cursor)


class Migration(migrations.Migration):
    dependencies = [("ledger", "0005_journal_sequence")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop, elidable=False)]
