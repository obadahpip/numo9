"""Bulk jobs (V-03-T02): one bulk action of a practice over many organisations.

``BulkJob`` — the action (``group``, ``tags``, ``staff``, ``settings``, ``message``, ``export``),
its parameters, the selection (organisation ids, or the directory query that found them), who
started it, its status and counters. ``BulkJobRow`` — **one row per selected organisation** with
its outcome (``succeeded`` / ``skipped`` / ``failed`` / ``cancelled``, ``pending`` until done), a
reason code and message, and the before/after values. A job is never silently partial: when it
ends, every row has an outcome.

Practice data (not one organisation's): reachable only through the practice's own API.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation, Practice


class BulkAction(models.TextChoices):
    GROUP = "group", _("Move to a group")
    TAGS = "tags", _("Add or remove tags")
    STAFF = "staff", _("Assign or unassign staff")
    SETTINGS = "settings", _("Change settings")
    MESSAGE = "message", _("Send a message")
    EXPORT = "export", _("Export the list")


class BulkStatus(models.TextChoices):
    PREVIEW = "preview", _("Preview")
    QUEUED = "queued", _("Waiting to start")
    RUNNING = "running", _("Running")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")


class RowOutcome(models.TextChoices):
    PENDING = "pending", _("Waiting")
    SUCCEEDED = "succeeded", _("Succeeded")
    SKIPPED = "skipped", _("Skipped")
    FAILED = "failed", _("Failed")
    CANCELLED = "cancelled", _("Cancelled")


FINAL_OUTCOMES = frozenset(
    {RowOutcome.SUCCEEDED, RowOutcome.SKIPPED, RowOutcome.FAILED, RowOutcome.CANCELLED}
)


def _in(field: str, choices: type[models.TextChoices]) -> models.Q:
    return models.Q(**{f"{field}__in": choices.values})


class BulkJob(models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    practice = models.ForeignKey(
        Practice, on_delete=models.PROTECT, related_name="bulk_jobs", verbose_name=_("practice")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bulk_jobs",
        verbose_name=_("started by"),
    )
    action = models.CharField(_("action"), max_length=16, choices=BulkAction.choices)
    params = models.JSONField(_("parameters"), default=dict, blank=True)
    selection = models.JSONField(
        _("selection"),
        default=dict,
        help_text=_('{"ids": [organisation ids]} or {"query": {directory search and filters}}'),
    )
    status = models.CharField(
        _("status"), max_length=16, choices=BulkStatus.choices, default=BulkStatus.PREVIEW
    )
    total = models.PositiveIntegerField(_("organisations"), default=0)
    job_run = models.ForeignKey(
        "jobs.JobRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("background job"),
    )
    result_file = models.CharField(_("result file"), max_length=500, blank=True)
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    confirmed_at = models.DateTimeField(_("confirmed at"), null=True, blank=True)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    cancel_requested_at = models.DateTimeField(_("cancel requested at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("bulk job")
        verbose_name_plural = _("bulk jobs")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(condition=_in("action", BulkAction), name="bulk_job_action"),
            models.CheckConstraint(condition=_in("status", BulkStatus), name="bulk_job_status"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("practice", "-created_at"), name="bulk_job_practice_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} × {self.total} ({self.status})"

    def counts(self) -> dict[str, int]:
        found = dict(
            self.rows.values("outcome").annotate(n=models.Count("id")).values_list("outcome", "n")
        )
        return {outcome: int(found.get(outcome, 0)) for outcome in RowOutcome.values}


class BulkJobRow(models.Model):
    job = models.ForeignKey(
        BulkJob, on_delete=models.CASCADE, related_name="rows", verbose_name=_("bulk job")
    )
    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="+", verbose_name=_("organisation")
    )
    position = models.PositiveIntegerField(_("position"))
    outcome = models.CharField(
        _("outcome"), max_length=16, choices=RowOutcome.choices, default=RowOutcome.PENDING
    )
    reason = models.CharField(_("reason code"), max_length=64, blank=True)
    message = models.CharField(_("message"), max_length=500, blank=True)
    before = models.JSONField(_("before"), default=dict, blank=True)
    after = models.JSONField(_("after"), default=dict, blank=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    class Meta:
        ordering = ("job", "position")
        verbose_name = _("bulk job row")
        verbose_name_plural = _("bulk job rows")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("job", "organisation"), name="bulk_row_one_per_org"),
            models.UniqueConstraint(fields=("job", "position"), name="bulk_row_position"),
            models.CheckConstraint(condition=_in("outcome", RowOutcome), name="bulk_row_outcome"),
            models.CheckConstraint(
                condition=models.Q(outcome=RowOutcome.PENDING, processed_at__isnull=True)
                | (~models.Q(outcome=RowOutcome.PENDING) & models.Q(processed_at__isnull=False)),
                name="bulk_row_processed_when_final",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("job", "outcome"), name="bulk_row_outcome_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.organisation_id}: {self.outcome}"
