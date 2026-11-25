"""D-02-T01 — ``Quote`` and ``QuoteLine``: optional lines, alternative groups and the selection;
the expiry date after the quote date; numbers unique per organisation; an invoiced quote names
its invoice; ``QuoteStatus`` is the frontend's ``QUOTE_STATUSES``."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest
from django.db import IntegrityError, transaction

from numo9.sales.models import QuoteLine, QuoteStatus
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
FRONTEND = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "sales" / "quotes" / "status.ts"
)


def test_status_enum_exported_to_the_frontend() -> None:
    text = FRONTEND.read_text(encoding="utf-8")
    block = text[text.index("QUOTE_STATUSES = [") : text.index("] as const")]
    assert re.findall(r'"([a-z_]+)"', block) == QuoteStatus.values


def test_lines_options_and_rules() -> None:
    books = sales_books()
    item = quote(
        books,
        [
            {"price": "1000", "tax": "sales.ON.standard"},
            {"price": "200", "is_optional": True},
            {"price": "300", "alternative_group": "finish"},
            {"price": "350", "alternative_group": "finish", "selected": False},
        ],
    )
    assert item.number == "QU-0001" and item.status == "draft"
    with org_context(books["org"]):
        rows = list(item.lines.order_by("position"))
    assert [(r.is_optional, r.alternative_group, r.selected) for r in rows] == [
        (False, "", True),
        (True, "", False),
        (False, "finish", True),
        (False, "finish", False),
    ]

    def refused(make: object) -> bool:
        try:
            with transaction.atomic():
                make()  # type: ignore[operator]
        except IntegrityError:
            return True
        return False

    with org_context(books["org"]):
        assert refused(
            lambda: QuoteLine(
                organisation=books["org"], document=item, is_optional=True, alternative_group="x"
            ).save()
        )
        item.expiry_date = item.date - dt.timedelta(days=1)
        assert refused(item.save)
        item.refresh_from_db()
        item.status = QuoteStatus.INVOICED
        assert refused(item.save)
    assert refused(lambda: quote(books, [], number="QU-0001"))
