"""Report layouts (K-01-T08).

``ReportLayout`` — a saved arrangement of one report for one organisation: which rows show, in
which order, under which labels, the text blocks between them and the footnotes. ``status``:

- ``draft`` — being edited;
- ``published`` — frozen: publishing runs the report with the layout's parameters and stores the
  result (``snapshot``: header, columns, rows, totals) with who and when. A published layout and
  its snapshot never change — later postings don't touch it; editing starts a new draft version;
- ``custom`` — a saved variant people pick by name (``name``), edited freely.

``practice`` names the practice whose staff made it for this client (practice layouts, K-01-T15),
empty for the organisation's own. ``version`` counts the versions of the same layout ``name``.
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel


class LayoutStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    PUBLISHED = "published", _("Published")
    CUSTOM = "custom", _("Custom")


class ReportLayout(AuditedModel, OrgOwnedModel):
    report_id = models.CharField(_("report"), max_length=60)
    name = models.CharField(_("name"), max_length=120)
    practice = models.ForeignKey(
        "tenancy.Practice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("practice"),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=LayoutStatus.choices, default=LayoutStatus.DRAFT
    )
    version = models.PositiveIntegerField(_("version"), default=1)
    params = models.JSONField(_("parameters"), default=dict, blank=True)
    config = models.JSONField(
        _("layout"),
        default=dict,
        blank=True,
        help_text=_('{"rows": [{"key", "label", "hidden"}], "text_blocks": [{"after", "text"}]}'),
    )
    notes = models.TextField(_("footnotes"), blank=True)
    snapshot = models.JSONField(_("published snapshot"), null=True, blank=True)
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("published by"),
    )

    class Meta:
        ordering = ("report_id", "name", "-version")
        verbose_name = _("report layout")
        verbose_name_plural = _("report layouts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(status__in=LayoutStatus.values),
                name="reports_layout_status_valid",
            ),
            models.UniqueConstraint(
                fields=["organisation", "report_id", "name", "version"],
                condition=models.Q(deleted_at__isnull=True),
                name="reports_layout_version_unique",
            ),
            # Published ⇔ a snapshot exists.
            models.CheckConstraint(
                condition=~models.Q(status="published") | models.Q(snapshot__isnull=False),
                name="reports_layout_published_snapshot",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.report_id} · {self.name} v{self.version}"
