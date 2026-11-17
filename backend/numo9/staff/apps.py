from django.apps import AppConfig


class StaffConfig(AppConfig):
    """Practice staff management (V-05): staff list, assignments, suspend/remove, dormant
    alerts, activity from the audit log."""

    name = "numo9.staff"
    label = "staff"
    verbose_name = "Practice staff"
