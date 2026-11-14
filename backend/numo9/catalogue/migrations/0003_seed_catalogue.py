"""Seed the product catalogue (U-01-T04): 7 products, 3 planned companion apps and the Phase 0–1
feature keys (accounting.*, tax.*, practice.*, portal.*).

The data is frozen here on purpose: later phases add their keys (payroll.*, inventory.*,
finance.*, hr.*…) with their own data migration. ``seed`` is idempotent — products are matched by
code and keys by key, so running it twice leaves the same rows (tests/test_catalogue_seed.py).
After every ``migrate`` / ``flush`` the app re-creates missing seed rows (``missing_only``: rows
the Platform Owner changed are left alone) — CatalogueConfig.ready.
Display texts live in numo9/catalogue/texts.py under the i18n keys written here.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

#: code, kind, status, sort
PRODUCTS: tuple[tuple[str, str, str, int], ...] = (
    ("accounting", "main", "active", 10),
    ("tax", "main", "active", 20),
    ("payroll", "main", "active", 30),
    ("inventory", "main", "active", 40),
    ("finance", "main", "active", 50),
    ("practice", "free_set", "active", 60),
    ("portal", "free_set", "active", 70),
    ("app.commerce", "companion", "planned", 100),
    ("app.bank", "companion", "planned", 110),
    ("app.receipts", "companion", "planned", 120),
)

#: (product, area, actions) in screen order. Projects, expense claims and document capture are
#: part of Accounting — never paid add-ons (gap 51).
FEATURES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("accounting", "contacts", ("read", "write")),
    ("accounting", "chart_of_accounts", ("read", "write")),
    ("accounting", "journals", ("read", "write", "approve")),
    ("accounting", "documents", ("read", "write")),
    ("accounting", "sales_quotes", ("read", "write")),
    ("accounting", "sales_invoices", ("read", "write", "approve")),
    ("accounting", "credit_notes", ("read", "write")),
    ("accounting", "invoice_reminders", ("read", "write")),
    ("accounting", "payments_received", ("read", "write")),
    ("accounting", "purchase_orders", ("read", "write", "approve")),
    ("accounting", "bills", ("read", "write", "approve")),
    ("accounting", "expense_claims", ("read", "write", "approve")),
    ("accounting", "banking", ("read", "write")),
    ("accounting", "projects", ("read", "write")),
    ("accounting", "multi_currency", ("read", "write")),
    ("accounting", "conversion_balances", ("read", "write")),
    ("accounting", "period_close", ("read", "write")),
    ("accounting", "recode", ("write",)),
    ("accounting", "reports", ("read",)),
    ("accounting", "assurance", ("read",)),
    ("tax", "codes", ("read", "write")),
    ("tax", "returns", ("read", "write", "approve")),
    ("tax", "reports", ("read",)),
    ("practice", "directory", ("read",)),
    ("practice", "groups", ("read", "write")),
    ("practice", "bulk_actions", ("write",)),
    ("practice", "dashboards", ("read",)),
    ("practice", "staff", ("read", "write")),
    ("portal", "documents", ("read", "write")),
    ("portal", "requests", ("read", "write")),
)


def seed(apps: Any, schema_editor: Any = None, *, missing_only: bool = False) -> None:
    """Create (``missing_only``) or create-and-reset the seeded rows."""
    Product = apps.get_model("catalogue", "Product")
    FeatureKey = apps.get_model("catalogue", "FeatureKey")
    products = {}
    for code, kind, status, sort in PRODUCTS:
        write = Product.objects.get_or_create if missing_only else Product.objects.update_or_create
        products[code], _ = write(
            code=code,
            defaults={
                "name_i18n_key": f"catalogue.product.{code}",
                "kind": kind,
                "status": status,
                "sort": sort,
            },
        )
    position = 0
    for code, area, actions in FEATURES:
        for action in actions:
            position += 10
            key = f"{code}.{area}.{action}"
            write_key = (
                FeatureKey.objects.get_or_create
                if missing_only
                else FeatureKey.objects.update_or_create
            )
            write_key(
                key=key,
                defaults={
                    "product": products[code],
                    "description_i18n_key": f"catalogue.feature.{key}",
                    "is_read_only": action == "read",
                    "sort": position,
                },
            )


class Migration(migrations.Migration):
    dependencies = [("catalogue", "0002_feature_key")]

    # Reverse: nothing to undo (0002/0001 drop the tables when unapplied further).
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
