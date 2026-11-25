"""C-06-T01 — ``PeriodClose``: a record per module per period end; one open close per module and
period end, one open year-end close per fiscal year end (no double closing journal); a reopened
close needs who and why; a year-end close is the general ledger's."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.ledger.models import PeriodClose
from numo9.tenancy.context import org_context
from tests.period_close_helpers import close_books

pytestmark = pytest.mark.django_db
JUNE = dt.date(2026, 6, 30)


def make(books: dict[str, Any], **fields: Any) -> PeriodClose:
    fields.setdefault("closed_by", books["owner"])
    with org_context(books["org"]):
        row = PeriodClose(organisation=books["org"], **fields)
        row.save()
    return row


def refused(books: dict[str, Any], **fields: Any) -> bool:
    try:
        with transaction.atomic():
            make(books, **fields)
    except IntegrityError:
        return True
    return False


def test_record_per_module_per_period() -> None:
    books = close_books()
    gl = make(books, module="gl", period_end=JUNE)
    make(books, module="ap", period_end=JUNE)
    assert str(gl) == "Period close gl 2026-06-30" and gl.is_open
    assert refused(books, module="gl", period_end=JUNE)  # one open close
    gl.reopened_by, gl.reopened_at, gl.reason = books["adviser"], timezone.now(), "Late bill"
    gl.save()
    make(books, module="gl", period_end=JUNE)  # closed again after the reopen


def test_rules() -> None:
    books = close_books()
    year_end = dt.date(2026, 12, 31)
    make(books, module="gl", period_end=year_end, kind="year_end")
    assert refused(books, module="gl", period_end=year_end, kind="year_end")
    assert refused(books, module="ap", period_end=dt.date(2026, 11, 30), kind="year_end")
    assert refused(books, module="crm", period_end=JUNE)
    assert refused(books, module="ar", period_end=JUNE, reopened_at=timezone.now())  # no who/why
