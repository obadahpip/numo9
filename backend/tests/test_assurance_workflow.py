"""K-09-T17 — finding workflow: acknowledge, false positive with a reason, reopen, automatic
resolution when the condition clears; every transition audited.

Acceptance: status transitions audited (person, old → new status, reason); a false positive
needs a reason; illegal transitions are refused; an acknowledged finding is resolved when its
condition clears.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

import pytest
from django.utils.translation import gettext_lazy as _

from numo9.assurance.models import ExceptionFinding
from numo9.assurance.rules.base import Context, Hit, Rule, RuleRegistry
from numo9.assurance.runner import run
from numo9.assurance.workflow import (
    WorkflowRefused,
    acknowledge,
    mark_false_positive,
    reopen,
)
from numo9.audit.models import AuditEvent
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
PRESENT: list[str] = []


class Present(Rule):
    code = "PRESENT"
    name = _("Present")

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        for subject in PRESENT:
            yield Hit("ledger.JournalEntry", subject, subject, Decimal("5.00"))


@pytest.fixture
def setup() -> Iterable[tuple[Organisation, RuleRegistry, ExceptionFinding, object]]:
    registry = RuleRegistry()
    registry.register(Present)
    PRESENT[:] = ["a"]
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    run(org, rules=registry)
    with org_context(org):
        finding = ExceptionFinding.objects.get()
        owner = people(org)["owner"]
    yield org, registry, finding, owner
    PRESENT.clear()


def _events(org: Organisation, action: str) -> list[AuditEvent]:
    with org_context(org):
        return list(AuditEvent.objects.filter(action=action))


def test_transitions_are_audited(setup: tuple) -> None:  # type: ignore[type-arg]
    org, _registry, finding, owner = setup
    done = acknowledge(finding, owner, "Owner to fund the float")
    assert (done.status, done.ack_by, done.reason) == (
        "acknowledged",
        owner,
        "Owner to fund the float",
    )
    assert done.ack_at is not None
    (event,) = _events(org, "assurance.finding.acknowledged")
    assert event.changes == {"status": ["open", "acknowledged"]}
    assert event.actor_user_id == owner.pk  # type: ignore[attr-defined]
    done = mark_false_positive(done, owner, "Float counted at night")
    (event,) = _events(org, "assurance.finding.false_positive")
    assert event.changes == {"status": ["acknowledged", "false_positive"]}
    assert event.meta["reason"] == "Float counted at night"
    done = reopen(done, owner)
    assert (done.status, done.ack_by, done.reason) == ("open", None, "")
    assert len(_events(org, "assurance.finding.reopened")) == 1


def test_false_positive_needs_a_reason_and_illegal_moves_are_refused(setup: tuple) -> None:  # type: ignore[type-arg]
    _org, _registry, finding, owner = setup
    with pytest.raises(WorkflowRefused) as error:
        mark_false_positive(finding, owner, "  no ")
    assert error.value.code == "assurance.finding.reason_required"
    with pytest.raises(WorkflowRefused) as error:
        reopen(finding, owner)  # open already
    assert error.value.code == "assurance.finding.transition"
    acknowledge(finding, owner)
    with pytest.raises(WorkflowRefused):
        acknowledge(finding, owner)


def test_acknowledged_finding_resolves_when_the_condition_clears(setup: tuple) -> None:  # type: ignore[type-arg]
    org, registry, finding, owner = setup
    acknowledge(finding, owner)
    PRESENT.clear()
    run(org, rules=registry, now=dt.datetime(2026, 12, 1, tzinfo=dt.UTC))
    finding.refresh_from_db()
    assert finding.status == "resolved"
    assert len(_events(org, "assurance.finding.resolved")) == 1
    with pytest.raises(WorkflowRefused):
        acknowledge(finding, owner)


def test_reopening_a_false_positive_with_a_newer_finding_is_refused(setup: tuple) -> None:  # type: ignore[type-arg]
    org, registry, finding, owner = setup
    mark_false_positive(finding, owner, "Known float")
    with org_context(org):
        ExceptionFinding(
            organisation=org,
            rule_code="PRESENT",
            severity="warning",
            subject_type="ledger.JournalEntry",
            subject_id="a",
            amount=Decimal("9.00"),
        ).save()
    with pytest.raises(WorkflowRefused):
        reopen(finding, owner)
