"""Organisation-scoped Celery tasks (A-01-T07).

A background job has no request, so nothing sets the tenant context for it. Every task that
reads or writes organisation data uses ``OrgTask`` as its base, which

1. **refuses to enqueue** a call without an explicit ``org_id`` keyword argument (the
   organisation's public UUID) — ``OrgIdRequired`` is raised in the caller, nothing is sent;
2. **refuses to run** a message without one (a message sent by name, or by an old producer):
   the task fails with ``OrgIdRequired`` and is not retried;
3. loads the organisation (``UnknownOrganisation`` if it doesn't exist) and runs the task
   body inside ``org_context(organisation, practice)``, so ``OrgScopedManager`` queries and
   the RLS setting ``app.current_org`` (A-01-T12) are scoped to it; the context is restored
   afterwards, so a worker thread never carries one job's organisation into the next.

The task body receives ``org_id`` (as a string). ``practice_id`` (optional) sets the acting
practice the way the request middleware does; it is not passed to the body (read it with
``acting_practice()``).
The organisation is looked up again for every run — never cached — so a job runs with the
organisation as it is now.

    @org_task(queue=queues.DEFAULT)
    def send_trial_reminder(*, org_id: str, days_left: int) -> None:
        organisation = current_org()            # the organisation of org_id
        ...

    send_trial_reminder.delay(org_id=str(organisation.public_id), days_left=3)

Platform tasks that hold no organisation's data (``numo9.jobs.ping``) use plain
``shared_task``. A-08-T03 builds the job base class (idempotency, JobRun) on this one.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from celery import Task, shared_task

from .context import TenantContextMissing, org_context
from .models import Organisation, Practice

ORG_ID = "org_id"
PRACTICE_ID = "practice_id"


class OrgIdRequired(TenantContextMissing):
    """An organisation-scoped task was enqueued or run without a valid ``org_id``."""


class UnknownOrganisation(LookupError):
    """``org_id`` names no organisation (deleted, or a wrong id)."""


def _public_id(task_name: str, kwargs: dict[str, Any], key: str, required: bool) -> str | None:
    value = kwargs.get(key)
    if value is None or value == "":
        if required:
            raise OrgIdRequired(
                f"Task {task_name} is organisation-scoped: pass {key}=<organisation public id> "
                "as a keyword argument."
            )
        return None
    try:
        return str(uuid.UUID(str(value)))
    except ValueError as exc:
        raise OrgIdRequired(f"Task {task_name}: {key} must be a UUID, got {value!r}.") from exc


def _normalised_kwargs(task_name: str, kwargs: dict[str, Any] | None) -> dict[str, Any]:
    """The task's kwargs with ``org_id`` (and ``practice_id``) validated and as strings (JSON)."""
    clean = dict(kwargs or {})
    clean[ORG_ID] = _public_id(task_name, clean, ORG_ID, required=True)
    practice = _public_id(task_name, clean, PRACTICE_ID, required=False)
    if practice is not None:
        clean[PRACTICE_ID] = practice
    return clean


class OrgTask(Task):  # type: ignore[misc]  # celery is untyped
    """Base class of every organisation-scoped task (see the module docstring)."""

    abstract = True
    #: A message without org_id is a programming error: never retry it automatically.
    throws = (OrgIdRequired, UnknownOrganisation)

    def apply_async(
        self,
        args: Any = None,
        kwargs: dict[str, Any] | None = None,
        **options: Any,
    ) -> Any:
        return super().apply_async(args, _normalised_kwargs(self.name, kwargs), **options)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        clean = _normalised_kwargs(self.name, kwargs)
        organisation = Organisation.objects.filter(public_id=clean[ORG_ID]).first()
        if organisation is None:
            raise UnknownOrganisation(f"Task {self.name}: no organisation {clean[ORG_ID]}.")
        practice = None
        practice_id = clean.pop(PRACTICE_ID, None)  # context only: read it with acting_practice()
        if practice_id:
            practice = Practice.objects.filter(public_id=practice_id).first()
            if practice is None:
                raise UnknownOrganisation(f"Task {self.name}: no practice {practice_id}.")
        with org_context(organisation, practice):
            return super().__call__(*args, **clean)


def org_task(*args: Any, **options: Any) -> Callable[..., Any]:
    """``shared_task`` with ``OrgTask`` as base: ``@org_task(queue="default")``."""
    options.setdefault("base", OrgTask)
    if not issubclass(options["base"], OrgTask):
        raise TypeError("org_task() base must be OrgTask or a subclass of it.")
    decorator: Callable[..., Any] = shared_task(*args, **options)
    return decorator
