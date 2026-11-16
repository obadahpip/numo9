from django.apps import AppConfig


class ImportsConfig(AppConfig):
    """Spreadsheet import framework (B-03): file parser, saved column mappings with auto-suggest.

    Used by the contacts import (B-03) and the chart-of-accounts import/export (C-01-T13).
    """

    name = "numo9.imports"
    label = "imports"
    verbose_name = "Imports"
