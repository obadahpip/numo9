"""Install the Canadian sales-tax table (G-01-T04) for every organisation that exists already.

New organisations get it when their chart is loaded (``numo9.tax.seed.on_chart_loaded``) or
when codes are first read (``ensure_tax_table``). Rolling back removes the installed rows."""

from typing import Any

from django.db import migrations


def install(apps: Any, schema_editor: Any) -> None:
    from numo9.tax.seed import install_tax_table

    class Historical:
        TaxAuthority = apps.get_model("tax", "TaxAuthority")
        TaxComponent = apps.get_model("tax", "TaxComponent")
        TaxCode = apps.get_model("tax", "TaxCode")
        TaxCodeComponent = apps.get_model("tax", "TaxCodeComponent")
        Account = apps.get_model("ledger", "Account")

    Organisation = apps.get_model("tenancy", "Organisation")
    for organisation in Organisation.objects.all().iterator():
        install_tax_table(organisation, models=Historical)


def remove(apps: Any, schema_editor: Any) -> None:
    for name in ("TaxCodeComponent", "TaxCode", "TaxComponent", "TaxAuthority"):
        apps.get_model("tax", name)._base_manager.all().delete()


class Migration(migrations.Migration):
    dependencies = [("tax", "0002_tax_code")]

    operations = [migrations.RunPython(install, remove)]
