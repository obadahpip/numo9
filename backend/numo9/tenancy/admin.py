"""Django admin scoping (A-01-T15).

- The admin site is for **platform staff only**: an active user with ``is_staff``. Organisation
  owners, organisation users and practice staff never get ``is_staff``; no API sets it.
- Business models are registered with ``OrgOwnedAdmin``. The admin works outside any
  organisation, so its queries go through the explicit, logged ``objects.unscoped(reason=...)``
  (the reason names the staff user), every change is logged on ``numo9.tenancy.admin``, Django
  keeps its own admin change log (``LogEntry``), and the full audit trail joins in A-04.
- "Delete" in the admin is a soft delete: business records are never removed (CRA six years).
- Platform models (practices, organisations and their memberships) are registered as plain
  admins: they hold no organisation's business data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest

from .models import (
    Organisation,
    OrganisationMember,
    OrgOwnedModel,
    Practice,
    PracticeAssignment,
    PracticeMember,
)

logger = logging.getLogger("numo9.tenancy.admin")

if TYPE_CHECKING:
    _OrgOwnedAdminBase = admin.ModelAdmin[Any]
    _OrganisationAdminBase = admin.ModelAdmin[Organisation]
    _PracticeAdminBase = admin.ModelAdmin[Practice]
    _TabularInline = admin.TabularInline[Any, Any]
else:
    _OrgOwnedAdminBase = _OrganisationAdminBase = _PracticeAdminBase = admin.ModelAdmin
    _TabularInline = admin.TabularInline


def _who(request: HttpRequest) -> str:
    user = request.user
    return f"{getattr(user, 'email', '?')} (id {getattr(user, 'pk', '?')})"


class OrgOwnedAdmin(_OrgOwnedAdminBase):
    """Base admin for every ``OrgOwnedModel``: explicit unscoped access with audit logging."""

    list_display = ("__str__", "organisation", "created_at", "deleted_at")
    list_filter = ("organisation",)
    readonly_fields = ("public_id", "created_by", "created_at", "updated_at", "deleted_at")
    actions = ("soft_delete_selected",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        model: type[OrgOwnedModel] = self.model
        queryset = model.objects.unscoped(
            reason=f"Django admin {model._meta.label} by platform staff {_who(request)}"
        )
        ordering = self.get_ordering(request)
        return queryset.order_by(*ordering) if ordering else queryset

    def save_model(
        self, request: HttpRequest, obj: Any, form: ModelForm[Any], change: bool
    ) -> None:
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        logger.warning(
            "Admin %s %s %s by %s",
            "changed" if change else "added",
            obj._meta.label,
            obj.public_id,
            _who(request),
        )

    def delete_model(self, request: HttpRequest, obj: Any) -> None:
        obj.soft_delete()
        logger.warning(
            "Admin soft-deleted %s %s by %s", obj._meta.label, obj.public_id, _who(request)
        )

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[Any]) -> None:
        for obj in queryset:
            self.delete_model(request, obj)

    def get_actions(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        actions = super().get_actions(request, *args, **kwargs)
        actions.pop("delete_selected", None)  # hard delete is never offered
        return actions

    @admin.action(description="Soft-delete selected records", permissions=["delete"])
    def soft_delete_selected(self, request: HttpRequest, queryset: QuerySet[Any]) -> None:
        self.delete_queryset(request, queryset)


class PracticeMemberInline(_TabularInline):
    model = PracticeMember
    extra = 0


class OrganisationMemberInline(_TabularInline):
    model = OrganisationMember
    extra = 0


@admin.register(Practice)
class PracticeAdmin(_PracticeAdminBase):
    list_display = ("name", "public_id", "created_at")
    search_fields = ("name",)
    readonly_fields = ("public_id", "created_at", "updated_at")
    inlines = (PracticeMemberInline,)


@admin.register(Organisation)
class OrganisationAdmin(_OrganisationAdminBase):
    list_display = ("name", "status", "time_zone", "public_id", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)
    readonly_fields = ("public_id", "created_at", "updated_at")
    inlines = (OrganisationMemberInline,)


@admin.register(PracticeAssignment)
class PracticeAssignmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("practice", "organisation", "role", "active")
    list_filter = ("active", "role")
    filter_horizontal = ("assigned_staff",)


__all__ = ["OrgOwnedAdmin"]
