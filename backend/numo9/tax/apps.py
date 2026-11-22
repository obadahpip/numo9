from django.apps import AppConfig


class TaxConfig(AppConfig):
    """Tax engine (G): effective-dated Canadian sales-tax components and codes that every
    document calculates from (G-01), place-of-supply defaulting (G-02)."""

    name = "numo9.tax"
    label = "tax"
    verbose_name = "Sales tax"
