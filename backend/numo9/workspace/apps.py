from django.apps import AppConfig


class WorkspaceConfig(AppConfig):
    """Accountant workspace (component V): the organisation directory and its saved views (V-01);
    groups and tags, bulk actions, dashboards and staff management join here (V-02…V-05)."""

    name = "numo9.workspace"
    label = "workspace"
    verbose_name = "Accountant workspace"

    def ready(self) -> None:
        from . import access, groups, signals

        signals.connect()
        groups.connect()  # membership clean-up when a practice stops serving (V-02-T02)
        access.connect()  # access through groups in the A-01 resolver (V-02-T05)
        from .summary import register_tags_provider
        from .tags import provide_tags

        register_tags_provider(provide_tags)  # tag names in the directory rows (V-02-T08)
