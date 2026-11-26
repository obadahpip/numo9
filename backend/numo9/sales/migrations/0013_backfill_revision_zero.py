"""D-03b-T03 — revision 0 for every posted invoice approved before revisions existed."""

from django.db import migrations


def forwards(apps, schema_editor):  # type: ignore[no-untyped-def]
    from numo9.sales.revisions import backfill_revision_zero

    backfill_revision_zero(apps)


class Migration(migrations.Migration):
    dependencies = [("sales", "0012_invoice_revision_fields")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop, elidable=True)]
