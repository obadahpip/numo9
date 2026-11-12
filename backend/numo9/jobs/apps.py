from django.apps import AppConfig


class JobsConfig(AppConfig):
    """Background jobs and scheduling (A-08): queues, the worker check task, job runs (T02)."""

    name = "numo9.jobs"
    label = "jobs"
    verbose_name = "Background jobs"
