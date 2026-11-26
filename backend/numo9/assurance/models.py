"""Exceptions engine models (K-09-T03).

- ``ExceptionRuleConfig`` — an organisation's settings of one rule: on/off, severity and
  parameters (validated against the rule's schema, ``rules.base``). No row = the rule's defaults.
- ``ExceptionFinding`` — one problem found by a rule about one subject (a journal, an account, a
  bill, a person, the organisation…). ``fingerprint`` = sha256(rule | subject type | subject id):
  **one open or acknowledged finding per fingerprint** (database constraint); resolved and
  false-positive rows stay as history. ``fix_entry`` is the draft journal proposed for it
  (K-09-T16).
- ``ExceptionRun`` — one evaluation: full (on demand, nightly) or incremental (a posting), with
  its counts.
"""

from __future__ import annotations

import hashlib
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel


class Severity(models.TextChoices):
    INFO = "info", _("Info")
    WARNING = "warning", _("Warning")
    CRITICAL = "critical", _("Critical")


#: Most severe first (lists, groups).
SEVERITY_ORDER: dict[str, int] = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


class FindingStatus(models.TextChoices):
    OPEN = "open", _("Open")
    ACKNOWLEDGED = "acknowledged", _("Acknowledged")
    RESOLVED = "resolved", _("Resolved")
    FALSE_POSITIVE = "false_positive", _("False positive")


#: Findings that still need attention (one per fingerprint).
ACTIVE_STATUSES: tuple[str, ...] = (FindingStatus.OPEN, FindingStatus.ACKNOWLEDGED)


class RunTrigger(models.TextChoices):
    MANUAL = "manual", _("On demand")
    NIGHTLY = "nightly", _("Nightly")
    POSTING = "posting", _("On posting")


class RunStatus(models.TextChoices):
    RUNNING = "running", _("Running")
    SUCCEEDED = "succeeded", _("Succeeded")
    FAILED = "failed", _("Failed")


def fingerprint_of(rule_code: str, subject_type: str, subject_id: str) -> str:
    raw = f"{rule_code}|{subject_type}|{subject_id}".encode()
    return hashlib.sha256(raw).hexdigest()


class ExceptionRuleConfig(AuditedModel, OrgOwnedModel):
    rule_code = models.CharField(_("rule"), max_length=60)
    enabled = models.BooleanField(_("on"), default=True)
    severity = models.CharField(_("severity"), max_length=10, choices=Severity.choices, blank=True)
    params = models.JSONField(_("parameters"), default=dict, blank=True)

    class Meta:
        ordering = ("rule_code",)
        verbose_name = _("assurance rule setting")
        verbose_name_plural = _("assurance rule settings")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "rule_code"), name="assurance_rule_config_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(severity="") | models.Q(severity__in=Severity.values),
                name="assurance_rule_config_severity_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.rule_code

    def audit_label(self) -> str:
        return self.rule_code


class ExceptionRun(OrgOwnedModel):
    trigger = models.CharField(_("trigger"), max_length=10, choices=RunTrigger.choices)
    status = models.CharField(
        _("status"), max_length=10, choices=RunStatus.choices, default=RunStatus.RUNNING
    )
    started_at = models.DateTimeField(_("started at"), default=timezone.now)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    #: Incremental runs: ``{"entries": [...], "accounts": [...]}`` (public ids); empty = full.
    scope = models.JSONField(_("scope"), default=dict, blank=True)
    rules = models.JSONField(_("rules run"), default=list, blank=True)
    #: ``{"created", "reopened", "updated", "resolved", "seen"}``.
    counts = models.JSONField(_("counts"), default=dict, blank=True)
    error = models.TextField(_("error"), blank=True)
    job_run = models.ForeignKey(
        "jobs.JobRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("job"),
    )

    class Meta:
        ordering = ("-started_at", "-pk")
        verbose_name = _("assurance run")
        verbose_name_plural = _("assurance runs")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(trigger__in=RunTrigger.values),
                name="assurance_run_trigger_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=RunStatus.values),
                name="assurance_run_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "started_at"), name="assurance_run_started_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_trigger_display()} {self.started_at:%Y-%m-%d %H:%M}"


class ExceptionFinding(OrgOwnedModel):
    rule_code = models.CharField(_("rule"), max_length=60)
    severity = models.CharField(_("severity"), max_length=10, choices=Severity.choices)
    subject_type = models.CharField(_("subject type"), max_length=60)
    subject_id = models.CharField(_("subject"), max_length=120)
    subject_label = models.CharField(_("subject label"), max_length=300, blank=True)
    fingerprint = models.CharField(_("fingerprint"), max_length=64)
    amount = models.DecimalField(
        _("amount"), max_digits=18, decimal_places=2, null=True, blank=True
    )
    details = models.JSONField(_("details"), default=dict, blank=True)
    status = models.CharField(
        _("status"), max_length=16, choices=FindingStatus.choices, default=FindingStatus.OPEN
    )
    first_seen = models.DateTimeField(_("first seen"), default=timezone.now)
    last_seen = models.DateTimeField(_("last seen"), default=timezone.now)
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    ack_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("acknowledged by"),
    )
    ack_at = models.DateTimeField(_("acknowledged at"), null=True, blank=True)
    reason = models.TextField(_("reason"), blank=True)
    last_run = models.ForeignKey(
        ExceptionRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("last run"),
    )
    fix_entry = models.ForeignKey(
        "ledger.JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assurance_findings",
        verbose_name=_("fix journal"),
    )

    class Meta:
        ordering = ("-last_seen", "-pk")
        verbose_name = _("assurance finding")
        verbose_name_plural = _("assurance findings")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "fingerprint"),
                condition=models.Q(status__in=ACTIVE_STATUSES),
                name="assurance_finding_one_active",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=FindingStatus.values),
                name="assurance_finding_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(severity__in=Severity.values),
                name="assurance_finding_severity_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status="false_positive") | ~models.Q(reason=""),
                name="assurance_finding_false_positive_reason",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "status", "rule_code"), name="assurance_finding_status_idx"
            ),
            models.Index(
                fields=("organisation", "fingerprint"), name="assurance_finding_print_idx"
            ),
            models.Index(
                fields=("organisation", "subject_type", "subject_id"),
                name="assurance_finding_subject_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rule_code} · {self.subject_label or self.subject_id}"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.fingerprint:
            self.fingerprint = fingerprint_of(self.rule_code, self.subject_type, self.subject_id)
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES
