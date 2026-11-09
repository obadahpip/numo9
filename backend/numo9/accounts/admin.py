"""Django admin for users (platform staff only; org-scoped admin rules arrive in A-01-T15)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import User

# The stubs make these Django classes generic; at runtime they are not subscriptable.
if TYPE_CHECKING:
    _CreationFormBase = AdminUserCreationForm[User]
    _ChangeFormBase = DjangoUserChangeForm[User]
    _UserAdminBase = DjangoUserAdmin[User]
else:
    _CreationFormBase = AdminUserCreationForm
    _ChangeFormBase = DjangoUserChangeForm
    _UserAdminBase = DjangoUserAdmin


class UserCreationForm(_CreationFormBase):
    class Meta:
        model = User
        fields = ("email", "name")


class UserChangeForm(_ChangeFormBase):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(_UserAdminBase):
    form = UserChangeForm
    add_form = UserCreationForm
    ordering = ("email",)
    list_display = ("email", "name", "locale", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "locale")
    search_fields = ("email", "name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Profile"), {"fields": ("name", "locale", "time_format")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "usable_password", "password1", "password2"),
            },
        ),
    )
