"""Per-person dashboard layouts with role defaults (K-05-T02).

- ``dashboard_role(user, organisation)`` — which default a person gets: owner/admin → owner;
  accountant delegate, or no membership but a practice serving the organisation → accountant;
  sales; purchasing; anyone else → basic.
- ``layout_for(user, organisation)`` — the person's layout; the first call saves their role's
  default (a new person gets the role default).
- ``save_layout(user, organisation, widgets)`` — the widgets in order with their settings:
  known keys only, each once, settings validated by the widget (``LayoutError`` names the
  problem); marks the layout customised.
- ``reset_layout(user, organisation)`` — back to the role's default (the role is looked up again:
  a person whose role changed gets the new role's default).
- ``visible_widgets(layout)`` — the stored widgets the library still knows, in order.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

from .models import DashboardLayout, DashboardRole
from .widgets import LIBRARY, MEMBER_ROLES, BadSetting, default_widgets

MAX_WIDGETS = len(LIBRARY)


class LayoutError(ValueError):
    """A refused layout: ``code`` is ``unknown_widget``, ``duplicate_widget``, ``bad_setting``
    or ``bad_layout``; ``key`` the widget, ``setting`` the setting."""

    def __init__(self, code: str, key: str = "", setting: str = "") -> None:
        super().__init__(code, key, setting)
        self.code, self.key, self.setting = code, key, setting


def dashboard_role(user: Any, organisation: Organisation) -> str:
    membership = (
        OrganisationMember.objects.filter(user=user, organisation=organisation)
        .values_list("role", flat=True)
        .first()
    )
    if membership is None:
        return DashboardRole.ACCOUNTANT  # reached through a practice serving the organisation
    return MEMBER_ROLES.get(membership, DashboardRole.BASIC)


def layout_for(user: Any, organisation: Organisation) -> DashboardLayout:
    with org_context(organisation):
        found: DashboardLayout | None = DashboardLayout.objects.filter(user=user).first()
        if found is not None:
            return found
        role = dashboard_role(user, organisation)
        try:
            with transaction.atomic():
                created: DashboardLayout = DashboardLayout.objects.create(
                    organisation=organisation,
                    user=user,
                    role=role,
                    widgets=default_widgets(role),
                )
                return created
        except IntegrityError:  # opened twice at once: the other request saved it
            layout: DashboardLayout = DashboardLayout.objects.get(user=user)
            return layout


def clean_widgets(widgets: Any) -> list[dict[str, Any]]:
    if not isinstance(widgets, list) or len(widgets) > MAX_WIDGETS:
        raise LayoutError("bad_layout")
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in widgets:
        if isinstance(item, str):
            item = {"key": item}
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise LayoutError("bad_layout")
        key = item["key"]
        if key not in LIBRARY:
            raise LayoutError("unknown_widget", key[:40])
        if key in seen:
            raise LayoutError("duplicate_widget", key)
        seen.add(key)
        try:
            settings = LIBRARY[key].clean_settings(item.get("settings"))
        except BadSetting as error:
            raise LayoutError("bad_setting", key, str(error.args[1])) from None
        clean.append({"key": key, "settings": settings})
    return clean


def save_layout(user: Any, organisation: Organisation, widgets: Any) -> DashboardLayout:
    clean = clean_widgets(widgets)
    layout = layout_for(user, organisation)
    with org_context(organisation):
        layout.widgets = clean
        layout.customised = True
        layout.save(update_fields=["widgets", "customised", "updated_at"])
    return layout


def reset_layout(user: Any, organisation: Organisation) -> DashboardLayout:
    layout = layout_for(user, organisation)
    role = dashboard_role(user, organisation)
    with org_context(organisation):
        layout.role = role
        layout.widgets = default_widgets(role)
        layout.customised = False
        layout.save(update_fields=["role", "widgets", "customised", "updated_at"])
    return layout


def visible_widgets(layout: DashboardLayout) -> list[dict[str, Any]]:
    return [
        item
        for item in layout.widgets or []
        if isinstance(item, dict) and item.get("key") in LIBRARY
    ]
