"""Accountant workspace models (V-01).

``OrgDirectorySummary`` (V-01-T02) — one denormalised row per **practice × organisation** the
practice actively serves: everything the organisation directory searches, filters, sorts and
counts, in one table, so 2,000 organisations answer in well under 300 ms (p95) without joining
settings, registrations, subscriptions and memberships on every keystroke.

- The row is *derived*: ``numo9.workspace.summary`` rebuilds it from the source records (signals on
  every change, a nightly full rebuild); nothing edits it by hand. Rows of an assignment that is
  switched off are deleted (the practice no longer serves the organisation).
- Per practice, not per organisation: tags are the practice's own (V-02), and a practice must never
  see another practice's tags for the same client.
- ``search_vector`` — PostgreSQL ``tsvector`` (configuration ``simple``, ``unaccent``: "Erable"
  finds "Érable") over name, legal name, BN, owner, tags, industry and province; GIN index.
  ``bn`` (the nine digits) also has a trigram index, so a partial BN typed with or without spaces
  matches.
- ``gst_cycle``, ``overdue_count`` and ``unfiled_count`` are filled by providers that later phases
  register (GST/HST returns, sales invoices, filings); empty / 0 until then.

It is a cross-organisation *read model* of directory facts (the same facts ``/api/v1/me/
organisations`` shows), not an organisation's business records: it is allow-listed in
``numo9.tenancy.checks`` and every read goes through ``numo9.workspace.search``, which limits it to
the organisations the user may access in that practice (isolation tests:
``tests/test_workspace_isolation.py``).
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation, Practice


class DirectoryStatus(models.TextChoices):
    """Commercial state as the directory shows it (status chips: Trial 12 d, Paid, Demo…)."""

    TRIAL = "trial", _("Trial")
    PAID = "paid", _("Paid")
    DEMO = "demo", _("Demo")
    READ_ONLY = "read_only", _("Read-only")
    ARCHIVED = "archived", _("Archived")


class Density(models.TextChoices):
    """Row height of the directory grid (A-10-T10 density toggle)."""

    COMFORTABLE = "comfortable", _("Comfortable")
    COMPACT = "compact", _("Compact")


class GstCycle(models.TextChoices):
    """GST/HST filing frequency (fed by the GST/HST returns provider of a later phase)."""

    MONTHLY = "monthly", _("Monthly")
    QUARTERLY = "quarterly", _("Quarterly")
    ANNUAL = "annual", _("Annual")


def _in(field: str, choices: type[models.TextChoices], *, blank: bool = False) -> models.Q:
    condition = models.Q(**{f"{field}__in": choices.values})
    return condition | models.Q(**{field: ""}) if blank else condition


class OrgDirectorySummary(models.Model):
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,  # derived data: goes with the practice
        related_name="directory_rows",
        verbose_name=_("practice"),
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,  # derived data: goes with the organisation
        related_name="directory_rows",
        verbose_name=_("organisation"),
    )
    name = models.CharField(_("name"), max_length=200)
    legal_name = models.CharField(_("legal name"), max_length=200, blank=True)
    bn = models.CharField(_("Business Number"), max_length=9, blank=True)
    owner_name = models.CharField(_("owner"), max_length=200, blank=True)
    owner_email = models.CharField(_("owner email"), max_length=254, blank=True)
    industry = models.CharField(_("industry"), max_length=100, blank=True)
    province = models.CharField(_("province or territory"), max_length=2, blank=True)
    package = models.CharField(_("package"), max_length=64, blank=True)
    status = models.CharField(_("status"), max_length=16, choices=DirectoryStatus.choices)
    trial_ends_at = models.DateTimeField(_("trial ends"), null=True, blank=True)
    fye_month = models.PositiveSmallIntegerField(_("fiscal year end month"), default=12)
    fye_day = models.PositiveSmallIntegerField(_("fiscal year end day"), default=31)
    gst_cycle = models.CharField(
        _("GST/HST cycle"), max_length=16, choices=GstCycle.choices, blank=True
    )
    payroll_enabled = models.BooleanField(_("payroll"), default=False)
    overdue_count = models.PositiveIntegerField(_("overdue items"), default=0)
    unfiled_count = models.PositiveIntegerField(_("unfiled returns"), default=0)
    tags = models.JSONField(_("tags"), default=list, blank=True)
    search_vector = SearchVectorField(_("search vector"), null=True, editable=False)
    refreshed_at = models.DateTimeField(_("refreshed at"))

    class Meta:
        verbose_name = _("organisation directory row")
        verbose_name_plural = _("organisation directory rows")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("practice", "organisation"), name="workspace_summary_one_per_assignment"
            ),
            models.CheckConstraint(
                condition=_in("status", DirectoryStatus), name="workspace_summary_status_valid"
            ),
            models.CheckConstraint(
                condition=_in("gst_cycle", GstCycle, blank=True),
                name="workspace_summary_gst_cycle_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(fye_month__gte=1, fye_month__lte=12),
                name="workspace_summary_fye_month_valid",
            ),
        ]
        # GIN (search_vector) and trigram (bn) indexes are created by the migration on PostgreSQL
        # only (numo9.audit.pg.PostgresOnly): a throw-away SQLite database can still migrate.
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("practice", "name"), name="workspace_summary_name_idx"),
            models.Index(fields=("practice", "status"), name="workspace_summary_status_idx"),
            models.Index(fields=("organisation",), name="workspace_summary_org_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.practice} → {self.name}"


class SavedView(models.Model):
    """A user's own named directory state in one practice (V-01-T08): search and filters, the
    columns shown and their order, the sort, the row density; one view can open by default.

    Personal: nobody else — not even a practice admin — lists, opens, changes or deletes it (the
    API answers 404). Stored on the server, so a view follows the user to another browser or
    device and survives logout/login. Not organisation data (it names filter values, not records):
    allow-listed platform model, like the practice memberships it belongs to.
    """

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # personal preferences go with the user
        related_name="directory_views",
        verbose_name=_("user"),
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name="directory_views",
        verbose_name=_("practice"),
    )
    name = models.CharField(_("name"), max_length=80)
    filters = models.JSONField(
        _("search and filters"),
        default=dict,
        blank=True,
        help_text=_('{"q": "maple", "province": ["ON"], "status": ["paid"]}'),
    )
    columns = models.JSONField(
        _("columns"), default=list, blank=True, help_text=_("Shown columns, in order.")
    )
    sort = models.JSONField(
        _("sort"), default=list, blank=True, help_text=_('["-overdue", "name"]')
    )
    density = models.CharField(
        _("density"), max_length=16, choices=Density.choices, default=Density.COMFORTABLE
    )
    is_default = models.BooleanField(_("opens by default"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("saved directory view")
        verbose_name_plural = _("saved directory views")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "user", "practice", Lower("name"), name="workspace_view_name_unique_per_user"
            ),
            models.UniqueConstraint(
                fields=("user", "practice"),
                condition=models.Q(is_default=True),
                name="workspace_view_one_default_per_user",
            ),
            models.CheckConstraint(
                condition=_in("density", Density), name="workspace_view_density_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.practice} · {self.name}"
