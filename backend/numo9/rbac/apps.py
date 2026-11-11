from typing import Any

from django.apps import AppConfig
from django.core import checks
from django.db.models.signals import post_migrate
from django.utils.module_loading import autodiscover_modules


class RbacConfig(AppConfig):
    """Roles, permissions and approval limits (A-03)."""

    name = "numo9.rbac"
    label = "rbac"
    verbose_name = "Roles and permissions"

    def ready(self) -> None:
        # Fill the permission catalogue from every installed app's permissions.py (A-03-T01).
        autodiscover_modules("permissions")
        from .checks import check_permission_declarations

        # Every API method declares its permission (A-03-T05).
        checks.register(check_permission_declarations, checks.Tags.urls)
        # Keep the system roles' permission sets in step with the catalogue (A-03-T03).
        post_migrate.connect(_sync_after_migrate, sender=self)


def _sync_after_migrate(sender: AppConfig, **kwargs: Any) -> None:
    from .models import Role, RolePermission
    from .system_roles import sync_system_roles

    sync_system_roles(Role, RolePermission)
