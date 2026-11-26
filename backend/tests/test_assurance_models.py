"""K-09-T03 — exceptions engine models: rule settings, findings and runs.

Acceptance: migration applies; one open (or acknowledged) finding per fingerprint — resolved and
false-positive rows are history and don't block a new active finding; a false positive needs a
reason; findings and settings are organisation-owned (another organisation sees nothing).
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.assurance.models import (
    ExceptionFinding,
    ExceptionRuleConfig,
    ExceptionRun,
    FindingStatus,
    fingerprint_of,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def _finding(org: Organisation, **fields: object) -> ExceptionFinding:
    values: dict[str, object] = {
        "organisation": org,
        "rule_code": "NEG_CASH",
        "severity": "critical",
        "subject_type": "ledger.Account",
        "subject_id": "acc-1",
        **fields,
    }
    finding = ExceptionFinding(**values)
    finding.save()
    return finding


def test_fingerprint_is_rule_and_subject() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        finding = _finding(org)
    assert finding.fingerprint == fingerprint_of("NEG_CASH", "ledger.Account", "acc-1")
    assert len(finding.fingerprint) == 64
    assert fingerprint_of("NEG_CASH", "ledger.Account", "acc-2") != finding.fingerprint


def test_one_active_finding_per_fingerprint() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        _finding(org)
        with pytest.raises(IntegrityError), transaction.atomic():
            _finding(org, status=FindingStatus.ACKNOWLEDGED)


def test_resolved_and_false_positive_rows_are_history() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        _finding(org, status=FindingStatus.RESOLVED)
        _finding(org, status=FindingStatus.FALSE_POSITIVE, reason="Float counted at night")
        _finding(org)  # a new active one is allowed
        assert ExceptionFinding.objects.count() == 3


def test_false_positive_needs_a_reason() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        _finding(org, status=FindingStatus.FALSE_POSITIVE, reason="")


def test_rule_config_one_per_rule_and_scoped_to_the_organisation() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    other = Organisation.objects.create(name="Other Co.")
    with org_context(org):
        config = ExceptionRuleConfig(organisation=org, rule_code="BACKDATED", params={"days": 3})
        config.save()
        ExceptionRun.objects.create(organisation=org, trigger="manual")
        _finding(org)
        with pytest.raises(IntegrityError), transaction.atomic():
            ExceptionRuleConfig(organisation=org, rule_code="BACKDATED").save()
    with org_context(other):
        assert ExceptionRuleConfig.objects.count() == 0
        assert ExceptionFinding.objects.count() == 0
        assert ExceptionRun.objects.count() == 0
