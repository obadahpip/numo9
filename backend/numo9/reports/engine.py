"""Report definition framework (K-01-T02): one engine for every report.

A report is a ``ReportDefinition`` subclass registered in the catalogue (``registry``):

    @register
    class TrialBalanceReport(ReportDefinition):
        id = "trial_balance"            # stable: layouts, notes and favourites point at it
        slug = "trial-balance"          # the URL (/o/<org>/reports/trial-balance)
        name = _("Trial balance")
        category = "financial"
        feature = "accounting.reports.read"
        params = (ParamSpec("as_of", "date"), ParamSpec("book", "choice", "accounting", BOOKS))

        def query(self, organisation, params): ...   # data from the ledger
        def rows(self, data, params): ...            # ReportRow list (sections, rows, text)
        def totals(self, rows, params): ...          # ReportRow list of totals

- **params schema** — ``ParamSpec(name, kind, default, choices)``; ``clean_params(raw)`` checks
  and converts what a request sends (unknown names refused, choices checked, dates parsed) and
  fills the defaults; kinds: ``date``, ``choice``, ``bool``, ``int``, ``text``;
- ``columns(params)`` — the value columns (key and label); one by default;
- ``run(organisation, raw_params)`` → ``ReportResult(definition, params, columns, rows, totals)``:
  ``query`` → ``rows`` → ``totals``, every value a ``Decimal`` or ``None`` per column.

The registry refuses two reports with the same id or slug, finds one by id or slug, and lists
them by category (the report home, K-01-T12). Every registered report is also an entry of the
global search and the command palette (A-09, K-01-T18): its name and ``keywords`` find it, and it
opens the runner (``/o/<org>/reports/<slug>``), gated by its feature key like the API.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, ClassVar

from django.utils.functional import Promise

PARAM_KINDS = ("date", "choice", "bool", "int", "text")
ROW_KINDS = ("section", "row", "total", "text")


class ReportError(ValueError):
    """A report or its parameters can't be used (``code`` names the problem)."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: str
    default: Any = None
    choices: tuple[str, ...] = ()
    required: bool = False

    def __post_init__(self) -> None:
        if self.kind not in PARAM_KINDS:
            raise ReportError(f"Unknown parameter kind {self.kind!r}.", code="reports.param.kind")

    def clean(self, value: Any) -> Any:
        if value is None or value == "":
            if self.required:
                raise ReportError(f"{self.name} is required.", code="reports.param.required")
            return self.default
        try:
            if self.kind == "date":
                return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))
            if self.kind == "bool":
                return value if isinstance(value, bool) else str(value).lower() in ("1", "true")
            if self.kind == "int":
                return int(value)
        except (TypeError, ValueError):
            raise ReportError(
                f"{self.name}: {value!r} isn't a valid {self.kind}.", code="reports.param.invalid"
            ) from None
        value = str(value)
        if self.kind == "choice" and value not in self.choices:
            raise ReportError(
                f"{self.name} must be one of {', '.join(self.choices)}.",
                code="reports.param.choice",
            )
        return value

    def as_dict(self) -> dict[str, Any]:
        default = self.default.isoformat() if isinstance(self.default, dt.date) else self.default
        return {
            "name": self.name,
            "kind": self.kind,
            "default": default,
            "choices": list(self.choices),
            "required": self.required,
        }


@dataclass(frozen=True)
class Column:
    key: str
    label: str


@dataclass
class ReportRow:
    key: str
    label: str
    kind: str = "row"
    values: list[Decimal | None] = field(default_factory=list)
    level: int = 0
    #: What the drill-down (K-01-T05) needs to list the figure's lines, per column.
    drill: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.kind not in ROW_KINDS:
            raise ReportError(f"Unknown row kind {self.kind!r}.", code="reports.row.kind")

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "level": self.level,
            "values": [None if v is None else f"{v:.2f}" for v in self.values],
            "drill": None
            if self.drill is None
            else {k: v.isoformat() if isinstance(v, dt.date) else v for k, v in self.drill.items()},
        }


@dataclass(frozen=True)
class ReportResult:
    definition: ReportDefinition
    params: dict[str, Any]
    columns: list[Column]
    rows: list[ReportRow]
    totals: list[ReportRow]

    def as_dict(self) -> dict[str, Any]:
        return {
            "report": self.definition.id,
            "params": {
                k: v.isoformat() if isinstance(v, dt.date) else v for k, v in self.params.items()
            },
            "columns": [{"key": c.key, "label": c.label} for c in self.columns],
            "rows": [r.as_dict() for r in self.rows],
            "totals": [r.as_dict() for r in self.totals],
        }


class ReportDefinition:
    id: ClassVar[str] = ""
    slug: ClassVar[str] = ""
    name: ClassVar[str | Promise] = ""
    description: ClassVar[str | Promise] = ""
    category: ClassVar[str] = "financial"
    #: The feature key a package needs (U-01) and the permission a person needs (A-03).
    feature: ClassVar[str] = "accounting.reports.read"
    permission: ClassVar[str] = "reports.reports.view"
    params: ClassVar[tuple[ParamSpec, ...]] = ()
    #: Other words people search the report by (K-01-T18): "TB", "income statement"…
    keywords: ClassVar[tuple[str | Promise, ...]] = ()

    def clean_params(self, raw: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = dict(raw or {})
        known = {spec.name for spec in self.params}
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ReportError(
                f"Unknown parameter(s): {', '.join(unknown)}.", code="reports.param.unknown"
            )
        return {spec.name: spec.clean(raw.get(spec.name)) for spec in self.params}

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [Column("amount", str(self.name))]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        raise NotImplementedError

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        raise NotImplementedError

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        return []

    def run(self, organisation: Any, raw: Mapping[str, Any] | None = None) -> ReportResult:
        from numo9.tenancy.context import org_context

        params = self.clean_params(raw)
        with org_context(organisation):
            data = self.query(organisation, params)
            rows = self.rows(data, params)
            totals = self.totals(rows, params)
        return ReportResult(self, params, self.columns(params), rows, totals)

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": str(self.name),
            "description": str(self.description),
            "category": self.category,
            "feature": self.feature,
            "params": [spec.as_dict() for spec in self.params],
        }


class ReportRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, ReportDefinition] = {}
        self._by_slug: dict[str, ReportDefinition] = {}

    def register(self, definition: type[ReportDefinition]) -> type[ReportDefinition]:
        report = definition()
        if not report.id or not report.slug:
            raise ReportError("A report needs an id and a slug.", code="reports.registry.id")
        if report.id in self._by_id:
            raise ReportError(f"Report id {report.id!r} is taken.", code="reports.registry.id")
        if report.slug in self._by_slug:
            raise ReportError(
                f"Report slug {report.slug!r} is taken.", code="reports.registry.slug"
            )
        self._by_id[report.id] = report
        self._by_slug[report.slug] = report
        _register_search(report)
        return definition

    def unregister(self, report_id: str) -> None:
        """Tests only."""
        report = self._by_id.pop(report_id, None)
        if report is not None:
            self._by_slug.pop(report.slug, None)
            from numo9.search.static import unregister_static

            unregister_static(f"reports.{report.id}")

    def get(self, key: str) -> ReportDefinition:
        found = self._by_id.get(key) or self._by_slug.get(key)
        if found is None:
            raise ReportError(f"There's no report {key!r}.", code="reports.unknown")
        return found

    def by_category(self) -> dict[str, list[ReportDefinition]]:
        grouped: dict[str, list[ReportDefinition]] = {}
        for report in sorted(self._by_id.values(), key=lambda r: str(r.name)):
            grouped.setdefault(report.category, []).append(report)
        return grouped

    def __iter__(self) -> Iterator[ReportDefinition]:
        return iter(sorted(self._by_id.values(), key=lambda r: r.id))

    def __contains__(self, key: object) -> bool:
        return key in self._by_id or key in self._by_slug


def _register_search(report: ReportDefinition) -> None:
    """The report as a global-search entry (A-09 static entries, group ``reports``)."""
    from numo9.search.static import REPORTS, StaticEntry, register_static

    register_static(
        StaticEntry(
            f"reports.{report.id}",
            REPORTS,
            report.name,
            f"reports/{report.slug}",
            tuple(report.keywords),
            permission_key=report.permission,
            feature_key=report.feature,
        )
    )


registry = ReportRegistry()
register = registry.register
