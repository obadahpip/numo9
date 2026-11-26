"""Finding workflow (K-09-T17): acknowledge, false positive with a reason, reopen; resolution is
automatic (the runner resolves a finding when its condition clears, K-09-T05, or when its fix is
posted, K-09-T16).

    open ──acknowledge──▶ acknowledged
      │                        │
      └──false_positive(reason)┴──▶ false positive ──reopen──▶ open
    acknowledged ──reopen──▶ open
    open / acknowledged ──(condition clears)──▶ resolved ──(recurs)──▶ open

Every transition is audited (``assurance.finding.acknowledged`` / ``false_positive`` /
``reopened``) with the person and ``changes.status``. A refused transition is
``WorkflowRefused`` (``assurance.finding.transition`` or ``assurance.finding.reason_required``).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.audit import service as audit
from numo9.tenancy.context import org_context

from .models import ACTIVE_STATUSES, ExceptionFinding, FindingStatus

MIN_REASON = 5


class WorkflowRefused(ValidationError):
    pass


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _move(
    finding: ExceptionFinding,
    to: str,
    allowed: tuple[str, ...],
    user: Any,
    *,
    reason: str = "",
) -> ExceptionFinding:
    with org_context(finding.organisation), transaction.atomic():
        locked = ExceptionFinding.objects.select_for_update().get(pk=finding.pk)
        if locked.status not in allowed:
            raise WorkflowRefused(
                _("This finding is %(status)s: it can't be %(action)s.")
                % {
                    "status": str(locked.get_status_display()).lower(),
                    "action": str(FindingStatus(to).label).lower(),
                },
                code="assurance.finding.transition",
            )
        if to == FindingStatus.OPEN and locked.status == FindingStatus.FALSE_POSITIVE:
            newer = (
                ExceptionFinding.objects.filter(
                    fingerprint=locked.fingerprint, status__in=ACTIVE_STATUSES
                )
                .exclude(pk=locked.pk)
                .exists()
            )
            if newer:
                raise WorkflowRefused(
                    _("A newer finding is open for the same problem: work on that one."),
                    code="assurance.finding.transition",
                )
        before = locked.status
        locked.status = to
        if to in (FindingStatus.ACKNOWLEDGED, FindingStatus.FALSE_POSITIVE):
            locked.ack_by, locked.ack_at = _person(user), timezone.now()
            locked.reason = reason
        else:
            locked.ack_by, locked.ack_at, locked.reason = None, None, ""
        locked.save(update_fields=["status", "ack_by", "ack_at", "reason", "updated_at"])
        verb = {FindingStatus.OPEN: "reopened"}.get(to, to)
        audit.record(
            f"assurance.finding.{verb}",
            obj=locked,
            object_label=f"{locked.rule_code} · {locked.subject_label or locked.subject_id}",
            changes={"status": [before, to]},
            meta={"rule": locked.rule_code, "reason": reason},
            actor=_person(user),
        )
        return locked


def acknowledge(finding: ExceptionFinding, user: Any, reason: str = "") -> ExceptionFinding:
    """Seen and being dealt with: it stays in the list (and costs half in the score)."""
    return _move(
        finding,
        FindingStatus.ACKNOWLEDGED,
        (FindingStatus.OPEN,),
        user,
        reason=(reason or "").strip(),
    )


def mark_false_positive(finding: ExceptionFinding, user: Any, reason: str) -> ExceptionFinding:
    """Not a problem: silent while it recurs with the same amount (runner)."""
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON:
        raise WorkflowRefused(
            _("Say why this is not a problem (at least %(min)d characters).") % {"min": MIN_REASON},
            code="assurance.finding.reason_required",
        )
    return _move(finding, FindingStatus.FALSE_POSITIVE, ACTIVE_STATUSES, user, reason=reason)


def reopen(finding: ExceptionFinding, user: Any) -> ExceptionFinding:
    """Back to open (an acknowledgement or a false positive taken back)."""
    return _move(
        finding,
        FindingStatus.OPEN,
        (FindingStatus.ACKNOWLEDGED, FindingStatus.FALSE_POSITIVE),
        user,
    )
