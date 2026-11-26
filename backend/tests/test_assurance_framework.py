"""K-09-T04 — rule plug-in framework: base class, registry, parameter schema validation,
``evaluate(org, scope)`` → hits, ``propose_fix(finding)`` → draft journal payload.

Acceptance: two dummy rules register and run; a duplicate code is refused; parameters are
validated (type, min, max, choices, unknown key) with defaults filled; the organisation's
settings (``ExceptionRuleConfig``) are read; ``explain`` formats amounts and dates.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from numo9.assurance.models import ExceptionFinding, ExceptionRuleConfig
from numo9.assurance.rules.base import (
    Context,
    FixProposal,
    Hit,
    Param,
    Rule,
    RuleRegistry,
    Scope,
    clean_params,
    evaluate,
    settings_for,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


class CountJournals(Rule):
    code = "DUMMY_COUNT"
    name = _("Dummy count")
    explanation = _("%(count)s things on %(day)s for %(total)s.")
    money_keys = ("total",)
    date_keys = ("day",)
    params = {
        "limit": Param("int", 2, _("Limit"), minimum=1, maximum=10),
        "mode": Param("choice", "a", _("Mode"), choices=("a", "b")),
        "amount": Param("decimal", Decimal("100.00"), _("Amount"), minimum=Decimal("0")),
        "strict": Param("bool", False, _("Strict")),
    }
    incremental = True

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        for n in range(ctx.params["limit"]):
            if ctx.scope is None or str(n) in ctx.scope.entries:
                yield Hit("ledger.JournalEntry", str(n), f"Thing {n}", Decimal(n), {"n": n})


class AlwaysOrg(Rule):
    code = "DUMMY_ORG"
    name = _("Dummy organisation")
    has_fix = True

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        yield Hit("tenancy.Organisation", str(ctx.organisation.public_id), "Org")

    def propose_fix(self, finding: ExceptionFinding, ctx: Context) -> FixProposal | None:
        return FixProposal("journal", "because", date=ctx.today, lines=[{"debit": "1.00"}])


@pytest.fixture
def rules() -> RuleRegistry:
    registry = RuleRegistry()
    registry.register(CountJournals)
    registry.register(AlwaysOrg)
    return registry


def test_two_dummy_rules_register_and_run(rules: RuleRegistry) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    assert rules.codes() == ["DUMMY_COUNT", "DUMMY_ORG"]
    hits = evaluate(org, "DUMMY_COUNT", rules=rules)
    assert [h.subject_id for h in hits] == ["0", "1"]
    (org_hit,) = evaluate(org, "DUMMY_ORG", rules=rules)
    assert org_hit.subject_id == str(org.public_id)
    # incremental scope: only the scope's journals are checked
    scoped = evaluate(org, "DUMMY_COUNT", Scope(entries=frozenset({"1"})), rules=rules)
    assert [h.subject_id for h in scoped] == ["1"]


def test_propose_fix_returns_a_draft_payload(rules: RuleRegistry) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    rule = rules.get("DUMMY_ORG")
    ctx = Context(org, {}, "warning", now=dt.datetime(2026, 6, 15, 12, tzinfo=dt.UTC))
    fix = rule.propose_fix(ExceptionFinding(rule_code="DUMMY_ORG"), ctx)
    assert fix is not None
    assert fix.as_dict()["date"] == "2026-06-15"
    assert rules.get("DUMMY_COUNT").propose_fix(ExceptionFinding(), ctx) is None


def test_duplicate_code_and_bad_codes_are_refused(rules: RuleRegistry) -> None:
    class Again(CountJournals):
        pass

    with pytest.raises(ValueError, match="registered already"):
        rules.register(Again)

    class Lower(Rule):
        code = "lower"

    with pytest.raises(ValueError):
        rules.register(Lower)
    with pytest.raises(LookupError):
        rules.get("NOPE")


def test_parameters_are_validated_and_defaults_filled(rules: RuleRegistry) -> None:
    rule = rules.get("DUMMY_COUNT")
    assert clean_params(rule, {}) == {
        "limit": 2,
        "mode": "a",
        "amount": Decimal("100.00"),
        "strict": False,
    }
    assert clean_params(rule, {"limit": "5", "amount": "12.5"})["amount"] == Decimal("12.50")
    for bad in (
        {"limit": 0},
        {"limit": 11},
        {"limit": "x"},
        {"limit": 1.5},
        {"mode": "c"},
        {"strict": "yes"},
        {"amount": -1},
        {"unknown": 1},
    ):
        with pytest.raises(ValidationError) as error:
            clean_params(rule, bad)
        assert error.value.code == "assurance.param_invalid"
        assert error.value.params is not None and error.value.params["param"] in bad


def test_organisation_settings_are_read(rules: RuleRegistry) -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    rule = rules.get("DUMMY_COUNT")
    assert settings_for(org, rule).enabled is True
    with org_context(org):
        ExceptionRuleConfig(
            organisation=org,
            rule_code="DUMMY_COUNT",
            enabled=False,
            severity="critical",
            params={"limit": 3},
        ).save()
    found = settings_for(org, rule)
    assert (found.enabled, found.severity, found.params["limit"]) == (False, "critical", 3)
    assert len(evaluate(org, "DUMMY_COUNT", rules=rules)) == 3


def test_explain_formats_amounts_and_dates(rules: RuleRegistry) -> None:
    rule = rules.get("DUMMY_COUNT")
    text = rule.explain({"count": 2, "day": "2026-06-15", "total": "-994.17"})
    assert text == "2 things on 15 Jun 2026 for −994.17."
    assert rule.schema()["params"][0] == {
        "name": "limit",
        "kind": "int",
        "label": "Limit",
        "default": 2,
        "minimum": 1,
        "maximum": 10,
        "choices": [],
    }
