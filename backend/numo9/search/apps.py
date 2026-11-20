from django.apps import AppConfig


class SearchConfig(AppConfig):
    """Global search and quick-create (A-09): one index of every record type of an organisation."""

    name = "numo9.search"
    label = "search"
    verbose_name = "Global search"
