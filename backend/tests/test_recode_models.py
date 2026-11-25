"""C-07-T01 — RecodeBatch and RecodeLineChange migrate; status, undo and one change per line."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.ledger.models import RecodeBatch, RecodeLineChange, RecodeStatus
from numo9.tenancy.context import org_context
from tests.period_close_helpers import close_books, post

pytestmark = pytest.mark.django_db


def test_batch_and_line_change() -> None:
    books = close_books()
    post(books, dt.date(2026, 3, 1), "bank", "revenue", "500.00")
    entry = post(books, dt.date(2026, 3, 5), "expense", "bank", "120.00")
    with org_context(books["org"]):
        batch = RecodeBatch.objects.create(
            organisation=books["org"],
            criteria={
                "match": "all",
                "conditions": [{"field": "account", "op": "is", "value": "x"}],
            },
            changes={"account": "y"},
        )
        line = entry.lines.get(line_no=1)
        change = RecodeLineChange.objects.create(
            organisation=books["org"],
            batch=batch,
            entry=entry,
            line_no=1,
            line_id=line.id,
            before={"account": "x"},
            after={"account": "y"},
            debit=Decimal("120.00"),
        )
        assert batch.status == RecodeStatus.DRAFT and batch.lines.get() == change
        with pytest.raises(IntegrityError), transaction.atomic():
            RecodeLineChange.objects.create(
                organisation=books["org"], batch=batch, entry=entry, line_no=1, line_id=line.id
            )
        with pytest.raises(IntegrityError), transaction.atomic():
            RecodeBatch.objects.filter(pk=batch.pk).update(status=RecodeStatus.UNDONE)
        RecodeBatch.objects.filter(pk=batch.pk).update(
            status=RecodeStatus.UNDONE, undone_by=books["adviser"], undone_at=timezone.now()
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            RecodeBatch.objects.filter(pk=batch.pk).update(status="bogus")
