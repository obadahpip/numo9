"""K-09-T18 — assurance score (0–100, weighted by severity) and summary; practice aggregation.

Acceptance: the score decreases with critical findings (more than with warnings or info); an
acknowledged finding costs half, resolved and false positives nothing; one rule counts at most
three findings; the score never goes below 0; the summary counts by severity and status and
groups by rule; the practice summary aggregates organisations.
"""

from __future__ import annotations

import pytest

from numo9.assurance.score import practice_summary, score_of, summary
from numo9.tenancy.models import Organisation
from tests.assurance_helpers import NOW, at, refined

pytestmark = pytest.mark.django_db


def test_score_decreases_with_critical_findings() -> None:
    assert score_of([]) == 100
    one_info = score_of([("A", "info", "open")])
    one_warning = score_of([("A", "warning", "open")])
    one_critical = score_of([("A", "critical", "open")])
    assert 100 > one_info > one_warning > one_critical == 85
    assert score_of([("A", "critical", "open"), ("B", "critical", "open")]) == 70


def test_acknowledged_half_resolved_and_false_positive_free_cap_and_floor() -> None:
    assert score_of([("A", "critical", "acknowledged")]) == 93  # 100 − 7.5, rounded half up
    assert score_of([("A", "critical", "resolved"), ("A", "critical", "false_positive")]) == 100
    five = [("A", "warning", "open")] * 5
    assert score_of(five) == 85  # three counted
    many = [(f"R{n}", "critical", "open") for n in range(10)]
    assert score_of(many) == 0


def test_teardown_summary() -> None:
    books = refined()
    from numo9.assurance.runner import run

    with at(NOW):
        run(books["org"], now=NOW)
    found = summary(books["org"])
    assert found["score"] < 50
    assert found["open"]["critical"] >= 3  # NEG_CASH, MISSING_BN, UNBALANCED_CONVERSION
    assert found["attention"] == found["open"]["critical"] + found["open"]["warning"]
    codes = [g["rule"] for g in found["rules"]]
    assert {"NEG_CASH", "MISSING_BN", "UNBALANCED_CONVERSION"} == set(codes[:3])
    assert found["rules"][0]["severity"] == "critical"
    assert found["last_run"] is not None
    other = Organisation.objects.create(name="Clean Co.")
    practice = practice_summary([books["org"], other])
    assert practice["count"] == 2 and practice["lowest_score"] == found["score"]
    assert practice["organisations"][0]["name"] == "REFINED Interiors Inc."
    assert practice["critical"] == found["open"]["critical"]
