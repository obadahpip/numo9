"""Tax settings history (G-06-T06): one history for every tax object, with attribution.

- ``TAX_OBJECT_TYPES`` — tax settings, codes, components and their links, and the statutory
  registrations (BN, program accounts, QST, PST). The audit log serves them together as
  ``?scope=tax`` (``GET audit/events?scope=tax``), the history drawer of the tax settings page.
- **Attribution is enforced** (``attribute``, run on every audit event before it is sealed): an
  event on a tax object names a person, or the job that wrote it with the job's id. A background
  job already carries its run id (A-08); any other system write — a seed, a management command,
  a Celery task that isn't a job — gets the id of the process run that wrote it
  (``meta.job = {"id", "task"}``), so no history row is "System" alone.
- ``tax_history(organisation)`` — the rows, newest first: who (person, or job and its id), what,
  old → new.
"""

from __future__ import annotations

import uuid
from typing import Any

#: Model labels of the tax objects (the history's scope).
TAX_OBJECT_TYPES: tuple[str, ...] = (
    "tax.TaxSettings",
    "tax.TaxCode",
    "tax.TaxComponent",
    "tax.TaxCodeComponent",
    "tax.TaxAuthority",
    "orgsettings.TaxRegistration",
)

#: One id per process run, for system writes that aren't background jobs (seeds, commands).
PROCESS_RUN = str(uuid.uuid4())


def has_job_id(meta: Any) -> bool:
    job = (meta or {}).get("job") if isinstance(meta, dict) else None
    return isinstance(job, dict) and bool(job.get("id"))


def attribute(event: Any) -> None:
    """Audit hook: a tax event without a person gets its run's job id (module docstring)."""
    if event.object_type not in TAX_OBJECT_TYPES or event.actor_user_id is not None:
        return
    meta = dict(event.meta or {})
    if has_job_id(meta):
        return
    task = meta.get("task") or meta.get("command") or event.actor_label or "system"
    meta["job"] = {"id": PROCESS_RUN, "task": str(task)}
    event.meta = meta


def who(event: Any) -> dict[str, Any]:
    if event.actor_user_id is not None and event.actor_user is not None:
        return {
            "kind": "user",
            "id": str(event.actor_user.public_id),
            "name": event.actor_label or event.actor_user.name,
        }
    job = (event.meta or {}).get("job") or {}
    return {"kind": "job", "id": str(job.get("id", "")), "name": event.actor_label}


def tax_history(organisation: Any, limit: int = 50) -> list[dict[str, Any]]:
    from numo9.audit.models import AuditEvent
    from numo9.tenancy.context import org_context

    with org_context(organisation):
        events = (
            AuditEvent.objects.filter(object_type__in=TAX_OBJECT_TYPES)
            .select_related("actor_user")
            .order_by("-created_at", "-pk")[:limit]
        )
        return [
            {
                "at": event.created_at.isoformat(),
                "action": event.action,
                "record": {
                    "type": event.object_type,
                    "id": event.object_id,
                    "label": event.object_label,
                },
                "by": who(event),
                "changes": event.changes or {},
                "reason": (event.meta or {}).get("reason", ""),
            }
            for event in events
        ]


def register_history() -> None:
    from numo9.audit.query import register_scope
    from numo9.audit.service import BEFORE_SEAL

    register_scope("tax", TAX_OBJECT_TYPES)
    if attribute not in BEFORE_SEAL:
        BEFORE_SEAL.append(attribute)
