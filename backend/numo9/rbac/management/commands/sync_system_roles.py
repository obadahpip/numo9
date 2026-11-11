"""``manage.py sync_system_roles`` — create missing system roles and align their permissions
with the catalogue (A-03-T03). Runs automatically after ``migrate``; idempotent."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from numo9.rbac.models import Role, RolePermission
from numo9.rbac.system_roles import sync_system_roles


class Command(BaseCommand):
    help = "Create missing system roles and align their permission sets with the catalogue."

    def handle(self, *args: Any, **options: Any) -> None:
        counts = sync_system_roles(Role, RolePermission)
        self.stdout.write(
            "System roles: {roles_created} created, {permissions_added} permissions added, "
            "{permissions_removed} removed.".format(**counts)
        )
