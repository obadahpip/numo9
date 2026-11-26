"""Control rules (K-09-T12, T13): segregation of duties and duplicates.

**SOD_SAME_CREATOR_APPROVER** — the same person created (or submitted) and approved a manual
journal (C-04 approval rounds) or a bill (E-02 approval). Numo9 refuses that today; it arrives
with legacy imports and data from before the approval rules, so the engine flags it. Pay runs
register their own source in ``SOD_SOURCES`` when payroll is built (placeholder).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from django.db.models import F, Q
from django.utils.translation import gettext_lazy

from numo9.ledger.models import ApprovalDecision, JournalApproval, JournalStatus

from ..models import ExceptionFinding, Severity
from .base import Context, Hit, Rule, register
from .common import ENTRY, Numbers, entry_total

BILL = "purchases.Bill"


def _person(user: Any) -> str:
    return str(user.name or user.email) if user is not None else ""


def journal_hits(ctx: Context) -> Iterable[Hit]:
    rounds = (
        JournalApproval.objects.filter(
            decision=ApprovalDecision.APPROVED,
            decided_by__isnull=False,
            entry__status=JournalStatus.POSTED,
        )
        .filter(Q(decided_by=F("submitted_by")) | Q(decided_by=F("entry__created_by")))
        .select_related("entry", "decided_by")
        .prefetch_related("entry__lines")
        .order_by("entry__date", "entry_id", "-submitted_at")
    )
    if ctx.scope is not None:
        rounds = rounds.filter(entry__public_id__in=sorted(ctx.scope.entries))
    numbers = Numbers(ctx.organisation)
    seen: set[int] = set()
    for row in rounds:
        if row.entry_id in seen:
            continue
        seen.add(row.entry_id)
        label = numbers.label(row.entry)
        yield Hit(
            ENTRY,
            str(row.entry.public_id),
            label,
            entry_total(row.entry),
            {
                "document": label,
                "entry": str(row.entry.public_id),
                "person": _person(row.decided_by),
                "date": row.entry.date.isoformat(),
            },
        )


def bill_hits(ctx: Context) -> Iterable[Hit]:
    from numo9.purchases.models import BILL_POSTED_STATUSES, Bill

    bills = (
        Bill.objects.filter(status__in=sorted(BILL_POSTED_STATUSES), approved_by__isnull=False)
        .filter(Q(approved_by=F("created_by")) | Q(approved_by=F("submitted_by")))
        .select_related("approved_by", "journal_entry")
        .order_by("date", "pk")
    )
    if ctx.scope is not None:
        bills = bills.filter(journal_entry__public_id__in=sorted(ctx.scope.entries))
    for bill in bills:
        yield Hit(
            BILL,
            str(bill.public_id),
            bill.number,
            bill.total,
            {
                "document": bill.number,
                "entry": str(bill.journal_entry.public_id) if bill.journal_entry else "",
                "person": _person(bill.approved_by),
                "date": bill.date.isoformat(),
            },
        )


#: Sources of "created and approved by the same person": journals, bills; payroll adds pay runs.
SOD_SOURCES: list[Callable[[Context], Iterable[Hit]]] = [journal_hits, bill_hits]


@register
class SameCreatorApprover(Rule):
    code = "SOD_SAME_CREATOR_APPROVER"
    name = gettext_lazy("Created and approved by the same person")
    description = gettext_lazy(
        "One person entered and approved the same journal, bill or pay run: no second pair of eyes."
    )
    explanation = gettext_lazy(
        "%(document)s (%(date)s) was entered and approved by %(person)s. Approval needs a second "
        "person."
    )
    default_severity = Severity.WARNING
    incremental = True
    money_keys = ()
    date_keys = ("date",)

    def covers(self, ctx: Context, finding: ExceptionFinding) -> bool:
        if ctx.scope is None:
            return True
        return str(finding.details.get("entry", "")) in ctx.scope.entries

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        for source in SOD_SOURCES:
            yield from source(ctx)
