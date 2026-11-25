"""Bulk statement runs (D-07-T08): one statement per chosen contact, emailed as a PDF — the B-02
engine and sender (``build_statement``, ``send_statement``) for many contacts at once.

``create_run(organisation, kind, as_at, user, start=…, contacts=…, include_zero=…)`` keeps a
**draft** ``StatementRun``; ``preview_run(run)`` lists, without sending, each contact the run would
reach — the amount due, the aging, the recipients — or why it is skipped:

- ``statements_off`` — the contact's statement preference is not email (B-01: none, post, portal);
- ``no_balance`` — nothing owed as at the date (unless ``include_zero``);
- ``no_recipient`` — no one at the contact marked "include in emails".

With no ``contacts`` chosen the run reaches every customer with a balance whose preference is
email; chosen contacts are taken as chosen (their preference still applies).

``execute_run(run, user)`` sends: **now** for up to ``ASYNC_THRESHOLD`` (20) contacts, else as the
job ``numo9.contacts.statement_run`` (A-08). Each contact is sent in its own savepoint — a failure
is recorded (``failed``) and the run goes on; each statement sent is a ``StatementSend`` in the
contact's history (B-02-T06), with its PDF and email messages. The run ends **Sent** with its
counts and per-contact ``results``.

The amount due of each statement is the contact's AR aging total (``tests/test_statement_run.py``,
data validation).
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.jobs.queues import REPORTS
from numo9.jobs.runtime import current_job, org_job, report_progress, start_job
from numo9.tenancy.context import org_context

from .models import (
    Contact,
    ContactRole,
    StatementPreference,
    StatementRun,
    StatementRunStatus,
    StatementSendKind,
)
from .statement_engine import build_statement
from .statements import StatementError, send_statement, statement_recipients

ASYNC_THRESHOLD = 20
JOB = "numo9.contacts.statement_run"
ZERO = Decimal("0.00")


class StatementRunRefused(ValidationError):
    """The run can't be created or sent (bad dates, not a draft)."""


def _refused(message: str, code: str) -> StatementRunRefused:
    return StatementRunRefused(message, code=code)


def create_run(
    organisation: Any,
    kind: str,
    as_at: dt.date,
    user: Any,
    *,
    start: dt.date | None = None,
    contacts: list[str] | None = None,
    include_zero: bool = False,
) -> StatementRun:
    if kind not in StatementSendKind.values:
        raise _refused(_("Choose an outstanding or an activity statement."), "contacts.run.kind")
    if kind == StatementSendKind.ACTIVITY and (start is None or start > as_at):
        raise _refused(
            _("An activity statement needs a start date on or before its end date."),
            "contacts.run.period",
        )
    chosen = []
    for value in contacts or []:
        try:
            chosen.append(str(uuid.UUID(str(value))))
        except ValueError:
            raise _refused(_("Choose contacts from the list."), "contacts.run.contacts") from None
    with org_context(organisation):
        if chosen:
            found = {
                str(pid)
                for pid in Contact.objects.filter(public_id__in=chosen).values_list(
                    "public_id", flat=True
                )
            }
            if found != set(chosen):
                raise _refused(_("Choose contacts from the list."), "contacts.run.contacts")
        run: StatementRun = StatementRun.objects.create(
            organisation=organisation,
            kind=kind,
            as_at=as_at,
            period_start=start if kind == StatementSendKind.ACTIVITY else None,
            contacts=list(dict.fromkeys(chosen)),
            include_zero=include_zero,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        return run


def _contacts(run: StatementRun) -> list[Contact]:
    rows = Contact.objects.filter(deleted_at__isnull=True)
    if run.contacts:
        rows = rows.filter(public_id__in=run.contacts)
    else:
        rows = rows.filter(roles__contains=[ContactRole.CUSTOMER])
    return list(rows.order_by("display_name", "pk"))


def _document(run: StatementRun, contact: Contact) -> Any:
    return build_statement(
        contact,
        run.kind,
        run.as_at,
        start=run.period_start,
        side="receivables",
    )


def _plan_one(run: StatementRun, contact: Contact) -> tuple[dict[str, Any], Any]:
    row: dict[str, Any] = {
        "contact": str(contact.public_id),
        "name": contact.display_name,
        "currency": contact.currency,
    }
    if contact.statement_pref != StatementPreference.EMAIL:
        return {**row, "status": "skipped", "reason": "statements_off"}, None
    document = _document(run, contact)
    row["amount_due"] = f"{document.amount_due:.2f}"
    row["aging"] = {k: f"{v:.2f}" for k, v in document.aging.items()}
    if document.amount_due == ZERO and not run.include_zero:
        return {**row, "status": "skipped", "reason": "no_balance"}, None
    recipients = statement_recipients(contact)
    row["recipients"] = recipients
    if not recipients:
        return {**row, "status": "skipped", "reason": "no_recipient"}, None
    return {**row, "status": "ready"}, document


def preview_run(run: StatementRun) -> list[dict[str, Any]]:
    """What the run would send, contact by contact (module docstring)."""
    with org_context(run.organisation):
        return [_plan_one(run, contact)[0] for contact in _contacts(run)]


def _counts(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        f"{status}_count": sum(1 for r in results if r["status"] == status)
        for status in ("sent", "skipped", "failed")
    }


def run_statements(run: StatementRun, user: Any) -> StatementRun:
    """Send every statement of the run (each contact in a savepoint)."""
    person = user if getattr(user, "is_authenticated", False) else None
    with org_context(run.organisation):
        run.refresh_from_db()
        if run.status not in (StatementRunStatus.DRAFT, StatementRunStatus.RUNNING):
            return run
        StatementRun.objects.filter(pk=run.pk).update(
            status=StatementRunStatus.RUNNING,
            run_by=person,
            run_at=timezone.now(),
            updated_at=timezone.now(),
        )
        contacts = _contacts(run)
        results: list[dict[str, Any]] = []
        try:
            for done, contact in enumerate(contacts, start=1):
                row, document = _plan_one(run, contact)
                if document is not None:
                    try:
                        with transaction.atomic():
                            send = send_statement(contact, document, user=person)
                        row = {**row, "status": "sent", "send": str(send.public_id)}
                    except StatementError:
                        row = {**row, "status": "skipped", "reason": "no_recipient"}
                    except Exception as error:  # a PDF or storage failure: this contact only
                        row = {**row, "status": "failed", "reason": str(error)[:300]}
                results.append(row)
                StatementRun.objects.filter(pk=run.pk).update(
                    results=results, **_counts(results), updated_at=timezone.now()
                )
                if current_job() is not None:
                    report_progress(done, len(contacts))
        except Exception:
            StatementRun.objects.filter(pk=run.pk).update(
                status=StatementRunStatus.FAILED,
                results=results,
                **_counts(results),
                updated_at=timezone.now(),
            )
            raise
        StatementRun.objects.filter(pk=run.pk).update(
            status=StatementRunStatus.DONE,
            results=results,
            **_counts(results),
            updated_at=timezone.now(),
        )
        run.refresh_from_db()
        from numo9.audit.service import record

        record(
            "contacts.statement_run.sent",
            obj=run,
            meta={
                "kind": run.kind,
                "as_at": run.as_at.isoformat(),
                "sent": run.sent_count,
                "skipped": run.skipped_count,
                "failed": run.failed_count,
            },
            actor=person,
        )
        return run


@org_job(name=JOB, queue=REPORTS, max_retries=0, atomic=False)
def statement_run_job(*, org_id: str, run_id: str, user_id: int | None = None) -> dict[str, Any]:
    from numo9.accounts.models import User

    run = StatementRun.objects.get(public_id=run_id)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    done = run_statements(run, user)
    return {"run": str(done.public_id), "sent": done.sent_count, "status": done.status}


def execute_run(run: StatementRun, user: Any) -> StatementRun:
    """Send now (≤ ``ASYNC_THRESHOLD`` contacts) or start the background job."""
    if run.status != StatementRunStatus.DRAFT:
        raise _refused(_("This statement run has been sent already."), "contacts.run.not_draft")
    with org_context(run.organisation):
        count = len(_contacts(run))
        if count <= ASYNC_THRESHOLD:
            return run_statements(run, user)
        with transaction.atomic():
            job = start_job(
                statement_run_job,
                organisation=run.organisation,
                key=f"statement-run:{run.public_id}",
                created_by=user if getattr(user, "is_authenticated", False) else None,
                run_id=str(run.public_id),
                user_id=user.pk if getattr(user, "is_authenticated", False) else None,
            )
            StatementRun.objects.filter(pk=run.pk).update(
                status=StatementRunStatus.RUNNING, job_run=job, updated_at=timezone.now()
            )
        run.refresh_from_db()
        return run
