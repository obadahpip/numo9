from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """Reports (K-01): one engine for every financial, tax and operational report — definitions
    in a registry, parameters, ledger aggregation, drill-down, header, layouts and notes."""

    name = "numo9.reports"
    label = "reports"
    verbose_name = "Reports"

    def ready(self) -> None:
        from . import cashflow, standard, statements  # noqa: F401 — registers the standard reports
