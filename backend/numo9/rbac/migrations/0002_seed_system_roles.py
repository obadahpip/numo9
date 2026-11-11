"""Seed the 15 system roles with their default permission sets (A-03-T03).

The definitions and rules live in ``numo9.rbac.system_roles``; the same sync runs after every
``migrate`` (``post_migrate``) so roles pick up permissions that later apps declare.
"""

from typing import Any

from django.db import migrations


def seed(apps: Any, schema_editor: Any) -> None:
    from numo9.rbac.system_roles import sync_system_roles

    sync_system_roles(apps.get_model("rbac", "Role"), apps.get_model("rbac", "RolePermission"))


def unseed(apps: Any, schema_editor: Any) -> None:
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    RolePermission.objects.filter(role__is_system=True).delete()
    Role.objects.filter(is_system=True).delete()


class Migration(migrations.Migration):
    dependencies = [("rbac", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
