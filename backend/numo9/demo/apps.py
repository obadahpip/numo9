from django.apps import AppConfig


class DemoConfig(AppConfig):
    """Demo organisations (U-07): seeded sample data, template cloning, reset, exclusions, purge."""

    name = "numo9.demo"
    label = "demo"
    verbose_name = "Demo organisations"

    def ready(self) -> None:
        from numo9.documents.pdf import register_watermark

        from . import phase0  # noqa: F401 — registers the Phase 0 seeders
        from .watermark import demo_watermark

        register_watermark(demo_watermark)
