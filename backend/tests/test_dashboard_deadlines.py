"""V-04-T05 — deadline provider interface + stub (filled by G-03a/N-07 later).

Acceptance: the Phase 0 stub returns [] safely (the widget answers ok with no item); a registered
provider's deadlines appear sorted by date, only for organisations of the dashboard's scope and
within the next 30 days.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from django.utils import timezone

from numo9.tenancy.models import PracticeMember
from numo9.workspace.dashboard import ALL, MINE, DashboardContext, answer_all
from numo9.workspace.widgets import (
    Deadline,
    no_deadlines_yet,
    register_deadline_provider,
    unregister_deadline_provider,
)
from tests.dashboard_helpers import Firm, build_firm

pytestmark = pytest.mark.django_db


@pytest.fixture
def firm() -> Firm:
    return build_firm()


def deadlines(firm: Firm, person: PracticeMember, scope: str = ALL) -> dict[str, object]:
    ctx = DashboardContext(user=person.user, practice=firm.practice, member=person, scope=scope)
    (widget,) = [w for w in answer_all(ctx) if w["key"] == "deadlines"]
    return widget


def admin(firm: Firm) -> PracticeMember:
    return PracticeMember.objects.get(practice=firm.practice, user=firm.admin)


def test_stub_returns_nothing_safely(firm: Firm) -> None:
    today = timezone.localdate()
    assert no_deadlines_yet({1, 2}, today, today + dt.timedelta(days=30)) == []
    widget = deadlines(firm, admin(firm))
    assert (widget["status"], widget["kind"], widget["count"], widget["items"]) == (
        "ok",
        "list",
        0,
        [],
    )


@pytest.fixture
def gst(firm: Firm) -> Iterator[None]:
    today = timezone.localdate()
    maple, pine = firm.orgs["Maple"].pk, firm.orgs["Pine"].pk

    def provider(orgs: set[int], start: dt.date, end: dt.date) -> list[Deadline]:
        return [
            Deadline(today + dt.timedelta(days=20), "gst_hst", "GST/HST return", pine),
            Deadline(today + dt.timedelta(days=5), "gst_hst", "GST/HST return", maple),
            Deadline(today + dt.timedelta(days=45), "t2", "T2 return", maple),  # after 30 days
        ]

    register_deadline_provider("test.gst", provider)
    yield
    unregister_deadline_provider("test.gst")


def test_registered_deadlines_sorted_within_30_days_and_scope(firm: Firm, gst: None) -> None:
    widget = deadlines(firm, admin(firm))
    assert [(i["organisation_name"], i["kind"]) for i in widget["items"]] == [  # type: ignore[attr-defined]
        ("Maple", "gst_hst"),
        ("Pine", "gst_hst"),
    ]
    mine = deadlines(firm, firm.sam, MINE)  # Sam serves Maple, not Pine
    assert [i["organisation_name"] for i in mine["items"]] == ["Maple"]  # type: ignore[attr-defined]
