from django.apps import AppConfig


class TaxConfig(AppConfig):
    """Tax engine (G): effective-dated Canadian sales-tax components and codes that every
    document calculates from (G-01), place-of-supply defaulting (G-02)."""

    name = "numo9.tax"
    label = "tax"
    verbose_name = "Sales tax"

    def ready(self) -> None:
        from numo9.ledger.template import CHART_LOADED

        from .seed import on_chart_loaded

        if on_chart_loaded not in CHART_LOADED:
            CHART_LOADED.append(on_chart_loaded)  # install the tax table with the chart (G-01-T04)
