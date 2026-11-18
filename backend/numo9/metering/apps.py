from django.apps import AppConfig


class MeteringConfig(AppConfig):
    """Usage metering (S-06-T07): ``meter(org, key, qty)`` events through a Redis stream, summed
    into daily aggregates per organisation and key."""

    name = "numo9.metering"
    label = "metering"
    verbose_name = "Usage metering"
