"""Journals in the approvals inbox (C-04-T08): manual journals awaiting approval.

Listed for people with ``accounting.journals.approve`` (each with whether they may approve it:
not its author or submitter, within their journal approval limit) and, for everyone else, the
ones they submitted themselves.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from numo9.rbac.approvals import effective_limit
from numo9.rbac.inbox import Approvable, approvables, blocked_reason, item
from numo9.rbac.models import ApprovalDocumentType

from .approvals import journal_total
from .models import ApprovalDecision, JournalApproval, JournalEntry, JournalStatus
from .sequence import format_journal_number


def journal_items(user: Any, organisation: Any, may_approve: bool) -> list[dict[str, Any]]:
    entries = JournalEntry.objects.filter(
        status=JournalStatus.AWAITING_APPROVAL, deleted_at__isnull=True
    ).select_related("created_by")
    rounds = {
        r.entry_id: r
        for r in JournalApproval.objects.filter(
            decision=ApprovalDecision.PENDING, entry__in=entries
        ).select_related("submitted_by")
    }
    if not may_approve:
        mine = [pk for pk, r in rounds.items() if r.submitted_by_id == user.pk]
        entries = entries.filter(Q(pk__in=mine) | Q(created_by=user))
    limit = effective_limit(user, ApprovalDocumentType.JOURNAL, organisation=organisation)
    out: list[dict[str, Any]] = []
    for entry in entries.order_by("pk"):
        round_ = rounds.get(entry.pk)
        total = journal_total(entry)
        authors = {entry.created_by_id, round_.submitted_by_id if round_ else None} - {None}
        blocked = blocked_reason(user, authors, limit, total) if may_approve else "self"
        out.append(
            item(
                kind="journal",
                id=str(entry.public_id),
                title=entry.narration or str(_("Manual journal")),
                subtitle=format_journal_number(organisation, entry.number) if entry.number else "",
                amount=total,
                date=entry.date,
                url=f"/o/{organisation.public_id}/accounting/journals/{entry.public_id}",
                submitted_by=round_.submitted_by if round_ else None,
                submitted_at=round_.submitted_at if round_ else None,
                created_by=entry.created_by,
                blocked=blocked,
                limit=limit,
            )
        )
    return out


def register_journal_approvals() -> None:
    approvables.register(
        Approvable(
            kind="journal",
            label=_("Manual journals"),
            permission="accounting.journals.approve",
            feature="accounting.journals.approve",
            items=journal_items,
        )
    )
