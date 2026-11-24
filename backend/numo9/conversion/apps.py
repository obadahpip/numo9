from django.apps import AppConfig


class ConversionConfig(AppConfig):
    """Conversion balances (C-05): the opening trial balance and open documents of an
    organisation moving to Numo9 at its conversion date."""

    name = "numo9.conversion"
    label = "conversion"
    verbose_name = "Conversion balances"
