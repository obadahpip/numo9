"""K-01-T17 — seed_report_books: the k6 fixture organisation with N posted lines over the last
12 months, balanced, an owner who can sign in, idempotent."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command

from numo9.ledger.models import JournalEntry, JournalLine
from numo9.reports.engine import registry
from numo9.reports.management.commands.seed_report_books import ORG_NAME
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
PASSWORD = "Seed-pass-2026!"  # noqa: S105 — a test fixture


def test_seeds_a_balanced_ledger_once(settings: Any) -> None:
    settings.DEBUG = True
    out = StringIO()
    call_command("seed_report_books", lines=500, password=PASSWORD, stdout=out)
    assert "500 lines" in out.getvalue()
    org = Organisation.objects.get(name=ORG_NAME)
    with org_context(org):
        assert JournalEntry.objects.filter(status="posted").count() == 50
        assert JournalLine.objects.count() == 500
    result = registry.get("trial_balance").run(org, {})
    debit, credit = result.totals[0].values
    assert debit == credit and debit
    call_command("seed_report_books", lines=500, stdout=out)
    assert "already seeded" in out.getvalue()
    with org_context(org):
        assert JournalLine.objects.count() == 500
    assert org.members.get().user.check_password(PASSWORD)


def test_refuses_without_debug(settings: Any) -> None:
    settings.DEBUG = False
    with pytest.raises(Exception, match="Dev and staging only"):
        call_command("seed_report_books", lines=10)
