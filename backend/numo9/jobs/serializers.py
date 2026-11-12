"""What a job looks like in the API (A-08-T06): job tray and, with more fields, the console."""

from __future__ import annotations

from typing import Any

from celery import current_app
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import RETRYABLE, JobRun, JobStatus

GENERIC_LABEL = _("Background job")


def job_label(task_name: str) -> str:
    """The job type's name for people: the task's ``label`` option, else "Background job"."""
    task = current_app.tasks.get(task_name)
    label = getattr(task, "label", None)
    return str(label or GENERIC_LABEL)


class JobProgressSerializer(serializers.Serializer[Any]):
    done = serializers.IntegerField()
    total = serializers.IntegerField(allow_null=True)
    percent = serializers.IntegerField(allow_null=True, help_text="0–100; null while unknown")
    message = serializers.CharField(allow_blank=True)


class JobErrorSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    message = serializers.CharField()


class JobSerializer(serializers.ModelSerializer[JobRun]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    type = serializers.CharField(source="task_name", read_only=True)
    label = serializers.SerializerMethodField()  # type: ignore[assignment]  # field named label
    status = serializers.ChoiceField(choices=JobStatus.choices, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    progress = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()
    can_retry = serializers.SerializerMethodField()

    class Meta:
        model = JobRun
        fields = [
            "id",
            "type",
            "label",
            "status",
            "status_label",
            "progress",
            "result_url",
            "error",
            "can_retry",
            "attempts",
            "created_at",
            "started_at",
            "finished_at",
            "next_retry_at",
        ]
        read_only_fields = fields

    def get_label(self, run: JobRun) -> str:
        return job_label(run.task_name)

    @extend_schema_field(JobProgressSerializer)
    def get_progress(self, run: JobRun) -> dict[str, Any]:
        return {
            "done": run.progress_done,
            "total": run.progress_total,
            "percent": run.progress_percent,
            "message": run.progress_message,
        }

    @extend_schema_field(JobErrorSerializer(allow_null=True))
    def get_error(self, run: JobRun) -> dict[str, str] | None:
        if not run.error_code:
            return None
        return {"code": run.error_code, "message": run.error_message}

    def get_can_retry(self, run: JobRun) -> bool:
        return run.status in RETRYABLE


def job_list_data(runs: list[JobRun]) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = JobSerializer(runs, many=True).data  # type: ignore[assignment]
    return [dict(item) for item in data]
