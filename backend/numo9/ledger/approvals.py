"""Journal approval (C-04-T02, T03): submit, approve, reject — the approver is never the author.

- ``journal_total(entry)`` — the journal's amount: the larger of its debit totals in the
  accounting and the tax book (``both`` lines count in each).
- ``approval_required(organisation, total)`` — a manual journal needs approval when the
  organisation set a threshold (``journal_approval_threshold``, C-04-T01) and the total is at or
  above it.
- ``submit_for_approval(entry, user)`` — Draft → Awaiting approval; opens an approval round
  (``JournalApproval``: total, who, when).
- ``approve(entry, user)`` — only an entry awaiting approval; the approver must not be the
  journal's author nor the person who submitted it (``ledger.journal.self_approval``, server-side
  whatever the UI shows); the amount must be within their approval limit for manual journals
  (A-03 ``assert_can_approve``: 403 ``approval.limit_exceeded`` naming who may approve — a limit
  of 5,000.00 can't approve 5,000.01). Approving **posts** the journal, as the approver, in the
  same transaction (every posting rule applies); the round records the decision and the limit.
- ``reject(entry, user, reason)`` — Awaiting approval → Draft with a reason (≥ 3 characters),
  by someone other than the author; ``withdraw(entry, user)`` — the author takes it back.

The posting gate (C-04-T03, ``assert_approved``) refuses to post a manual journal that needs
approval and has no approved round — 409 ``ledger.journal.approval_required``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status

from numo9.rbac.approvals import assert_can_approve
from numo9.rbac.models import ApprovalDocumentType
from numo9.tenancy.context import org_context

from .models import (
    ApprovalDecision,
    Book,
    JournalApproval,
    JournalEntry,
    JournalLine,
    JournalStatus,
    JournalType,
    LedgerError,
)

ZERO = Decimal("0.00")
MIN_REASON = 3


class ApprovalRefused(LedgerError):
    """An approval action refused (``code`` names the rule)."""

    status_code = status.HTTP_409_CONFLICT


class ApprovalRequired(ApprovalRefused):
    """A manual journal at or above the threshold posted without approval (C-04-T03)."""


def journal_total(entry: JournalEntry) -> Decimal:
    with org_context(entry.organisation):
        rows = (
            JournalLine.objects.filter(entry=entry)
            .values("book")
            .annotate(debit=Coalesce(Sum("debit"), ZERO))
            .order_by()
        )
        sums = {row["book"]: row["debit"] for row in rows}
    both = sums.get(Book.BOTH, ZERO)
    return Decimal(max(both + sums.get(Book.ACCOUNTING, ZERO), both + sums.get(Book.TAX, ZERO)))


def threshold(organisation: Any) -> Decimal | None:
    from numo9.orgsettings.models import OrganisationSettings

    value = (
        OrganisationSettings._base_manager.filter(organisation=organisation)
        .values_list("journal_approval_threshold", flat=True)
        .first()
    )
    return None if value is None else Decimal(value)


def approval_required(organisation: Any, total: Decimal) -> bool:
    limit = threshold(organisation)
    return limit is not None and total >= limit


def latest_round(entry: JournalEntry) -> JournalApproval | None:
    with org_context(entry.organisation):
        found: JournalApproval | None = (
            JournalApproval.objects.filter(entry=entry).order_by("-submitted_at", "-pk").first()
        )
        return found


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _awaiting(entry: JournalEntry) -> JournalEntry:
    locked = JournalEntry._base_manager.select_for_update().get(pk=entry.pk)
    if locked.status != JournalStatus.AWAITING_APPROVAL:
        raise ApprovalRefused(
            _("%(journal)s isn't waiting for approval."),
            code="ledger.journal.not_awaiting",
            params={"journal": str(locked)},
        )
    return locked


def _pending(entry: JournalEntry) -> JournalApproval:
    found = (
        JournalApproval._base_manager.select_for_update()
        .filter(entry=entry, decision=ApprovalDecision.PENDING)
        .first()
    )
    if found is None:  # submitted before approval rounds existed: open one now
        found = JournalApproval(
            organisation_id=entry.organisation_id,
            entry=entry,
            total=journal_total(entry),
            submitted_by=entry.created_by,
        )
        found.save()
    return found


def submit_for_approval(entry: JournalEntry, user: Any) -> JournalEntry:
    """Draft → Awaiting approval, opening an approval round."""
    from .services import submit

    with org_context(entry.organisation), transaction.atomic():
        submitted = submit(entry)
        JournalApproval(
            organisation_id=entry.organisation_id,
            entry=submitted,
            total=journal_total(submitted),
            submitted_by=_person(user),
        ).save()
    from .notifications import journal_submitted

    journal_submitted(submitted, user)
    return submitted


def _not_the_author(entry: JournalEntry, round_: JournalApproval, user: Any) -> None:
    authors = {entry.created_by_id, round_.submitted_by_id} - {None}
    if getattr(user, "pk", None) in authors:
        raise ApprovalRefused(
            _("You wrote or submitted %(journal)s: someone else must approve or reject it."),
            code="ledger.journal.self_approval",
            params={"journal": str(entry)},
        )


def approve(entry: JournalEntry, user: Any) -> JournalEntry:
    """Approve and post (module docstring); returns the posted entry."""
    from .services import post_entry

    with org_context(entry.organisation), transaction.atomic():
        locked = _awaiting(entry)
        round_ = _pending(locked)
        _not_the_author(locked, round_, user)
        total = journal_total(locked)
        limit = assert_can_approve(
            user,
            ApprovalDocumentType.JOURNAL,
            total,
            organisation=locked.organisation,
            exclude=[p for p in (locked.created_by, round_.submitted_by) if p is not None],
        )
        round_.decision = ApprovalDecision.APPROVED
        round_.decided_by = _person(user)
        round_.decided_at = timezone.now()
        round_.limit = limit
        round_.total = total
        round_.save()
        posted = post_entry(locked, user=user)
    from .notifications import journal_decided

    journal_decided(posted, round_)
    return posted


def reject(entry: JournalEntry, user: Any, reason: str) -> JournalEntry:
    """Awaiting approval → Draft with the reason; the author can't reject their own journal."""
    from .services import return_to_draft

    text = " ".join((reason or "").split())
    if len(text) < MIN_REASON:
        raise ApprovalRefused(
            _("Say why the journal is sent back (at least %(min)d characters)."),
            code="ledger.journal.reject_reason_required",
            params={"min": MIN_REASON},
        )
    with org_context(entry.organisation), transaction.atomic():
        locked = _awaiting(entry)
        round_ = _pending(locked)
        _not_the_author(locked, round_, user)
        round_.decision = ApprovalDecision.REJECTED
        round_.decided_by = _person(user)
        round_.decided_at = timezone.now()
        round_.reason = text
        round_.save()
        returned = return_to_draft(locked)
    from .notifications import journal_decided

    journal_decided(returned, round_)
    return returned


def withdraw(entry: JournalEntry, user: Any) -> JournalEntry:
    """The author takes an awaiting journal back to draft (no approval needed for that)."""
    from .services import return_to_draft

    with org_context(entry.organisation), transaction.atomic():
        locked = _awaiting(entry)
        round_ = _pending(locked)
        round_.decision = ApprovalDecision.WITHDRAWN
        round_.decided_by = _person(user)
        round_.decided_at = timezone.now()
        round_.save()
        return return_to_draft(locked)


def assert_approved(
    entry: JournalEntry | None, organisation: Any, total: Decimal, kind: str
) -> None:
    """The posting gate (C-04-T03): a manual journal that needs approval posts only after an
    approved round (``approve`` posts it); module postings and reversals are never gated."""
    if kind != JournalType.MANUAL or not approval_required(organisation, total):
        return
    if entry is not None:
        round_ = latest_round(entry)
        if round_ is not None and round_.decision == ApprovalDecision.APPROVED:
            return
    raise ApprovalRequired(
        _(
            "Approval required: journals of %(threshold)s or more must be approved by someone "
            "else before they post. Submit it for approval."
        ),
        code="ledger.journal.approval_required",
        params={"threshold": f"{threshold(organisation):,.2f}"},
    )
