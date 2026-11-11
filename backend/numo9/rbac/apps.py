from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class RbacConfig(AppConfig):
    """Roles, permissions and approval limits (A-03)."""

    name = "numo9.rbac"
    label = "rbac"
    verbose_name = "Roles and permissions"

    def ready(self) -> None:
        # Fill the permission catalogue from every installed app's permissions.py (A-03-T01).
        autodiscover_modules("permissions")
