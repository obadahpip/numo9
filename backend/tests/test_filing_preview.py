"""G-03a-T15 — preview: a proposed change → removed / added / changed periods, writing nothing.
Acceptance: the preview's diff is the actual result after confirming, for a switch, an
out-of-cycle period and its deletion; a refused change is refused in the preview too."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.tax.filing_service import _spans, apply_change, period_rows, preview, switch_frequency
from numo9.tax.models import FilingCycle, FilingPeriod, PeriodStatus, TaxError
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date
TODAY = day(2026, 6, 1)


@pytest.fixture
def reg() -> Any:
    item = registration(stop=day(2026, 12, 31))
    switch_frequency(item, "quarterly", day(2026, 1, 1), today=TODAY)
    return item


def state(reg: Any) -> tuple[list[dict[str, Any]], int, int]:
    with org_context(reg.organisation):
        return (
            period_rows(reg),
            FilingCycle.objects.filter(registration=reg).count(),
            AuditEvent.objects.filter(object_type="orgsettings.TaxRegistration").count(),
        )


def spans(rows: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [(r["start"], r["end"], r["kind"]) for r in rows]


@pytest.mark.parametrize(
    "change",
    [
        {"action": "switch", "frequency": "monthly", "effective_from": day(2026, 7, 1),
         "approval_ref": "2026-GST-48812"},
        {"action": "switch", "frequency": "monthly", "effective_from": day(2026, 8, 15),
         "approval_ref": "2026-GST-48812"},
        {"action": "custom", "start": day(2026, 5, 10), "end": day(2026, 8, 20)},
    ],
    ids=["switch-on-boundary", "switch-mid-period", "custom"],
)  # fmt: skip
def test_preview_is_what_confirming_does(reg: Any, change: dict[str, Any]) -> None:
    before = state(reg)
    shown = preview(reg, change, today=TODAY)
    assert state(reg) == before  # nothing written: no period, cycle or audit event
    done = apply_change(reg, change, today=TODAY)
    assert _spans(shown) == _spans(done)
    assert spans(shown["periods"]) == spans(done["periods"]) == spans(state(reg)[0])
    assert shown["warnings"] == done["warnings"]


def test_switch_diff_names_removed_added_and_changed(reg: Any) -> None:
    shown = preview(
        reg,
        {"action": "switch", "frequency": "monthly", "effective_from": day(2026, 8, 15),
         "approval_ref": "A-9"},
        today=TODAY,
    )  # fmt: skip
    assert spans(shown["removed"]) == [("2026-10-01", "2026-12-31", "regular")]
    assert spans(shown["added"])[:2] == [
        ("2026-08-15", "2026-08-31", "stub"),
        ("2026-09-01", "2026-09-30", "regular"),
    ]
    (cut,) = shown["changed"]
    assert (cut["before"]["end"], cut["after"]["end"], cut["after"]["kind"]) == (
        "2026-09-30", "2026-08-14", "stub",
    )  # fmt: skip
    assert cut["after"]["due_date"] != cut["before"]["due_date"]
    assert [w["code"] for w in shown["warnings"]] == ["tax.filing.not_fiscal_year_start"]


def test_deleting_a_custom_period_previews_and_confirms(reg: Any) -> None:
    apply_change(
        reg, {"action": "custom", "start": day(2026, 7, 1), "end": day(2026, 8, 15)}, today=TODAY
    )
    with org_context(reg.organisation):
        custom = FilingPeriod.objects.get(registration=reg, kind="custom")
    change = {"action": "delete_custom", "period": custom.public_id}
    shown = preview(reg, change, today=TODAY)
    assert spans(shown["removed"])[0] == ("2026-07-01", "2026-08-15", "custom")
    done = apply_change(reg, change, today=TODAY)
    assert _spans(shown) == _spans(done)
    assert spans(done["periods"])[2:] == [
        ("2026-07-01", "2026-09-30", "regular"),
        ("2026-10-01", "2026-12-31", "regular"),
    ]


def test_a_refused_change_is_refused_in_the_preview(reg: Any) -> None:
    with org_context(reg.organisation):
        first = FilingPeriod.objects.filter(registration=reg).order_by("start")[0]
        first.status = PeriodStatus.FILED
        first.save()
    before = state(reg)
    for change, code in (
        ({"action": "switch", "frequency": "monthly", "effective_from": day(2026, 2, 1),
          "approval_ref": "A-1"}, "tax.filing.inside_filed"),
        ({"action": "switch", "frequency": "monthly", "effective_from": day(2026, 7, 1)},
         "tax.filing.approval_required"),
        ({"action": "custom", "start": day(2026, 3, 1), "end": day(2026, 4, 30)},
         "tax.filing.custom_overlaps_filed"),
        ({"action": "nothing"}, "tax.filing.action"),
    ):  # fmt: skip
        with pytest.raises(TaxError) as error:
            preview(reg, change, today=TODAY)
        assert error.value.code == code
    assert state(reg) == before


def test_changes_are_audited_on_the_registration(reg: Any) -> None:
    apply_change(
        reg,
        {"action": "switch", "frequency": "monthly", "effective_from": day(2026, 7, 1),
         "approval_ref": "2026-GST-48812"},
        today=TODAY,
    )  # fmt: skip
    with org_context(reg.organisation):
        event = AuditEvent.objects.filter(action="tax.filing.frequency_changed").latest("pk")
    assert event.changes == {"frequency": ["quarterly", "monthly"]}
    assert event.meta["effective_from"] == "2026-07-01"
    assert event.meta["approval_ref"] == "2026-GST-48812"
    assert event.object_type == "orgsettings.TaxRegistration"
