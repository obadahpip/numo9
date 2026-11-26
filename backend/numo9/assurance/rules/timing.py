"""Timing rules (K-09-T10, T11): backdated postings and weekend postings.

**BACKDATED** — a journal, invoice or bill posted more than ``days`` after its document date
(the posting time's date in the organisation's time zone − the entry's date). An invoice or a
bill is judged by its **first** posting (a revision's re-post or a recode keeps the original
date on purpose and is never "backdated"); find & recode re-posts, reversals, opening balances
and closing entries are left out.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy

from numo9.ledger.models import (
    JournalCategory,
    JournalEntry,
    JournalStatus,
    JournalType,
    RecodeLineChange,
)

from ..models import ExceptionFinding, Severity
from .base import Context, Hit, Param, Rule, register
from .common import ENTRY, Numbers, entry_total

#: Source documents judged as documents (subject = the document), by source type.
DOCUMENTS: dict[str, str] = {
    "sales.invoice": "sales.Invoice",
    "purchases.bill": "purchases.Bill",
}


def _reposts() -> Any:
    rows = RecodeLineChange.objects.values_list("repost_entry_id", "undo_repost_entry_id")
    return {pk for pair in rows for pk in pair if pk is not None}


def _document_labels(source_type: str, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    if source_type == "sales.invoice":
        from numo9.sales.models import Invoice as Model
    else:
        from numo9.purchases.models import Bill as Model  # type: ignore[assignment]
    rows = Model.objects.filter(public_id__in=sorted(ids)).values_list("public_id", "number")
    return {str(pid): number for pid, number in rows}


@register
class Backdated(Rule):
    code = "BACKDATED"
    name = gettext_lazy("Backdated posting")
    description = gettext_lazy(
        "A journal, invoice or bill posted long after its date: it changes periods that may "
        "already have been reported."
    )
    explanation = gettext_lazy(
        "%(document)s is dated %(date)s but was posted on %(posted_on)s (%(gap)s days later; "
        "the limit is %(days)s)."
    )
    default_severity = Severity.WARNING
    incremental = True
    date_keys = ("date", "posted_on")
    params = {"days": Param("int", 7, gettext_lazy("Days"), minimum=1, maximum=365)}

    def covers(self, ctx: Context, finding: ExceptionFinding) -> bool:
        if ctx.scope is None:
            return True
        return str(finding.details.get("entry", "")) in ctx.scope.entries

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        entries = (
            JournalEntry.objects.filter(
                status__in=(JournalStatus.POSTED, JournalStatus.REVERSED),
                reversal_of__isnull=True,
                posted_at__isnull=False,
            )
            .exclude(type__in=(JournalType.OPENING, JournalType.REVERSAL))
            .exclude(journal_type=JournalCategory.CLOSING)
            .exclude(pk__in=_reposts())
            .filter(Q(source_type="") | Q(source_type__in=list(DOCUMENTS)) | Q(type="manual"))
            .prefetch_related("lines")
            .order_by("posted_at", "pk")
        )
        if ctx.scope is not None:
            entries = entries.filter(public_id__in=sorted(ctx.scope.entries))
        first_posting: dict[tuple[str, str], int] = {}
        rows = (
            JournalEntry.objects.filter(source_type__in=list(DOCUMENTS), posted_at__isnull=False)
            .order_by("posted_at", "pk")
            .values_list("source_type", "source_id", "pk")
        )
        for source_type, source_id, pk in rows:
            first_posting.setdefault((source_type, source_id), pk)
        limit = ctx.params["days"]
        numbers = Numbers(ctx.organisation)
        late: list[tuple[JournalEntry, dt.date, int]] = []
        for entry in entries:
            if entry.status != JournalStatus.POSTED and entry.source_type not in DOCUMENTS:
                continue  # a reversed journal was corrected
            document = entry.source_type in DOCUMENTS
            if document and first_posting.get((entry.source_type, entry.source_id)) != entry.pk:
                continue
            if entry.posted_at is None:
                continue
            posted_on = entry.posted_at.astimezone(ctx.zone).date()
            gap = (posted_on - entry.date).days
            if gap > limit:
                late.append((entry, posted_on, gap))
        labels: dict[str, dict[str, str]] = {}
        for source_type in DOCUMENTS:
            ids = {e.source_id for e, _p, _g in late if e.source_type == source_type}
            labels[source_type] = _document_labels(source_type, ids)
        for entry, posted_on, gap in late:
            if entry.source_type in DOCUMENTS:
                subject_type = DOCUMENTS[entry.source_type]
                subject_id = entry.source_id
                label = labels[entry.source_type].get(entry.source_id) or numbers.label(entry)
            else:
                subject_type, subject_id, label = ENTRY, str(entry.public_id), numbers.label(entry)
            yield Hit(
                subject_type,
                subject_id,
                label,
                entry_total(entry),
                {
                    "document": label,
                    "entry": str(entry.public_id),
                    "journal": numbers.label(entry),
                    "date": entry.date.isoformat(),
                    "posted_on": posted_on.isoformat(),
                    "gap": gap,
                    "days": limit,
                },
            )
