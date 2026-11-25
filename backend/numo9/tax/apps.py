from typing import Any

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

        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["tax.TaxCode"] = _sweep_code
        SWEEP_FACTORIES["tax.TaxComponent"] = _sweep_component
        SWEEP_FACTORIES["tax.TaxSettings"] = _sweep_settings

        from numo9.ledger import services as ledger

        from .returns import tax_lock_guard

        if tax_lock_guard not in ledger.POSTING_GUARDS:
            ledger.POSTING_GUARDS.append(tax_lock_guard)  # the Tax lock on postings (G-03-T07)

        from .history import register_history

        register_history()  # one attributed history of every tax object (G-06-T06)


def _sweep_code(organisation: Any) -> Any:
    from .models import TaxCode
    from .seed import ensure_tax_table

    ensure_tax_table(organisation)
    return TaxCode._base_manager.filter(organisation=organisation, code="sales.ON.standard").first()


def _sweep_component(organisation: Any) -> Any:
    from .models import TaxComponent
    from .seed import ensure_tax_table

    ensure_tax_table(organisation)
    return TaxComponent._base_manager.filter(organisation=organisation, key="gst").first()


def _sweep_settings(organisation: Any) -> Any:
    from .settings import tax_settings

    return tax_settings(organisation)
