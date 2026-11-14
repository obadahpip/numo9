"""Seed the CRA GIFI list, RC4088(E) Rev. 23 (C-01-T04)."""

from typing import Any

from django.db import migrations


def seed(apps: Any, schema_editor: Any) -> None:
    from numo9.ledger.gifi import seed_gifi

    seed_gifi(apps, missing_only=True)


class Migration(migrations.Migration):
    dependencies = [("ledger", "0001_initial")]

    # Reverse: nothing to undo (0001 drops the table when unapplied further).
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
