"""Bulk jobs: create (with its preview), confirm, cancel, run (V-03-T05).

- ``create_job`` — checks the action's practice permission, validates the parameters, previews
  and stores the job (``preview``); nothing else is written;
- ``confirm`` — resolves the selection again (the directory may have changed since the preview),
  creates **one pending row per organisation** and starts the background job (A-08, platform
  job ``numo9.bulk.run``, keyed by the bulk job so it is started once);
- ``cancel`` — asks the running job to stop before the next organisation (done rows stay done,
  the rest end ``cancelled``); a job not yet started is cancelled at once;
- ``run_bulk_job`` — the executor. Each organisation is one transaction: the row is locked, its
  access is checked again for the person who started the job (directory access and the action's
  organisation permission — ``skipped: no_access`` / ``no_permission``), the change is applied and
  the outcome written **in the same transaction** — with its audit event in the organisation's log
  (``bulk.<action>.applied``, the person who started the job as actor, ``bulk_job_id``;
  V-03-T11). A worker killed mid-job leaves finished rows
  finished and the current one untouched; the rerun (A-08 retries, or a redelivery) takes the
  rows still pending — each organisation is changed exactly once. An error in one organisation
  rolls back that organisation only (``failed: error``) and the job goes on. When the job ends,
  every row has an outcome.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import current_job, platform_job, start_job
from numo9.jobs.runtime import report_progress as _job_progress
from numo9.rbac.resolver import has_practice_perm
from numo9.tenancy.models import Practice
from numo9.workspace.search import directory_scope

from .actions import Context, get_action
from .models import BulkJob, BulkJobRow, BulkStatus, RowOutcome
from .preview import evaluate, preview, reason_text, selected_organisations

RUN_JOB = "numo9.bulk.run"


def _require(user: Any, practice: Practice, permission: str) -> None:
    if not has_practice_perm(user, practice, permission):
        from numo9.rbac.catalogue import catalogue

        label = str(catalogue.get(permission).label)
        raise api_error(errors.PERMISSION_DENIED, action=label[:1].lower() + label[1:])


def create_job(
    user: Any, practice: Practice, action_key: str, params: Any, selection: Any
) -> tuple[BulkJob, dict[str, Any]]:
    action = get_action(action_key)
    _require(user, practice, action.practice_permission)
    cleaned = action.clean(practice, params)
    result = preview(user, practice, action.key, cleaned, selection)
    job = BulkJob.objects.create(
        practice=practice,
        created_by=user,
        action=action.key,
        params=cleaned,
        selection=selection,
        total=result["total"],
    )
    return job, result


def confirm(job: BulkJob, user: Any) -> BulkJob:
    action = get_action(job.action)
    _require(user, job.practice, action.practice_permission)
    with transaction.atomic():
        job = BulkJob.objects.select_for_update().get(pk=job.pk)
        if job.status != BulkStatus.PREVIEW:
            raise api_error(errors.BULK_NOT_PREVIEW)
        orgs, _allowed = selected_organisations(job.created_by, job.practice, job.selection)
        BulkJobRow.objects.bulk_create(
            BulkJobRow(job=job, organisation=org, position=position)
            for position, org in enumerate(orgs)
        )
        job.total = len(orgs)
        job.status = BulkStatus.QUEUED
        job.confirmed_at = timezone.now()
        job.save(update_fields=["total", "status", "confirmed_at"])
        run = start_job(
            run_bulk_job, key=str(job.public_id), created_by=user, bulk_job=str(job.public_id)
        )
        job.job_run = run
        job.save(update_fields=["job_run"])
    return job


def cancel(job: BulkJob) -> BulkJob:
    with transaction.atomic():
        job = BulkJob.objects.select_for_update().get(pk=job.pk)
        if job.status in (BulkStatus.COMPLETED, BulkStatus.CANCELLED):
            return job
        job.cancel_requested_at = job.cancel_requested_at or timezone.now()
        fields = ["cancel_requested_at"]
        if job.status == BulkStatus.PREVIEW:
            job.status = BulkStatus.CANCELLED
            job.finished_at = timezone.now()
            fields += ["status", "finished_at"]
        job.save(update_fields=fields)
    return job


def _cancel_rest(job: BulkJob) -> None:
    job.rows.filter(outcome=RowOutcome.PENDING).update(
        outcome=RowOutcome.CANCELLED,
        reason="cancelled",
        message=reason_text("cancelled"),
        processed_at=timezone.now(),
    )


def _process(job: BulkJob, row_id: int) -> None:
    """One organisation, in one transaction (row lock, access check, change, outcome)."""
    action = get_action(job.action)
    with transaction.atomic():
        row = BulkJobRow.objects.select_for_update().select_related("organisation").get(pk=row_id)
        if row.outcome != RowOutcome.PENDING:
            return  # finished by an earlier attempt: never applied twice
        organisation = row.organisation
        allowed = directory_scope(job.created_by, job.practice).filter(
            organisation=organisation
        ).exists() and has_practice_perm(job.created_by, job.practice, action.practice_permission)
        ctx = Context(organisation, job.practice, job.created_by, job.params, {"job": job})
        try:
            with transaction.atomic(), _attributed(job):
                line = evaluate(action, ctx, allowed, write=True)
                if line.status == "change":
                    _audit(job, organisation, line.before, line.after)
        except Exception as exc:  # noqa: BLE001 — one organisation's failure is its outcome
            row.outcome, row.reason = RowOutcome.FAILED, "error"
            row.message = reason_text("error")[:500]
            row.before, row.after = {}, {"error": type(exc).__name__}
        else:
            if line.status == "skipped":
                row.outcome, row.reason = RowOutcome.SKIPPED, line.reason
                row.message = reason_text(line.reason)[:500]
            elif line.status == "no_change":
                row.outcome, row.reason = RowOutcome.SKIPPED, "no_change"
                row.message = str(_no_change_text())
            else:
                row.outcome, row.reason, row.message = RowOutcome.SUCCEEDED, "", ""
            row.before, row.after = line.before, line.after
        row.processed_at = timezone.now()
        row.save(update_fields=["outcome", "reason", "message", "before", "after", "processed_at"])


def report_progress(done: int, total: int | None = None) -> None:
    """The job tray's progress — when running as the background job (not when called inline)."""
    if current_job() is not None:
        _job_progress(done, total)


@contextmanager
def _attributed(job: BulkJob) -> Iterator[None]:
    """Every audit event of the row — the services' own and ``bulk.<action>.applied`` — names the
    person who started the job (not "System") and carries ``bulk_job_id`` (V-03-T11)."""
    from numo9.audit.context import audit_context, user_label
    from numo9.audit.models import ActorKind

    with audit_context(
        kind=ActorKind.USER,
        user=job.created_by,
        label=user_label(job.created_by),
        meta={"bulk_job_id": str(job.public_id), "bulk_action": job.action},
    ):
        yield


def _audit(job: BulkJob, organisation: Any, before: dict[str, Any], after: dict[str, Any]) -> None:
    from numo9.audit.service import record

    record(
        f"bulk.{job.action}.applied",
        organisation=organisation,
        object_type="tenancy.Organisation",
        object_id=str(organisation.public_id),
        object_label=organisation.name,
        changes={field: [before.get(field), value] for field, value in after.items()},
        meta={"bulk_job_id": str(job.public_id), "bulk_action": job.action},
        actor=job.created_by,
    )


def _no_change_text() -> str:
    from django.utils.translation import gettext

    return gettext("Already as asked: nothing to change.")


def execute(job: BulkJob) -> dict[str, int]:
    """Run (or resume) ``job`` until every row has an outcome."""
    BulkJob.objects.filter(pk=job.pk, status=BulkStatus.QUEUED).update(
        status=BulkStatus.RUNNING, started_at=timezone.now()
    )
    job.refresh_from_db()
    pending = list(
        job.rows.filter(outcome=RowOutcome.PENDING)
        .order_by("position")
        .values_list("pk", flat=True)
    )
    done = job.total - len(pending)
    for row_id in pending:
        if BulkJob.objects.filter(pk=job.pk, cancel_requested_at__isnull=False).exists():
            _cancel_rest(job)
            break
        _process(job, row_id)
        done += 1
        report_progress(done, job.total)
    cancelled = BulkJob.objects.filter(pk=job.pk, cancel_requested_at__isnull=False).exists()
    if cancelled:
        _cancel_rest(job)
    BulkJob.objects.filter(pk=job.pk).update(
        status=BulkStatus.CANCELLED if cancelled else BulkStatus.COMPLETED,
        finished_at=timezone.now(),
    )
    job.refresh_from_db()
    return job.counts()


@platform_job(name=RUN_JOB, queue=DEFAULT, atomic=False)
def run_bulk_job(*, bulk_job: str) -> dict[str, int]:
    return execute(BulkJob.objects.get(public_id=bulk_job))
