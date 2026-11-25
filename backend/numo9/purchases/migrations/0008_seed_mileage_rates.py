"""Seed the CRA per-kilometre allowance rates 2022–2026 (E-04-T02)."""

from typing import Any

from django.db import migrations


def seed(apps: Any, schema_editor: Any) -> None:
    from numo9.purchases.mileage import seed_mileage_rates

    seed_mileage_rates(apps.get_model("purchases", "MileageRate"))


class Migration(migrations.Migration):
    dependencies = [("purchases", "0007_mileage_rate")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
