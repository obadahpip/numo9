"""Job runs: the record of every background job a person or the platform started (A-08-T02).

A ``JobRun`` is written before the Celery message is sent and updated by the job base class
(A-08-T03) as the job moves through its lifecycle:

    queued → running → succeeded
                     ↘ retrying → running → …            (A-08-T04: backoff + jitter)
                     ↘ failed   (an error that retrying cannot fix)
                     ↘ dead     (retries used up: the dead-letter state — kept for a person to
                                 retry or purge from the job dashboard, A-08-T08)

It is what users see in the job tray (A-08-T07: progress, result link, error with Retry) and
what the platform owner sees in the console (A-08-T08); Celery's own result backend keeps
outcomes for one day only. Finished runs are kept 30 days (``RETENTION``, purged by a beat job,
A-08-T05).

**Idempotency.** ``idempotency_key`` is unique across the table: starting a job with a key that
already has a run returns that run instead of starting a second one, and the database refuses a
duplicate even when two processes race (A-08-T03 builds the key from the task name, the
organisation and the caller's key, so two organisations never collide).

**Tenancy.** Organisation jobs (an import, a bulk edit, an export) belong to one organisation and
are read through ``objects`` — the ``OrgScopedManager`` of every business record, so an API view
can never list another organisation's jobs. Platform jobs (the retention purge, a nightly
rebuild) have no organisation (``organisation`` is empty). The job machinery itself and the
platform console read every run through ``platform_runs`` — a plain manager kept for those two
uses only (``numo9/jobs/runtime.py``, ``numo9/jobs/console.py``).
"""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation, OrgOwnedModel

#: Finished job runs are kept this long (A-08 business rule), then purged.
RETENTION = timedelta(days=30)


class JobStatus(models.TextChoices):
    QUEUED = "queued", _("Waiting to start")
    RUNNING = "running", _("Running")
    RETRYING = "retrying", _("Waiting to try again")
    SUCCEEDED = "succeeded", _("Done")
    FAILED = "failed", _("Failed")
    DEAD = "dead", _("Failed after several tries")


#: A run in one of these states will not change again unless a person retries it.
FINISHED: frozenset[str] = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.DEAD})
#: A run in one of these states is still going (shown as active in the job tray).
ACTIVE: frozenset[str] = frozenset({JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.RETRYING})
#: Failed runs a person may start again (A-08-T04 retry from the tray or the console).
RETRYABLE: frozenset[str] = frozenset({JobStatus.FAILED, JobStatus.DEAD})


class JobRun(OrgOwnedModel):
    """One background job: what it is, where it stands, and how it ended."""

    # Platform jobs have no organisation (overrides the required field of OrgOwnedModel).
    organisation = models.ForeignKey(  # type: ignore[assignment]  # nullable here
        Organisation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="job_runs",
        verbose_name=_("organisation"),
    )
    task_name = models.CharField(_("job type"), max_length=200)
    queue = models.CharField(_("queue"), max_length=32, default="default")
    status = models.CharField(
        _("status"), max_length=16, choices=JobStatus.choices, default=JobStatus.QUEUED
    )
    # Progress: `progress_done` of `progress_total` steps (total unknown → empty).
    progress_done = models.PositiveIntegerField(_("steps done"), default=0)
    progress_total = models.PositiveIntegerField(_("steps in total"), null=True, blank=True)
    progress_message = models.CharField(_("progress note"), max_length=200, blank=True)
    # The task's keyword arguments, kept so a failed run can be sent again (JSON, as on the wire).
    payload = models.JSONField(_("arguments"), default=dict, blank=True)
    result = models.JSONField(_("result"), null=True, blank=True)
    result_url = models.CharField(_("result link"), max_length=500, blank=True)
    # What went wrong: a stable code and a message the person who started the job may read;
    # `error_detail` (exception type and text, scrubbed) is for the platform console only.
    error_code = models.CharField(_("error code"), max_length=100, blank=True)
    error_message = models.TextField(_("error"), blank=True)
    error_detail = models.TextField(_("error detail"), blank=True)
    idempotency_key = models.CharField(_("idempotency key"), max_length=255)
    attempts = models.PositiveSmallIntegerField(_("attempts"), default=0)
    max_retries = models.PositiveSmallIntegerField(_("maximum retries"), default=5)
    celery_task_id = models.CharField(_("Celery task id"), max_length=255, blank=True)
    worker = models.CharField(_("worker"), max_length=255, blank=True)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    next_retry_at = models.DateTimeField(_("next try at"), null=True, blank=True)

    # Job machinery and platform console only — see the module docstring.
    platform_runs = models.Manager["JobRun"]()

    class Meta:
        verbose_name = _("job run")
        verbose_name_plural = _("job runs")
        # The organisation-scoped manager stays the default (related lookups, dumpdata, admin).
        default_manager_name = "objects"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["idempotency_key"], name="jobs_jobrun_idempotency_key_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=JobStatus.values), name="jobs_jobrun_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(progress_total__isnull=True)
                | models.Q(progress_done__lte=models.F("progress_total")),
                name="jobs_jobrun_progress_within_total",
            ),
            models.CheckConstraint(
                condition=~models.Q(idempotency_key=""), name="jobs_jobrun_idempotency_key_set"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            # Job tray: a person's recent jobs in an organisation.
            models.Index(
                fields=["organisation", "created_by", "-created_at"], name="jobs_run_tray_idx"
            ),
            # Console: failures and queues; retention purge.
            models.Index(fields=["status", "-created_at"], name="jobs_run_status_idx"),
            models.Index(fields=["finished_at"], name="jobs_run_finished_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.task_name} [{self.status}] {self.public_id}"

    @property
    def is_finished(self) -> bool:
        return self.status in FINISHED

    @property
    def is_platform(self) -> bool:
        return self.organisation_id is None

    @property
    def progress_percent(self) -> int | None:
        """0–100, or None while the number of steps is unknown (succeeded runs are 100)."""
        if self.status == JobStatus.SUCCEEDED:
            return 100
        if not self.progress_total:
            return None
        return min(100, (self.progress_done * 100) // self.progress_total)
