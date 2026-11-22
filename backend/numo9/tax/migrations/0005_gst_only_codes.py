"""Add the GST-only sales codes (``sales.BC.gst``, ``sales.MB.gst``, ``sales.SK.gst``,
``sales.QC.gst``, G-02-T02) to organisations whose table was installed before them: what the
place-of-supply resolver picks when the organisation isn't registered for the provincial tax."""

from typing import Any

from django.db import migrations

KEYS = ("sales.BC.gst", "sales.MB.gst", "sales.SK.gst", "sales.QC.gst")


def add(apps: Any, schema_editor: Any) -> None:
    from numo9.tax.seed import install_missing_codes

    class Historical:
        TaxAuthority = apps.get_model("tax", "TaxAuthority")
        TaxComponent = apps.get_model("tax", "TaxComponent")
        TaxCode = apps.get_model("tax", "TaxCode")
        TaxCodeComponent = apps.get_model("tax", "TaxCodeComponent")

    Organisation = apps.get_model("tenancy", "Organisation")
    for organisation in Organisation.objects.all().iterator():
        install_missing_codes(organisation, models=Historical)


def remove(apps: Any, schema_editor: Any) -> None:
    TaxCode = apps.get_model("tax", "TaxCode")
    TaxCodeComponent = apps.get_model("tax", "TaxCodeComponent")
    TaxCodeComponent._base_manager.filter(tax_code__code__in=KEYS).delete()
    TaxCode._base_manager.filter(code__in=KEYS).delete()


class Migration(migrations.Migration):
    dependencies = [("tax", "0004_code_itc_restriction")]

    operations = [migrations.RunPython(add, remove)]
