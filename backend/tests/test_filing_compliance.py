"""G-03a-T22 — compliance fixtures (tests/fixtures/compliance/filing_cycles.yaml): quarterly →
monthly from 1 July; annual → quarterly mid-year (a stub); a financial year ending 31 March; a
leap year; two switches in one year. Acceptance: 100 % pass — the periods (dates, kind, status,
listed due dates) are exactly the hand-written ones, with no gap or overlap."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
import yaml

from numo9.tax.filing_service import add_custom_period, switch_frequency
from numo9.tax.models import FilingPeriod, PeriodStatus
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = [pytest.mark.django_db, pytest.mark.compliance]

FIXTURE = Path(__file__).parent / "fixtures" / "compliance" / "filing_cycles.yaml"
DOCUMENT: dict[str, Any] = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
TODAY = dt.date.fromisoformat(DOCUMENT["today"])
iso = dt.date.fromisoformat


def test_fixture_covers_the_scenarios_of_the_plan() -> None:
    assert [s["name"] for s in DOCUMENT["scenarios"]] == [
        "quarterly_to_monthly_1_july",
        "annual_to_quarterly_mid_year_stub",
        "financial_year_ending_31_march",
        "leap_year",
        "two_switches_in_a_year",
    ]


def run(reg: Any, step: dict[str, Any]) -> None:
    if "switch" in step:
        switch_frequency(
            reg,
            step["switch"],
            iso(step["from"]),
            approval_ref=step.get("approval_ref", ""),
            today=TODAY,
        )
    elif "custom" in step:
        add_custom_period(reg, iso(step["custom"][0]), iso(step["custom"][1]), today=TODAY)
    else:
        with org_context(reg.organisation):
            periods = FilingPeriod.objects.filter(registration=reg).order_by("start")
            for period in periods[: step["file"]]:
                period.status = PeriodStatus.FILED
                period.save(update_fields=["status"])


@pytest.mark.parametrize("scenario", DOCUMENT["scenarios"], ids=lambda s: str(s["name"]))
def test_scenario(scenario: dict[str, Any]) -> None:
    spec = scenario["registration"]
    month, day = (int(x) for x in spec["fye"].split("-"))
    reg = registration(
        scenario["name"], start=iso(spec["start"]), stop=iso(spec["stop"]),
        fye_month=month, fye_day=day,
    )  # fmt: skip
    for step in scenario["steps"]:
        run(reg, step)
    with org_context(reg.organisation):
        periods = list(FilingPeriod.objects.filter(registration=reg).order_by("start"))
    expected = scenario["periods"]
    assert [(p.start.isoformat(), p.end.isoformat(), p.kind) for p in periods] == [
        (e["start"], e["end"], e["kind"]) for e in expected
    ]
    assert periods[0].start == iso(spec["start"]) and periods[-1].end == iso(spec["stop"])
    for a, b in zip(periods, periods[1:], strict=False):
        assert b.start == a.end + dt.timedelta(days=1)
    for period, e in zip(periods, expected, strict=True):
        if "due" in e:
            assert period.due_date.isoformat() == e["due"], f"{e['start']} due"
        if "status" in e:
            assert period.status == e["status"]
        else:
            assert period.status in (PeriodStatus.OPEN, PeriodStatus.CLOSED)
