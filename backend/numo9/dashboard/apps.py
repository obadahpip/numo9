from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Organisation dashboard (K-05): each person's home layout (widgets, order, settings) with
    role defaults, the widget library and the widget data services (deadlines …)."""

    name = "numo9.dashboard"
    label = "dashboard"
    verbose_name = "Dashboard"
