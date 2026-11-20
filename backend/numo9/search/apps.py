from django.apps import AppConfig


class SearchConfig(AppConfig):
    """Global search and quick-create (A-09): one index of every record type of an organisation."""

    name = "numo9.search"
    label = "search"
    verbose_name = "Global search"

    def ready(self) -> None:
        from django.contrib.postgres.lookups import TrigramStrictWordSimilar
        from django.db import models

        from .providers import register_phase0_providers

        # ``title__trigram_strict_word_similar`` (``<<%``, served by the trigram GIN index)
        # without installing the whole django.contrib.postgres app.
        models.CharField.register_lookup(TrigramStrictWordSimilar)

        register_phase0_providers()
