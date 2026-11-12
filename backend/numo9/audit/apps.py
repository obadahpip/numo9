from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Audit log and record history (A-04)."""

    name = "numo9.audit"
    label = "audit"
    verbose_name = "Audit log"

    def ready(self) -> None:
        from numo9.rbac.audit import rbac_changed

        from .receivers import store_rbac_change

        # Role, assignment, limit and access-request changes (A-03-T15) land in the log.
        rbac_changed.connect(store_rbac_change, dispatch_uid="numo9.audit.rbac")
        # Sign-in, sign-out, failed sign-in and 2FA changes (A-02-T14).
        from . import auth_events

        auth_events.connect()
