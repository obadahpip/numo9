from typing import Any

from django.apps import AppConfig


class JobsConfig(AppConfig):
    """Background jobs and scheduling (A-08): queues, the worker check task, job runs (T02)."""

    name = "numo9.jobs"
    label = "jobs"
    verbose_name = "Background jobs"

    def ready(self) -> None:
        # Tenant sweep (A-01-T09): rows of JobRun for the job tray endpoints, started by the
        # organisation's owner (a person only sees the jobs they started).
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["jobs.JobRun"] = _sweep_job_run


def _sweep_job_run(organisation: Any) -> Any:
    import uuid

    from numo9.tenancy.models import OrganisationMember, OrganisationRole

    from .models import JobRun, JobStatus

    owner = (
        OrganisationMember.objects.filter(organisation=organisation, role=OrganisationRole.OWNER)
        .select_related("user")
        .first()
    )
    return JobRun.platform_runs.create(
        organisation=organisation,
        task_name="numo9.sweep.job",
        status=JobStatus.FAILED,  # retryable, so every verb has something to answer
        error_code="job.failed",
        idempotency_key=f"sweep:{uuid.uuid4()}",
        created_by=owner.user if owner else None,
    )
