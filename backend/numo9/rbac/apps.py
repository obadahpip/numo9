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
        # Tenant sweep (A-01-T09): rows of ApprovalLimit for the approval-limits endpoints.
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["rbac.ApprovalLimit"] = _sweep_limit


def _sync_after_migrate(sender: AppConfig, **kwargs: Any) -> None:
    from .models import Role, RolePermission
    from .system_roles import sync_system_roles

    sync_system_roles(Role, RolePermission)


def _sweep_limit(organisation: Any) -> Any:
    from .models import ApprovalLimit, Role

    owner = Role.objects.get(is_system=True, scope="organisation", key="owner")
    existing = ApprovalLimit._base_manager.filter(
        organisation=organisation, role=owner, doc_type="bill", deleted_at__isnull=True
    ).first()
    return existing or ApprovalLimit._base_manager.create(
        organisation=organisation, role=owner, doc_type="bill", max_amount=1000
    )
