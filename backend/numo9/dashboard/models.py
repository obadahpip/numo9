"""Organisation dashboard models (K-05).

``DashboardLayout`` (K-05-T02) — one person's organisation home: which widgets, in which order,
with which settings. One row per person and organisation, created from the person's **role
default** the first time their home is opened (``numo9.dashboard.layouts.layout_for``); from then
on it is theirs (``customised`` once they changed it). Widget keys the library doesn't know any
more are kept but not shown; the practice home has its own layout (``workspace.DashboardLayout``,
V-04-T09).
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import OrgOwnedModel


class DashboardRole(models.TextChoices):
    """The role defaults (K-05 business rule: owner, accountant, sales and purchasing differ)."""

    OWNER = "owner", _("Owner or admin")
    ACCOUNTANT = "accountant", _("Accountant")
    SALES = "sales", _("Sales")
    PURCHASING = "purchasing", _("Purchasing")
    BASIC = "basic", _("Everyone else")


class DashboardLayout(OrgOwnedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # personal preferences go with the person
        related_name="organisation_dashboards",
        verbose_name=_("person"),
    )
    widgets = models.JSONField(
        _("widgets"),
        default=list,
        blank=True,
        help_text=_('In order: [{"key": "cash_in_out", "settings": {"months": 6}}, …].'),
    )
    role = models.CharField(
        _("role default"),
        max_length=16,
        choices=DashboardRole.choices,
        help_text=_("The role whose default layout this one started from."),
    )
    customised = models.BooleanField(_("changed by the person"), default=False)

    class Meta:
        verbose_name = _("dashboard layout")
        verbose_name_plural = _("dashboard layouts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "user"), name="dashboard_layout_one_per_person"
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=DashboardRole.values),
                name="dashboard_layout_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · dashboard"
