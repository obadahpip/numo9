from django.apps import AppConfig


class SearchConfig(AppConfig):
    """Global search and quick-create (A-09): one index of every record type of an organisation."""

    name = "numo9.search"
    label = "search"
    verbose_name = "Global search"

    def ready(self) -> None:
        from .providers import register_phase0_providers

        register_phase0_providers()
