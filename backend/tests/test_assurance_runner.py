"""K-09-T05 — runner: full run, incremental run on posting, dedupe / reopen / resolve.

Acceptance: re-running creates no duplicates; a resolved finding whose condition recurs is
reopened (same row); a false positive recurring with the same amount stays silent, with a
different amount it is a new finding; a cleared condition resolves the finding; an incremental
run re-checks only the scope's subjects; disabled rules are skipped (and their findings
resolved on a full run); posting a journal queues one incremental job for its journal and
accounts at commit; the nightly job starts one run per organisation.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

import pytest
from django.utils.translation import gettext_lazy as lazy

from numo9.assurance.models import (
    ExceptionFinding,
    ExceptionRuleConfig,
    FindingStatus,
)
from numo9.assurance.rules.base import Context, Hit, Rule, RuleRegistry, Scope
from numo9.assurance.runner import JOB, run, run_all, run_job
from numo9.audit.models import AuditEvent
from numo9.ledger.services import post_journal
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.job_helpers import deliver
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db

#: What the dummy rule finds: subject id → amount.
STATE: dict[str, Decimal] = {}


class Dummy(Rule):
    code = "DUMMY"
    name = lazy("Dummy")
    incremental = True

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        for subject, amount in STATE.items():
            if ctx.scope is None or subject in ctx.scope.entries:
                yield Hit("ledger.JournalEntry", subject, subject, amount, {"x": 1})


class OrgLevel(Rule):
    code = "ORG_LEVEL"
    name = lazy("Organisation level")

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        yield Hit("tenancy.Organisation", str(ctx.organisation.public_id), "Org")


@pytest.fixture
def rules() -> Iterable[RuleRegistry]:
    registry = RuleRegistry()
    registry.register(Dummy)
    registry.register(OrgLevel)
    STATE.clear()
    yield registry
    STATE.clear()


def _findings(org: Organisation, **filters: Any) -> list[ExceptionFinding]:
    with org_context(org):
        return list(ExceptionFinding.objects.filter(rule_code="DUMMY", **filters).order_by("pk"))


def test_rerun_creates_no_duplicates(rules: RuleRegistry) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    STATE.update({"a": Decimal("10.00"), "b": Decimal("20.00")})
    first = run(org, rules=rules)
    assert first.counts["created"] == 3 and first.rules == ["DUMMY", "ORG_LEVEL"]
    second = run(org, rules=rules)
    assert second.counts["created"] == 0 and second.counts["updated"] == 3
    assert len(_findings(org)) == 2
    with org_context(org):
        assert AuditEvent.objects.filter(action="assurance.finding.opened").count() == 3


def test_cleared_condition_resolves_and_recurrence_reopens(rules: RuleRegistry) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    STATE["a"] = Decimal("10.00")
    run(org, rules=rules)
    (finding,) = _findings(org)
    STATE.clear()
    assert run(org, rules=rules).counts["resolved"] == 1
    finding.refresh_from_db()
    assert finding.status == FindingStatus.RESOLVED and finding.resolved_at is not None
    STATE["a"] = Decimal("12.00")
    assert run(org, rules=rules).counts["reopened"] == 1
    (again,) = _findings(org)
    assert again.pk == finding.pk
    assert (again.status, again.resolved_at, again.amount) == ("open", None, Decimal("12.00"))
    with org_context(org):
        assert AuditEvent.objects.filter(action="assurance.finding.reopened").count() == 1


def test_false_positive_same_amount_stays_silent_different_amount_is_new(
    rules: RuleRegistry,
) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    STATE["a"] = Decimal("10.00")
    run(org, rules=rules)
    (finding,) = _findings(org)
    with org_context(org):
        finding.status, finding.reason = FindingStatus.FALSE_POSITIVE, "Known float"
        finding.save()
    assert run(org, rules=rules).counts["suppressed"] == 1
    assert len(_findings(org)) == 1
    STATE["a"] = Decimal("15.00")
    assert run(org, rules=rules).counts["created"] == 1
    rows = _findings(org)
    assert [r.status for r in rows] == ["false_positive", "open"]
    assert rows[1].amount == Decimal("15.00")
    # and it is deduplicated from then on
    run(org, rules=rules)
    assert len(_findings(org)) == 2


def test_incremental_run_rechecks_only_the_scope(rules: RuleRegistry) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    STATE.update({"a": Decimal("1"), "b": Decimal("2")})
    run(org, rules=rules)
    STATE.clear()  # both conditions cleared, but only "a" is posted again
    done = run(org, scope=Scope(entries=frozenset({"a"})), trigger="posting", rules=rules)
    assert done.rules == ["DUMMY"]  # ORG_LEVEL isn't incremental
    statuses = {f.subject_id: f.status for f in _findings(org)}
    assert statuses == {"a": "resolved", "b": "open"}


def test_disabled_rule_is_skipped_and_its_findings_resolved(rules: RuleRegistry) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    STATE["a"] = Decimal("1")
    run(org, rules=rules)
    with org_context(org):
        ExceptionRuleConfig(organisation=org, rule_code="DUMMY", enabled=False).save()
    done = run(org, rules=rules)
    assert done.rules == ["ORG_LEVEL"]
    assert [f.status for f in _findings(org)] == ["resolved"]


def test_posting_queues_one_incremental_job(sent: list[dict[str, Any]], settings: Any) -> None:
    settings.NUMO9_ASSURANCE_ON_POSTING = True
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        entry = post_journal(pay(accounts["office"], accounts["chequing"], "10.00"), user=None)
    (message,) = [m for m in sent if m["task"] == JOB]
    kwargs = message["kwargs"]
    assert kwargs["trigger"] == "posting"
    assert kwargs["scope"]["entries"] == [str(entry.public_id)]
    assert set(kwargs["scope"]["accounts"]) == {
        str(accounts["office"].public_id),
        str(accounts["chequing"].public_id),
    }
    result = deliver(run_job, message)
    assert result["counts"]["seen"] >= 0


def test_nightly_starts_one_run_per_organisation(sent: list[dict[str, Any]]) -> None:
    Organisation.objects.create(name="A")
    Organisation.objects.create(name="B")
    count = Organisation.objects.count()
    assert run_all(dt.datetime(2026, 6, 15, 8, tzinfo=dt.UTC)) == count
    assert run_all(dt.datetime(2026, 6, 15, 9, tzinfo=dt.UTC)) == count  # same day: same keys
    assert len([m for m in sent if m["task"] == JOB]) == count
