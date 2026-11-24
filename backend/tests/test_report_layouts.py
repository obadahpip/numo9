"""K-01-T08 — report layouts: rows reordered, renamed and hidden, text blocks inserted; drafts are
saved in place; publishing stores a snapshot that new postings never change and freezes the
layout (a later change is a new draft version); custom layouts are named variants.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.ledger.services import post_journal
from numo9.reports.engine import registry
from numo9.reports.layouts import LayoutLocked, apply_layout, publish, save_custom, save_draft
from numo9.reports.models import ReportLayout
from numo9.tenancy.context import org_context
from tests.journal_helpers import pay
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db
PARAMS = {"date_from": "2026-06-01", "date_to": "2026-06-30"}
CONFIG = {
    "rows": [
        {"key": "account:5400", "label": "Premises rent"},
        {"key": "account:1000", "hidden": True},
    ],
    "text_blocks": [{"after": "account:5400", "text": "Rent rose in June."}, {"text": "Unaudited"}],
}


@pytest.fixture
def books() -> dict[str, Any]:
    return report_books()


def test_apply_layout(books: dict[str, Any]) -> None:
    result = registry.get("account_activity").run(books["org"], PARAMS)
    rows = apply_layout(result, CONFIG)
    assert [(r.kind, r.label) for r in rows] == [
        ("text", "Unaudited"),
        ("row", "Premises rent"),
        ("text", "Rent rose in June."),
        ("row", "6100 · Office supplies"),  # not in the layout: after the ones it names
    ]
    assert apply_layout(result, {}) == result.rows


def test_publish_freezes_a_snapshot(books: dict[str, Any]) -> None:
    org = books["org"]
    draft = save_draft(org, "account-activity", "Board pack", params=PARAMS, config=CONFIG)
    again = save_draft(org, "account_activity", "Board pack", params=PARAMS, config={}, notes="n")
    assert again.pk == draft.pk and again.version == 1  # a draft is saved in place
    again = save_draft(org, "account_activity", "Board pack", params=PARAMS, config=CONFIG)
    published = publish(again, None, dt.date(2026, 7, 15))
    snapshot = published.snapshot
    assert snapshot is not None
    assert published.status == "published" and published.published_at is not None
    assert snapshot["header"]["period_label"] == "1 Jun 2026 to 30 Jun 2026"
    rent = next(r for r in snapshot["rows"] if r["label"] == "Premises rent")
    assert rent["values"] == ["2400.00", "0.00", "2400.00"]
    with org_context(org):
        post_journal(
            pay(books["rent"], books["chequing"], "500.00", dt.date(2026, 6, 28)), user=None
        )
        published.refresh_from_db()
    assert published.snapshot == snapshot  # later postings never change a published report
    live = registry.get("account_activity").run(org, PARAMS)
    assert next(r for r in live.rows if r.key == "account:5400").values[0] == 2900
    with pytest.raises(LayoutLocked):
        publish(published, None, dt.date(2026, 7, 15))
    next_version = save_draft(org, "account_activity", "Board pack", params=PARAMS, config={})
    assert (next_version.version, next_version.status) == (2, "draft")
    with org_context(org):
        assert ReportLayout.objects.get(pk=published.pk).snapshot == snapshot


def test_custom_and_rules(books: dict[str, Any]) -> None:
    org = books["org"]
    custom = save_custom(
        org, "trial_balance", "Bank only", params={"as_of": "2026-06-30"}, config={}
    )
    assert custom.status == "custom"
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        ReportLayout(
            organisation=org, report_id="trial_balance", name="x", status="published"
        ).save()
