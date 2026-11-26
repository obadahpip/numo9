"""Recurring documents — the shared generator (D-04-T05, reused by E-03-T02 for bills).

``RecurringGenerator`` turns the due occurrences of a template (a recurring invoice, a recurring
bill) into documents, **exactly once per occurrence**, whatever happens to the workers:

- the schedule is the recurring-journal engine (C-04-T05: RFC 5545 rule from the start date, a
  29th–31st clamped to the month's last day) between the template's start and end dates, in the
  organisation's own time zone (the hourly job asks each organisation for its local date);
- ``run_occurrence(template, day)`` locks the template row (``SELECT … FOR UPDATE``), finds or
  inserts the **run row** — unique per (template, occurrence date), the idempotency row — and only
  the insert that wins keeps its document. Everything (document, run row, audit) commits in one
  transaction: a worker that dies half-way leaves nothing, and the next tick (or a second worker
  waiting on the lock) finds the row and does nothing;
- ``skip_reason(template, day)`` (D-04-T06) — a skipped occurrence is recorded as a ``skipped`` run
  with its reason (``code`` / ``message``), an audit event ``<app>.<template>.skipped`` and a
  notification to the template's owner (on commit) — never generated on another date; a skipped
  date isn't retried;
- ``build(template, day)`` makes the draft document; ``finish(template, document)`` applies the
  template's mode (draft / approve / approve and send). A refused approval or send keeps the
  document (a draft, or approved but not sent): the run is ``created`` with the refusal's code,
  and the owner is told;
- ``generate_due(organisation, today)`` runs every due occurrence (``next_run`` ≤ today) oldest
  first, then moves ``next_run`` to the first occurrence after today (``None``: the schedule is
  over — the owner is told once that it ended) and ``last_run`` to the latest generated date;
- ``generate_all(now)`` — the hourly job: every organisation on its own date. A template that
  fails unexpectedly doesn't stop the others; the job fails at the end (visible in the job
  dashboard, A-08) and its rerun is safe;
- ``replay(organisation, start, end)`` — the support tool (``manage.py replay_ticks``, D-04-T11):
  the occurrences of those days run again through ``run_occurrence``; those that already ran
  create nothing.

A subclass names its models and hooks::

    class RecurringInvoiceGenerator(RecurringGenerator):
        template_model = RecurringInvoiceTemplate
        run_model = RecurringInvoiceRun
        job = "numo9.sales.recurring_invoices"
        lock_module = LockModule.AR
        event_prefix = "sales.recurring_invoice"

        def build(self, template, day): ...
        def finish(self, template, document): ...
        def link(self, template): ...
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from functools import partial
from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils.translation import gettext as _
from rest_framework.exceptions import APIException

from numo9.ledger import recurring as engine

from .models import RecurringRunStatus

logger = logging.getLogger("numo9.documents.recurring")

#: The refusals a step of generation may meet (ledger and validation errors, lock / closed-period
#: and catalogue 4xx). Anything else is a bug: the occurrence's transaction rolls back.
REFUSALS: tuple[type[Exception], ...] = (ValidationError, APIException)


@dataclass(frozen=True)
class Skip:
    """Why an occurrence isn't generated; ``notify``: tell the template's owner."""

    code: str
    message: str
    notify: bool = True


@dataclass
class Outcome:
    """What ``finish`` did: the document, and a refusal of the mode's next step if any."""

    document: Any
    code: str = ""
    message: str = ""
    notify: bool = False


class GenerationFailed(RuntimeError):
    """Some templates failed unexpectedly during a tick (logged); the others were generated."""


def reason(error: BaseException) -> tuple[str, str]:
    """A refusal's code and message: ledger / validation errors, lock and closed-period 409s
    (``{"detail", "code"}``), catalogue errors (a message with its code)."""
    detail = getattr(error, "detail", None)
    if isinstance(detail, dict):
        code = detail.get("code") or getattr(error, "default_code", "") or "invalid"
        return str(code), str(detail.get("detail") or error)
    if isinstance(error, APIException):
        code = getattr(detail, "code", None) or getattr(error, "default_code", "") or "invalid"
        return str(code), str(detail if detail is not None else error)
    code = getattr(error, "code", None)
    if not code and isinstance(error, ValidationError):
        if hasattr(error, "error_dict"):
            items = [item for items in error.error_dict.values() for item in items]
        else:
            items = list(getattr(error, "error_list", []))
        code = next((item.code for item in items if getattr(item, "code", None)), None)
    messages = getattr(error, "messages", None) or [str(error)]
    return str(code or "invalid"), " ".join(str(m) for m in messages)


class RecurringGenerator:
    """The generator of one kind of recurring document (module docstring)."""

    template_model: ClassVar[Any]
    run_model: ClassVar[Any]
    #: The Celery job's name (audit meta; ``CELERY_BEAT_SCHEDULE`` key).
    job: ClassVar[str]
    #: The lock date module the documents post to (``ar`` for invoices, ``ap`` for bills).
    lock_module: ClassVar[str]
    #: Notification events ``<prefix>.skipped`` / ``.failed`` / ``.ended``.
    event_prefix: ClassVar[str]

    # ---- hooks -----------------------------------------------------------------------------

    def build(self, template: Any, day: dt.date) -> Any:
        """The draft document of the occurrence on ``day`` (saved, figures calculated)."""
        raise NotImplementedError

    def finish(self, template: Any, document: Any) -> Outcome:
        """Apply the template's mode to the new draft (draft / approve / approve and send)."""
        raise NotImplementedError

    def link(self, template: Any) -> str:
        """The template's page in the app (notifications)."""
        raise NotImplementedError

    def contact_of(self, template: Any) -> Any:
        return template.contact

    def skip_reason(self, template: Any, day: dt.date) -> Skip | None:
        """D-04-T06: paused → skipped (logged, not notified: the owner paused it); an archived
        or deleted contact; a date in a locked or closed period (``assert_can_post`` of the
        documents' lock module, for drafts too — never dated elsewhere)."""
        from numo9.ledger.periods import assert_can_post

        if template.paused:
            return Skip(
                "documents.recurring.paused",
                _("The template was paused on this date."),
                notify=False,
            )
        contact = self.contact_of(template)
        if contact is None or contact.deleted_at is not None or contact.is_archived:
            return Skip(
                "documents.recurring.contact_archived",
                _("%(contact)s is archived: nothing was created for this date.")
                % {"contact": getattr(contact, "display_name", "") or _("The contact")},
            )
        try:
            assert_can_post(template.organisation, day, None, self.lock_module)
        except REFUSALS as error:
            code, message = reason(error)
            return Skip(code, message)
        return None

    # ---- schedule --------------------------------------------------------------------------

    def schedule(
        self,
        template: Any,
        *,
        after: dt.date | None = None,
        until: dt.date | None = None,
        limit: int | None = None,
    ) -> list[dt.date]:
        return engine.occurrences(
            template.rrule,
            template.start_date,
            template.end_date,
            after=after,
            until=until,
            limit=limit,
        )

    # ---- one occurrence --------------------------------------------------------------------

    def _action(self, template: Any, verb: str) -> str:
        meta = self.template_model._meta
        return f"{meta.app_label}.{meta.model_name}.{verb}"

    def run_occurrence(self, template: Any, day: dt.date) -> Any:
        """Generate the occurrence on ``day`` once (module docstring); ``None`` when it already
        ran (another worker, an earlier tick, a replay)."""
        from numo9.audit import service as audit

        run_model = self.run_model
        with transaction.atomic():
            locked = self.template_model._base_manager.select_for_update().get(pk=template.pk)
            if run_model._base_manager.filter(template=locked, occurrence_date=day).exists():
                return None
            skip = self.skip_reason(locked, day)
            outcome: Outcome | None = None
            if skip is None:
                try:
                    with transaction.atomic():
                        document = self.build(locked, day)
                except REFUSALS as error:
                    skip = Skip(*reason(error))
                else:
                    outcome = self.finish(locked, document)
            try:
                with transaction.atomic():
                    run = run_model._base_manager.create(
                        organisation=locked.organisation,
                        template=locked,
                        occurrence_date=day,
                        template_version=locked.version,
                        status=RecurringRunStatus.SKIPPED
                        if outcome is None
                        else RecurringRunStatus.CREATED,
                        document=None if outcome is None else outcome.document,
                        code=skip.code if skip else (outcome.code if outcome else ""),
                        message=skip.message if skip else (outcome.message if outcome else ""),
                    )
            except IntegrityError:  # another worker won the insert: its document stands
                transaction.set_rollback(True)
                return None
            meta = {"date": day.isoformat(), "job": self.job, "version": locked.version}
            if skip is not None:
                audit.record(
                    self._action(locked, "skipped"),
                    obj=locked,
                    changes={},
                    meta={**meta, "code": skip.code, "reason": skip.message},
                    actor=None,
                )
                if skip.notify:
                    self._notify_on_commit(locked, "skipped", day, skip.message)
            else:
                assert outcome is not None  # noqa: S101 — not skipped: finished
                audit.record(
                    self._action(locked, "generated"),
                    obj=locked,
                    changes={},
                    meta={
                        **meta,
                        "document": str(outcome.document.public_id),
                        "code": outcome.code,
                    },
                    actor=None,
                )
                if outcome.notify:
                    self._notify_on_commit(locked, "failed", day, outcome.message)
            return run

    # ---- notifications ---------------------------------------------------------------------

    def owners(self, template: Any) -> list[Any]:
        """Who hears about the template: its author while still a member, else the
        organisation's owners and admins."""
        from numo9.tenancy.models import OrganisationMember

        members = OrganisationMember.objects.filter(organisation=template.organisation)
        author = template.created_by
        if author is not None and members.filter(user=author).exists():
            return [author]
        return [m.user for m in members.filter(role__in=("owner", "admin")).select_related("user")]

    def _notify_on_commit(self, template: Any, kind: str, day: dt.date | None, why: str) -> None:
        transaction.on_commit(partial(self._notify, template, kind, day, why))

    def _notify(self, template: Any, kind: str, day: dt.date | None, why: str) -> None:
        from numo9.notifications.services import notify
        from numo9.tenancy.context import org_context

        with org_context(template.organisation):
            recipients = self.owners(template)
        if not recipients:
            return
        notify(
            f"{self.event_prefix}.{kind}",
            recipients,
            organisation=template.organisation,
            params={
                "name": template.name,
                "date": day.isoformat() if day else "",
                "reason": why,
            },
            link=self.link(template),
        )

    # ---- due occurrences -------------------------------------------------------------------

    def generate_template(self, template: Any, today: dt.date) -> list[Any]:
        """The template's due occurrences up to ``today``, then ``next_run`` / ``last_run``."""
        from numo9.audit import service as audit

        runs: list[Any] = []
        start = template.next_run
        if start is not None:
            for day in self.schedule(template, after=start - dt.timedelta(days=1), until=today):
                run = self.run_occurrence(template, day)
                if run is not None:
                    runs.append(run)
        following = self.schedule(template, after=max(today, start or today), limit=1)
        upcoming = following[0] if following else None
        last = self.run_model._base_manager.filter(
            template_id=template.pk, status=RecurringRunStatus.CREATED
        ).aggregate(last=Max("occurrence_date"))["last"]
        moved = self.template_model._base_manager.filter(
            pk=template.pk, next_run=template.next_run
        ).update(next_run=upcoming, last_run=last)
        if moved and template.next_run is not None and upcoming is None:
            # The schedule is over (its end date, or an end date moved before the next run):
            # the owner hears it once — only the worker whose update moved next_run says so.
            with transaction.atomic():
                audit.record(
                    self._action(template, "ended"),
                    obj=template,
                    changes={},
                    meta={"job": self.job, "end_date": str(template.end_date or "")},
                    actor=None,
                )
                self._notify_on_commit(
                    template, "ended", template.end_date, _("The schedule has no more dates.")
                )
        return runs

    def due(self, organisation: Any, today: dt.date) -> Any:
        return self.template_model.objects.filter(
            organisation=organisation,
            deleted_at__isnull=True,
            next_run__isnull=False,
            next_run__lte=today,
        ).order_by("next_run", "pk")

    def generate_due(self, organisation: Any, today: dt.date) -> list[Any]:
        """Every due occurrence of the organisation's templates (a paused template's are
        recorded as skipped: the history shows them, and resuming doesn't bill them), oldest
        first."""
        from numo9.tenancy.context import org_context

        runs: list[Any] = []
        with org_context(organisation):
            for template in self.due(organisation, today):
                runs.extend(self.generate_template(template, today))
        return runs

    def generate_all(self, now: dt.datetime | None = None) -> dict[str, int]:
        """The hourly job (module docstring): ``{"created", "skipped", "failed"}``."""
        from django.utils import timezone

        from numo9.orgsettings.locks import local_date
        from numo9.tenancy.context import org_context
        from numo9.tenancy.models import Organisation

        now = now or timezone.now()
        counts = {"created": 0, "skipped": 0, "failed": 0}
        for organisation in Organisation.objects.order_by("pk").iterator():
            today = local_date(organisation, now)
            with org_context(organisation):
                templates = list(self.due(organisation, today))
                for template in templates:
                    try:
                        runs = self.generate_template(template, today)
                    except Exception:  # noqa: BLE001 — one template must not stop the others
                        logger.exception(
                            "recurring.generation_failed",
                            extra={"job": self.job, "template": str(template.public_id)},
                        )
                        counts["failed"] += 1
                        continue
                    for run in runs:
                        counts[run.status] += 1
        if counts["failed"]:
            raise GenerationFailed(
                f"{counts['failed']} recurring template(s) failed in {self.job}: see the logs "
                f"({counts['created']} created, {counts['skipped']} skipped)."
            )
        return counts

    # ---- support -----------------------------------------------------------------------------

    def replay(
        self,
        organisation: Any,
        start: dt.date,
        end: dt.date | None = None,
        *,
        dry_run: bool = False,
    ) -> list[tuple[Any, dt.date, Any]]:
        """Run the occurrences dated ``start``…``end`` (one day by default) of the organisation's
        templates again: ``(template, date, run or None)`` — ``None`` when it already ran (or, in
        a dry run, what would run). Dates before a template was created are never replayed (a
        schedule that started in the past doesn't bill the months before it existed), and
        ``next_run`` isn't moved back."""
        from numo9.orgsettings.locks import local_date
        from numo9.tenancy.context import org_context

        end = end or start
        out: list[tuple[Any, dt.date, Any]] = []
        with org_context(organisation):
            templates = self.template_model.objects.filter(
                organisation=organisation, deleted_at__isnull=True
            ).order_by("pk")
            for template in templates:
                created = local_date(organisation, template.created_at)
                after = max(start, created) - dt.timedelta(days=1)
                for day in self.schedule(template, after=after, until=end):
                    if dry_run:
                        done = self.run_model._base_manager.filter(
                            template=template, occurrence_date=day
                        ).first()
                        out.append((template, day, done))
                        continue
                    out.append((template, day, self.run_occurrence(template, day)))
        return out
