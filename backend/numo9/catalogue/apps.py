from typing import Any

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CatalogueConfig(AppConfig):
    """Product catalogue and feature keys (U-01)."""

    name = "numo9.catalogue"
    label = "catalogue"
    verbose_name = "Product catalogue"

    def ready(self) -> None:
        # Seeded products and keys exist after every migrate and flush (test databases are
        # flushed between transactional tests): missing rows are created, changed ones kept.
        post_migrate.connect(_seed_after_migrate, sender=self)


def _seed_after_migrate(sender: AppConfig, **kwargs: Any) -> None:
    import importlib

    from django.apps import apps as global_apps

    seed = importlib.import_module("numo9.catalogue.migrations.0003_seed_catalogue").seed
    # The migration state's (historical) models, like the data migration itself: seeding is not
    # an audited change (U-01-T14 audits changes made to the catalogue afterwards).
    seed(kwargs.get("apps") or global_apps, missing_only=True)
