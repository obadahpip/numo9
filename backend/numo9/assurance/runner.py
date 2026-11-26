"""The runner (K-09-T05): evaluate the rules, keep the findings, open / reopen / resolve them.

``run(organisation, trigger=…, scope=None)`` — one ``ExceptionRun``: every enabled rule (a
``scope`` runs the *incremental* rules only, for the scope's journals and accounts). Per rule:

1. ``evaluate`` → hits; each hit's fingerprint (rule, subject) is looked up among the rule's
   findings (the latest row per fingerprint);
2. **none** → a new open finding; **open / acknowledged** → refreshed (``last_seen``, amount,
   details, severity); **resolved** → **reopened** (the condition recurs); **false positive** →
   left alone while the amount is the same, a **new finding** when it differs;
3. the rule's open and acknowledged findings it no longer hits — and that it re-checked (a full
   run, or ``rule.covers`` the subject in an incremental run) — are **resolved** automatically.

Re-running therefore never duplicates (the database also allows one active finding per
fingerprint). Every status change is audited (``assurance.finding.opened`` / ``reopened`` /
``resolved``). A disabled rule is not evaluated and its active findings are resolved on a full
run (the rule was switched off).

Triggers: *on demand* (``start_run``, a background job when asked through the API), *nightly*
(``nightly_job``: every organisation) and *on posting* — ``posted_hook`` (registered in
``numo9.ledger.services.POSTED_HOOKS``) collects the posted journal and its accounts and, when
the transaction commits, starts one incremental job for them (``numo9.assurance.run``, keyed by
the journals so a re-sent message runs once).
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.audit import service as audit
from numo9.jobs.queues import DEFAULT, REPORTS
from numo9.jobs.runtime import org_job, platform_job, start_job
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import (
    ACTIVE_STATUSES,
    ExceptionFinding,
    ExceptionRun,
    FindingStatus,
    RunStatus,
    RunTrigger,
    fingerprint_of,
)
from .rules.base import Context, Hit, Rule, RuleRegistry, Scope, registry, settings_for

logger = logging.getLogger(__name__)

JOB = "numo9.assurance.run"
NIGHTLY_JOB = "numo9.assurance.nightly"


def _audit(finding: ExceptionFinding, verb: str, actor: Any = None, **meta: Any) -> None:
    audit.record(
        f"assurance.finding.{verb}",
        obj=finding,
        object_label=f"{finding.rule_code} · {finding.subject_label or finding.subject_id}",
        changes={},
        meta={
            "rule": finding.rule_code,
            "subject": {"type": finding.subject_type, "id": finding.subject_id},
            "amount": f"{finding.amount:.2f}" if finding.amount is not None else None,
            **meta,
        },
        actor=actor,
    )


def _same_amount(finding: ExceptionFinding, hit: Hit) -> bool:
    if finding.amount is None or hit.amount is None:
        return finding.amount is None and hit.amount is None
    return bool(abs(finding.amount - hit.amount) < 0.005)


def _refresh(finding: ExceptionFinding, hit: Hit, ctx: Context, run: ExceptionRun) -> None:
    finding.severity = ctx.severity
    finding.subject_label = hit.label[:300]
    finding.amount = hit.amount
    finding.details = hit.details
    finding.last_seen = ctx.now
    finding.last_run = run


def _new(rule: Rule, hit: Hit, ctx: Context, run: ExceptionRun, fingerprint: str) -> Any:
    finding = ExceptionFinding(
        organisation=ctx.organisation,
        rule_code=rule.code,
        subject_type=hit.subject_type,
        subject_id=hit.subject_id,
        fingerprint=fingerprint,
        first_seen=ctx.now,
        status=FindingStatus.OPEN,
    )
    _refresh(finding, hit, ctx, run)
    finding.save()
    _audit(finding, "opened", run=str(run.public_id))
    return finding


def resolve(finding: ExceptionFinding, *, now: dt.datetime, actor: Any = None, **meta: Any) -> None:
    """Mark an active finding resolved (the condition is gone) and audit it."""
    finding.status = FindingStatus.RESOLVED
    finding.resolved_at = now
    finding.save(update_fields=["status", "resolved_at", "updated_at"])
    _audit(finding, "resolved", actor, **meta)


def apply_hits(
    rule: Rule, ctx: Context, hits: Iterable[Hit], run: ExceptionRun, counts: Counter[str]
) -> list[ExceptionFinding]:
    """Steps 1–3 of the module docstring for one rule; the active findings it hit."""
    by_print: dict[str, Hit] = {}
    for hit in hits:
        by_print.setdefault(fingerprint_of(rule.code, hit.subject_type, hit.subject_id), hit)
    latest: dict[str, ExceptionFinding] = {}
    if by_print:
        rows = ExceptionFinding.objects.filter(
            rule_code=rule.code, fingerprint__in=list(by_print)
        ).order_by("fingerprint", "-first_seen", "-pk")
        for row in rows:
            latest.setdefault(row.fingerprint, row)
    hit_findings: list[ExceptionFinding] = []
    for fingerprint, hit in by_print.items():
        counts["seen"] += 1
        found = latest.get(fingerprint)
        if found is None:
            hit_findings.append(_new(rule, hit, ctx, run, fingerprint))
            counts["created"] += 1
        elif found.status in ACTIVE_STATUSES:
            _refresh(found, hit, ctx, run)
            found.save()
            hit_findings.append(found)
            counts["updated"] += 1
        elif found.status == FindingStatus.RESOLVED:
            _refresh(found, hit, ctx, run)
            found.status, found.resolved_at = FindingStatus.OPEN, None
            found.ack_by, found.ack_at, found.reason = None, None, ""
            found.save()
            _audit(found, "reopened", run=str(run.public_id))
            hit_findings.append(found)
            counts["reopened"] += 1
        elif _same_amount(found, hit):  # a false positive that recurs as it was
            found.last_seen, found.last_run = ctx.now, run
            found.save(update_fields=["last_seen", "last_run", "updated_at"])
            counts["suppressed"] += 1
        else:  # a false positive recurring with a different amount: a new finding
            hit_findings.append(_new(rule, hit, ctx, run, fingerprint))
            counts["created"] += 1
    gone = ExceptionFinding.objects.filter(rule_code=rule.code, status__in=ACTIVE_STATUSES).exclude(
        fingerprint__in=list(by_print)
    )
    for finding in gone:
        if rule.covers(ctx, finding):
            resolve(finding, now=ctx.now, run=str(run.public_id))
            counts["resolved"] += 1
    return hit_findings


def _switched_off(rule: Rule, ctx: Context, counts: Counter[str]) -> None:
    for finding in ExceptionFinding.objects.filter(rule_code=rule.code, status__in=ACTIVE_STATUSES):
        resolve(finding, now=ctx.now, switched_off=True)
        counts["resolved"] += 1


def run(
    organisation: Organisation,
    *,
    trigger: str = RunTrigger.MANUAL,
    scope: Scope | None = None,
    codes: Sequence[str] | None = None,
    user: Any = None,
    now: dt.datetime | None = None,
    job_run: Any = None,
    rules: RuleRegistry | None = None,
) -> ExceptionRun:
    """Evaluate the organisation's rules (module docstring); the finished run."""
    now = now or timezone.now()
    rules = rules or registry
    with org_context(organisation), transaction.atomic():
        record: ExceptionRun = ExceptionRun.objects.create(
            organisation=organisation,
            trigger=trigger,
            scope=scope.as_dict() if scope is not None else {},
            started_at=now,
            job_run=job_run,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        counts: Counter[str] = Counter()
        done: list[str] = []
        for rule in rules:
            if codes is not None and rule.code not in codes:
                continue
            if scope is not None and not rule.incremental:
                continue
            found = settings_for(organisation, rule)
            ctx = Context(organisation, found.params, found.severity, scope, now)
            if not found.enabled:
                if scope is None:
                    _switched_off(rule, ctx, counts)
                continue
            apply_hits(rule, ctx, list(rule.evaluate(ctx)), record, counts)
            done.append(rule.code)
        record.rules = done
        record.counts = {
            k: counts.get(k, 0)
            for k in ("seen", "created", "updated", "reopened", "suppressed", "resolved")
        }
        record.status = RunStatus.SUCCEEDED
        record.finished_at = timezone.now()
        record.save(update_fields=["rules", "counts", "status", "finished_at", "updated_at"])
        return record


# ---- background jobs ------------------------------------------------------------------------


@org_job(name=JOB, queue=REPORTS, max_retries=2)
def run_job(
    *,
    org_id: str,
    trigger: str = RunTrigger.MANUAL,
    scope: dict[str, Any] | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    from numo9.accounts.models import User
    from numo9.jobs.runtime import current_job

    organisation = Organisation.objects.get(public_id=org_id)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    done = run(
        organisation,
        trigger=trigger,
        scope=Scope.from_dict(scope) if scope else None,
        user=user,
        job_run=current_job(),
    )
    return {"run": str(done.public_id), "counts": done.counts}


def start_run(organisation: Organisation, *, user: Any = None, key: str | None = None) -> Any:
    """Start a full on-demand run in the background; the job run."""
    person = user if getattr(user, "is_authenticated", False) else None
    return start_job(
        run_job,
        organisation=organisation,
        key=key,
        created_by=person,
        trigger=RunTrigger.MANUAL,
        user_id=person.pk if person is not None else None,
    )


def run_all(now: dt.datetime | None = None) -> int:
    """The nightly run: every active organisation, one job each (keyed by the day)."""
    now = now or timezone.now()
    started = 0
    for organisation in Organisation.objects.order_by("pk").iterator():
        start_job(
            run_job,
            organisation=organisation,
            key=f"nightly:{now.date().isoformat()}",
            trigger=RunTrigger.NIGHTLY,
        )
        started += 1
    return started


@platform_job(name=NIGHTLY_JOB, queue=DEFAULT)
def nightly_job() -> int:
    return run_all()


# ---- incremental runs on posting -------------------------------------------------------------


def _start_incremental(organisation: Organisation, scope: Scope) -> None:
    try:
        with org_context(organisation):
            start_job(
                run_job,
                organisation=organisation,
                key="posting:" + ",".join(sorted(scope.entries)),
                trigger=RunTrigger.POSTING,
                scope=scope.as_dict(),
            )
    except Exception:  # never fail a posting because the checks couldn't be queued
        logger.exception("assurance: incremental run for %s not started", organisation.pk)


def posted_hook(entry: Any, checked: Any, spec: Any, organisation: Any, person: Any) -> None:
    """``POSTED_HOOKS``: re-check at once the findings this journal fixes (K-09-T16), and queue
    an incremental run for the journal and its accounts when the transaction commits (nothing is
    queued when it rolls back)."""
    from .fixes import resolve_fixed

    with org_context(organisation):
        resolve_fixed(entry, person)
    scope = Scope(
        frozenset({str(entry.public_id)}),
        frozenset(str(line.account.public_id) for line in checked.lines),
    )
    transaction.on_commit(lambda: _start_incremental(organisation, scope))
