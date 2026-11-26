"""Rule plug-in framework (K-09-T04): base class, parameter schema, registry, evaluation.

A rule is a ``Rule`` subclass registered with ``@register``:

    @register
    class Backdated(Rule):
        code = "BACKDATED"
        name = _("Backdated posting")
        description = _("Posted more than N days after the document date.")
        explanation = _("%(document)s is dated %(date)s but was posted on %(posted)s …")
        default_severity = Severity.WARNING
        params = {"days": Param("int", 7, _("Days"), minimum=1, maximum=365)}
        incremental = True

        def evaluate(self, ctx):        # → Hit per subject that has the problem
            ...

        def propose_fix(self, finding, ctx):   # optional → FixProposal (a draft journal payload)
            ...

- ``evaluate(ctx)`` — ``ctx.organisation``, ``ctx.params`` (validated, defaults filled),
  ``ctx.scope`` (``None`` = a full run; a ``Scope`` of entry and account public ids for an
  incremental run — the rule then checks those only), ``ctx.now`` / ``ctx.today`` (the
  organisation's local date).
- ``covers(ctx, finding)`` — in an incremental run, whether the rule re-checked the finding's
  subject (an open finding it no longer hits is then resolved). Default: the subject is one of
  the scope's journals (``ledger.JournalEntry``) or accounts (``ledger.Account``).
- ``explain(details)`` — the plain-language sentence of a finding from its ``details``
  (``money_keys`` formatted as amounts, ``date_keys`` as dates, in the active language).
- Parameters are validated by ``clean_params`` against ``params`` (type, minimum, maximum,
  choices); an unknown key or a bad value raises ``ValidationError``
  (``assurance.param_invalid``, ``params.param`` the name).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, ClassVar
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.functional import Promise
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.ledger.cash_guard import format_day, format_signed

from ..models import Severity

if TYPE_CHECKING:
    from ..models import ExceptionFinding

PARAM_KINDS = ("int", "decimal", "bool", "choice", "str", "codes")


def _invalid(name: str, message: Any) -> ValidationError:
    return ValidationError(message, code="assurance.param_invalid", params={"param": name})


@dataclass(frozen=True)
class Param:
    """One parameter of a rule: its type, default, label and limits."""

    kind: str
    default: Any
    label: Promise
    minimum: Any = None
    maximum: Any = None
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in PARAM_KINDS:
            raise ValueError(f"Unknown parameter kind {self.kind!r}.")

    def clean(self, name: str, value: Any) -> Any:
        if self.kind == "bool":
            if isinstance(value, bool):
                return value
            raise _invalid(name, _("%(param)s must be on or off.") % {"param": self.label})
        if self.kind == "choice":
            if value in self.choices:
                return value
            raise _invalid(
                name,
                _("%(param)s must be one of: %(choices)s.")
                % {"param": self.label, "choices": ", ".join(self.choices)},
            )
        if self.kind == "str":
            if isinstance(value, str) and len(value) <= 100:
                return value.strip()
            raise _invalid(name, _("%(param)s must be a short text.") % {"param": self.label})
        if self.kind == "codes":
            if isinstance(value, list) and all(isinstance(v, str) and v for v in value):
                return [v.strip() for v in value]
            raise _invalid(
                name, _("%(param)s must be a list of account codes.") % {"param": self.label}
            )
        number: Any
        try:
            if isinstance(value, bool):
                raise TypeError
            if self.kind == "int":
                if isinstance(value, float) and not value.is_integer():
                    raise TypeError
                number = int(str(value))
            else:
                number = Decimal(str(value)).quantize(Decimal("0.01"))
        except (TypeError, ValueError, InvalidOperation):
            raise _invalid(name, _("%(param)s must be a number.") % {"param": self.label}) from None
        if self.minimum is not None and number < self.minimum:
            raise _invalid(
                name,
                _("%(param)s must be at least %(min)s.")
                % {"param": self.label, "min": self.minimum},
            )
        if self.maximum is not None and number > self.maximum:
            raise _invalid(
                name,
                _("%(param)s must be at most %(max)s.")
                % {"param": self.label, "max": self.maximum},
            )
        return number

    def as_dict(self, name: str) -> dict[str, Any]:
        def plain(value: Any) -> Any:
            return f"{value:.2f}" if isinstance(value, Decimal) else value

        return {
            "name": name,
            "kind": self.kind,
            "label": str(self.label),
            "default": plain(self.default),
            "minimum": plain(self.minimum),
            "maximum": plain(self.maximum),
            "choices": list(self.choices),
        }


def json_params(values: Mapping[str, Any]) -> dict[str, Any]:
    """Parameter values as stored in JSON (decimals as strings)."""
    return {k: (f"{v:.2f}" if isinstance(v, Decimal) else v) for k, v in values.items()}


@dataclass(frozen=True)
class Scope:
    """What an incremental run re-checks: journals and accounts (public ids, as strings)."""

    entries: frozenset[str] = frozenset()
    accounts: frozenset[str] = frozenset()

    def as_dict(self) -> dict[str, list[str]]:
        return {"entries": sorted(self.entries), "accounts": sorted(self.accounts)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Scope:
        return cls(
            frozenset(str(e) for e in data.get("entries", ())),
            frozenset(str(a) for a in data.get("accounts", ())),
        )


@dataclass
class Context:
    organisation: Any
    params: dict[str, Any]
    severity: str
    scope: Scope | None = None
    now: dt.datetime = field(default_factory=timezone.now)

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(getattr(self.organisation, "time_zone", "") or "America/Toronto")

    @property
    def today(self) -> dt.date:
        return self.now.astimezone(self.zone).date()

    @property
    def full(self) -> bool:
        return self.scope is None


@dataclass
class Hit:
    """A subject the rule found a problem with."""

    subject_type: str
    subject_id: str
    label: str = ""
    amount: Decimal | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FixProposal:
    """A proposed correcting entry (``kind="journal"``: a draft journal payload, never posted
    by the engine) or a link to another tool (``kind="recode"``: a prefilled find & recode)."""

    kind: str
    reasoning: str
    date: dt.date | None = None
    narration: str = ""
    lines: list[dict[str, Any]] = field(default_factory=list)
    recode: dict[str, Any] | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reasoning": self.reasoning,
            "date": self.date.isoformat() if self.date else None,
            "narration": self.narration,
            "lines": self.lines,
            "recode": self.recode,
            "alternatives": self.alternatives,
        }


def fix_line(
    account: Any,
    *,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    description: str = "",
) -> dict[str, Any]:
    return {
        "account": str(account.public_id),
        "code": account.code,
        "label": str(account),
        "debit": f"{debit:.2f}",
        "credit": f"{credit:.2f}",
        "description": description,
    }


class Rule:
    code: ClassVar[str] = ""
    name: ClassVar[Promise] = gettext_lazy("Rule")
    description: ClassVar[Promise | str] = ""  # not gettext(""): that is the catalogue header
    explanation: ClassVar[Promise | str] = ""
    default_severity: ClassVar[str] = Severity.WARNING
    params: ClassVar[dict[str, Param]] = {}
    incremental: ClassVar[bool] = False
    has_fix: ClassVar[bool] = False
    money_keys: ClassVar[tuple[str, ...]] = ()
    date_keys: ClassVar[tuple[str, ...]] = ()

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        raise NotImplementedError

    def covers(self, ctx: Context, finding: ExceptionFinding) -> bool:
        scope = ctx.scope
        if scope is None:
            return True
        if finding.subject_type == "ledger.JournalEntry":
            return finding.subject_id in scope.entries
        if finding.subject_type == "ledger.Account":
            return finding.subject_id in scope.accounts
        return False

    def propose_fix(self, finding: ExceptionFinding, ctx: Context) -> FixProposal | None:
        return None

    def display(self, details: Mapping[str, Any]) -> dict[str, Any]:
        shown = dict(details)
        for key in self.money_keys:
            if shown.get(key) not in (None, ""):
                shown[key] = format_signed(Decimal(str(shown[key])))
        for key in self.date_keys:
            if shown.get(key):
                shown[key] = format_day(dt.date.fromisoformat(str(shown[key])[:10]))
        return shown

    def explain(self, details: Mapping[str, Any]) -> str:
        template = str(self.explanation)
        try:
            return template % self.display(details)
        except (KeyError, ValueError, TypeError):
            return str(self.description)

    def schema(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": str(self.name),
            "description": str(self.description),
            "default_severity": self.default_severity,
            "incremental": self.incremental,
            "has_fix": self.has_fix,
            "params": [p.as_dict(n) for n, p in self.params.items()],
        }


def clean_params(rule: Rule, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """``raw`` validated against the rule's schema, defaults filled in."""
    raw = dict(raw or {})
    unknown = sorted(set(raw) - set(rule.params))
    if unknown:
        message = _("%(rule)s has no parameter %(param)s.")
        raise _invalid(unknown[0], message % {"rule": rule.code, "param": unknown[0]})
    cleaned: dict[str, Any] = {}
    for name, param in rule.params.items():
        cleaned[name] = param.clean(name, raw[name]) if name in raw else param.default
    return cleaned


class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    def register(self, rule_class: type[Rule]) -> type[Rule]:
        code = rule_class.code
        if not code or code != code.upper():
            raise ValueError(f"A rule code is UPPER_CASE: {code!r}.")
        existing = self._rules.get(code)
        if existing is not None and type(existing) is not rule_class:
            raise ValueError(f"Rule {code} is registered already.")
        for name, param in rule_class.params.items():
            param.clean(name, param.default)  # a default must pass its own schema
        self._rules[code] = rule_class()
        return rule_class

    def unregister(self, code: str) -> None:
        self._rules.pop(code, None)

    def get(self, code: str) -> Rule:
        try:
            return self._rules[code]
        except KeyError:
            raise LookupError(f"No assurance rule {code}.") from None

    def __contains__(self, code: object) -> bool:
        return code in self._rules

    def __iter__(self) -> Iterator[Rule]:
        return iter(sorted(self._rules.values(), key=lambda r: r.code))

    def codes(self) -> list[str]:
        return sorted(self._rules)


registry = RuleRegistry()


def register(rule_class: type[Rule]) -> type[Rule]:
    return registry.register(rule_class)


# ---- settings and evaluation -------------------------------------------------------------


@dataclass(frozen=True)
class RuleSettings:
    enabled: bool
    severity: str
    params: dict[str, Any]


def settings_for(organisation: Any, rule: Rule) -> RuleSettings:
    """The organisation's settings of the rule (its ``ExceptionRuleConfig`` or the defaults).

    Stored parameters that no longer validate (a rule's schema changed) fall back to defaults."""
    from numo9.tenancy.context import org_context

    from ..models import ExceptionRuleConfig

    with org_context(organisation):
        config = ExceptionRuleConfig.objects.filter(rule_code=rule.code).first()
    if config is None:
        return RuleSettings(True, rule.default_severity, clean_params(rule, {}))
    try:
        params = clean_params(rule, config.params)
    except ValidationError:
        params = clean_params(rule, {})
    return RuleSettings(config.enabled, config.severity or rule.default_severity, params)


def context_for(
    organisation: Any,
    rule: Rule,
    *,
    scope: Scope | None = None,
    now: dt.datetime | None = None,
    params: Mapping[str, Any] | None = None,
) -> Context:
    found = settings_for(organisation, rule)
    values = clean_params(rule, params) if params is not None else found.params
    return Context(organisation, values, found.severity, scope, now or timezone.now())


def evaluate(
    organisation: Any,
    code: str,
    scope: Scope | None = None,
    *,
    now: dt.datetime | None = None,
    params: Mapping[str, Any] | None = None,
    rules: RuleRegistry | None = None,
) -> list[Hit]:
    """Run one rule over the organisation (inside its context): the hits."""
    from numo9.tenancy.context import org_context

    rule = (rules or registry).get(code)
    ctx = context_for(organisation, rule, scope=scope, now=now, params=params)
    with org_context(organisation):
        return list(rule.evaluate(ctx))
