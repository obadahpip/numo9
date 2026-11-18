from django.apps import AppConfig


class BulkConfig(AppConfig):
    """Bulk edit and bulk actions on a practice's organisations (V-03): preview, background
    job with one outcome per organisation, results."""

    name = "numo9.bulk"
    label = "bulk"
    verbose_name = "Bulk actions"
