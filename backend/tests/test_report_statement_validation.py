"""K-02-T15 — data validation on the fixture organisations: the balance sheet balances, net
income = Δ retained earnings, trial balance = general ledger, cash flow = Δ cash."""

from __future__ import annotations

import datetime as dt
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from numo9.demo.seeders import run_seed
from numo9.reports import statements
from numo9.reports.validation import validate_statements
from numo9.tenancy.models import Organisation
from tests.report_helpers import report_books

pytestmark = [pytest.mark.django_db, pytest.mark.data_validation]


def test_report_books_are_consistent() -> None:
    org = report_books()["org"]
    for start, end in (
        (dt.date(2026, 1, 1), dt.date(2026, 7, 31)),
        (dt.date(2026, 6, 1), dt.date(2026, 6, 30)),
        (dt.date(2026, 7, 9), dt.date(2026, 12, 31)),
    ):
        assert validate_statements(org, start, end) == []


def test_demo_organisation_is_consistent() -> None:
    org = Organisation.objects.create(name="Demo")
    run_seed(org)
    today = dt.date.today()
    assert validate_statements(org, today.replace(month=1, day=1), today) == []
    assert validate_statements(org, today.replace(month=1, day=1), today, "tax") == []


def test_command_reports_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    org = report_books()["org"]
    out = StringIO()
    call_command(
        "validate_statements", "--org", str(org.public_id), "--to", "2026-07-31", stdout=out
    )
    assert "OK" in out.getvalue()
    monkeypatch.setattr(statements, "_earnings_change", lambda *a: 0)
    real = statements.balance_figures

    def broken(*args, **kwargs):  # type: ignore[no-untyped-def]
        data = real(*args, **kwargs)
        data.retained[-1] += 1
        return data

    monkeypatch.setattr(statements, "balance_figures", broken)
    with pytest.raises(CommandError):
        call_command(
            "validate_statements",
            "--org",
            str(org.public_id),
            "--to",
            "2026-07-31",
            stdout=StringIO(),
        )
