"""History preview of a bank rule (F-04-T08): "test against history" without writing anything.

``preview_rule(candidate, days=90)`` runs the candidate — a saved rule or the builder's unsaved
form — together with the organisation's other active rules over the statement lines of the last
``days`` days (90 by default) that rules may code (the apply service's own test: Uncoded, no
transaction yet, not in a locked period). For every line the candidate matches it says:

- ``applies`` — the candidate would win and code it; ``also_matches`` lists the lower-priority
  rules it shadows (the conflicts);
- ``shadowed`` — a higher-priority rule wins (``shadowed_by``) and the candidate would not run.

Nothing is written. The number of ``applies`` rows equals what ``apply_rules`` codes with the
rule on the same data (integration-tested).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from ..models import StatementLine, StatementLineStatus
from .apply import reverted_rules, skip_reason
from .conditions import LineFacts
from .engine import RuleSpec, choose, load_rules

DEFAULT_DAYS = 90
MAX_ROWS = 500


@dataclass(frozen=True)
class PreviewRow:
    line: StatementLine
    outcome: str  # "applies" | "shadowed"
    shadowed_by: RuleSpec | None = None
    also_matches: tuple[RuleSpec, ...] = ()


@dataclass
class PreviewResult:
    since: dt.date
    days: int
    rows: list[PreviewRow] = field(default_factory=list)
    scanned: int = 0

    @property
    def applies(self) -> int:
        return sum(1 for row in self.rows if row.outcome == "applies")

    @property
    def shadowed(self) -> int:
        return sum(1 for row in self.rows if row.outcome == "shadowed")


def history_lines(since: dt.date) -> Any:
    return (
        StatementLine.objects.select_related("bank_account", "organisation")
        .filter(status=StatementLineStatus.UNCODED, bank_transaction__isnull=True, date__gte=since)
        .order_by("-date", "-pk")
    )


def preview_rule(
    candidate: RuleSpec,
    *,
    days: int = DEFAULT_DAYS,
    today: dt.date | None = None,
    user: Any = None,
) -> PreviewResult:
    """What ``candidate`` would do to the last ``days`` days of lines (module docstring)."""
    since = (today or timezone.localdate()) - dt.timedelta(days=days)
    rules = [*load_rules(exclude=candidate.id), candidate]
    result = PreviewResult(since=since, days=days)
    for line in history_lines(since):
        facts = LineFacts.of(line)
        if not candidate.matches(facts):
            continue
        result.scanned += 1
        if skip_reason(line, user) is not None:
            continue
        outcome = choose(rules, facts)
        if outcome.winner is not None and outcome.winner.id in reverted_rules(line):
            continue  # a reverted rule never codes that line again (apply skips it too)
        if outcome.winner is candidate:
            row = PreviewRow(line, "applies", also_matches=outcome.shadowed)
        else:
            row = PreviewRow(line, "shadowed", shadowed_by=outcome.winner)
        result.rows.append(row)
    return result
