from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Audit log and record history (A-04)."""

    name = "numo9.audit"
    label = "audit"
    verbose_name = "Audit log"
