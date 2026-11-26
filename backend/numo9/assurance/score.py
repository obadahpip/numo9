"""Assurance score and summary (K-09-T18).

``score = max(0, round(100 − penalty))``: each **open** finding costs its severity's weight —
critical 15, warning 5, info 1 — an **acknowledged** one half of it, and each rule counts at most
``PER_RULE_CAP`` findings (one noisy rule can't empty the score alone). Resolved and
false-positive findings cost nothing.

``summary(organisation)`` — the score, counts by severity (open) and by status, the open
findings per rule (most severe first) and the last run. ``practice_summary(organisations)`` —
the practice-level aggregation V-04 reads (average and lowest score, critical findings, the
organisations needing attention first).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from numo9.tenancy.context import org_context

from .models import (
    ACTIVE_STATUSES,
    SEVERITY_ORDER,
    ExceptionFinding,
    ExceptionRun,
    FindingStatus,
    Severity,
)
from .rules.base import registry

WEIGHTS: dict[str, Decimal] = {
    Severity.CRITICAL: Decimal("15"),
    Severity.WARNING: Decimal("5"),
    Severity.INFO: Decimal("1"),
}
ACKNOWLEDGED_SHARE = Decimal("0.5")
PER_RULE_CAP = 3


def score_of(findings: Iterable[tuple[str, str, str]]) -> int:
    """``findings`` = (rule code, severity, status) of the active findings."""
    per_rule: dict[str, list[Decimal]] = defaultdict(list)
    for rule, severity, status in findings:
        if status not in ACTIVE_STATUSES:
            continue
        weight = WEIGHTS.get(severity, Decimal("0"))
        if status == FindingStatus.ACKNOWLEDGED:
            weight *= ACKNOWLEDGED_SHARE
        per_rule[rule].append(weight)
    penalty = sum(
        (
            sum(sorted(costs, reverse=True)[:PER_RULE_CAP], Decimal("0"))
            for costs in per_rule.values()
        ),
        Decimal("0"),
    )
    value = (Decimal("100") - penalty).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(0, int(value))


def _rule_name(code: str) -> str:
    return str(registry.get(code).name) if code in registry else code


def summary(organisation: Any) -> dict[str, Any]:
    with org_context(organisation):
        rows = list(
            ExceptionFinding.objects.values_list("rule_code", "severity", "status").order_by()
        )
        last = ExceptionRun.objects.filter(status="succeeded").order_by("-started_at").first()
    active = [r for r in rows if r[2] in ACTIVE_STATUSES]
    by_status = Counter(status for _rule, _severity, status in rows)
    open_by_severity = Counter(
        severity for _rule, severity, status in active if status == FindingStatus.OPEN
    )
    groups: dict[tuple[str, str], int] = Counter((rule, severity) for rule, severity, _s in active)
    rules = sorted(
        (
            {"rule": rule, "name": _rule_name(rule), "severity": severity, "count": count}
            for (rule, severity), count in groups.items()
        ),
        key=lambda g: (SEVERITY_ORDER.get(str(g["severity"]), 9), str(g["name"])),
    )
    return {
        "score": score_of(rows),
        "open": {
            s: open_by_severity.get(s, 0)
            for s in (Severity.CRITICAL, Severity.WARNING, Severity.INFO)
        },
        "statuses": {s: by_status.get(s, 0) for s in FindingStatus.values},
        "attention": open_by_severity.get(Severity.CRITICAL, 0)
        + open_by_severity.get(Severity.WARNING, 0),
        "rules": rules,
        "last_run": (
            {
                "id": str(last.public_id),
                "trigger": last.trigger,
                "started_at": last.started_at.isoformat(),
                "finished_at": last.finished_at.isoformat() if last.finished_at else None,
            }
            if last is not None
            else None
        ),
    }


def practice_summary(organisations: Iterable[Any]) -> dict[str, Any]:
    """V-04's aggregation over the organisations a practice serves (each one scoped on its own)."""
    rows = []
    for organisation in organisations:
        found = summary(organisation)
        rows.append(
            {
                "organisation": str(organisation.public_id),
                "name": organisation.name,
                "score": found["score"],
                "critical": found["open"][Severity.CRITICAL],
                "attention": found["attention"],
            }
        )
    rows.sort(key=lambda r: (r["score"], r["name"]))
    scores = [r["score"] for r in rows]
    return {
        "organisations": rows,
        "count": len(rows),
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "lowest_score": min(scores) if scores else None,
        "critical": sum(r["critical"] for r in rows),
    }
