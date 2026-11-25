"""Tax reports in the K-01 engine (G-05): every figure from the posted tax lines (G-05-T02), on
the organisation's basis or an explicit override (G-05-T03). Specs: ``docs/specs/tax-reports.md``.

Every report takes ``date_from`` / ``date_to`` or a filing ``period`` (its public id, which sets
the range), ``basis`` (``settings`` — the organisation's, G-06 — ``accrual`` or ``cash``),
``kind`` (``all``, ``gst_hst``, ``qst``, ``pst``) and ``side`` (``all``, ``sales``,
``purchase``). Feature key ``tax.reports.read``.

- ``tax_summary`` (G-05-T04) — per side, component and tax code: basis, tax, recoverable,
  non-recoverable; totals per side and the net tax (collected − recoverable).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext_lazy as _

from numo9.reports.engine import (
    Column,
    ParamSpec,
    ReportDefinition,
    ReportError,
    ReportRow,
    register,
)

from .cash_basis import RecognisedLine, recognised_lines

ZERO = Decimal("0.00")
FEATURE = "tax.reports.read"
BASES = ("settings", "accrual", "cash")
TAX_KINDS = ("all", "gst_hst", "qst", "pst")
SIDES = ("all", "sales", "purchase")
SIDE_LABELS = {"sales": _("Sales — tax collected"), "purchase": _("Purchases — ITCs and ITRs")}
KIND_LABELS = {"gst": _("GST"), "hst": _("HST"), "qst": _("QST"), "pst": _("PST")}
COMMON_PARAMS = (
    ParamSpec("date_from", "date"),
    ParamSpec("date_to", "date"),
    ParamSpec("period", "text", ""),
    ParamSpec("basis", "choice", "settings", BASES),
    ParamSpec("kind", "choice", "all", TAX_KINDS),
    ParamSpec("side", "choice", "all", SIDES),
)


def amount_columns() -> list[Column]:
    return [
        Column("basis", str(_("Basis"))),
        Column("tax", str(_("Tax"))),
        Column("recoverable", str(_("Recoverable"))),
        Column("non_recoverable", str(_("Non-recoverable"))),
    ]


def component_label(kind: str, component: str) -> str:
    label = str(KIND_LABELS.get(kind, kind.upper() or component))
    return f"{label} ({component})" if component and component != kind else label


class TaxReport(ReportDefinition):
    """What every tax report shares: the range, the basis, the filters."""

    category = "tax"
    feature = FEATURE
    params = COMMON_PARAMS

    def range(self, organisation: Any, params: dict[str, Any]) -> tuple[dt.date, dt.date]:
        if params.get("period"):
            from .models import FilingPeriod

            try:
                key = uuid.UUID(str(params["period"]))
            except ValueError:
                raise ReportError("Choose a filing period.", code="tax.reports.period") from None
            period = FilingPeriod.objects.filter(public_id=key).first()
            if period is None:
                raise ReportError("Choose a filing period.", code="tax.reports.period")
            return period.start, period.end
        start, end = params.get("date_from"), params.get("date_to")
        if start is None or end is None or start > end:
            raise ReportError(
                "Choose a filing period, or a start and an end date.", code="tax.reports.range"
            )
        return start, end

    def basis(self, organisation: Any, params: dict[str, Any]) -> str:
        if params["basis"] != "settings":
            return str(params["basis"])
        from .settings import tax_settings

        return "cash" if tax_settings(organisation).basis == "cash" else "accrual"

    def load(
        self, organisation: Any, params: dict[str, Any], *, current_only: bool = False
    ) -> TaxData:
        start, end = self.range(organisation, params)
        basis = self.basis(organisation, params)
        lines = recognised_lines(
            organisation,
            start,
            end,
            basis=basis,
            kind=params["kind"],
            side=params["side"],
            current_only=current_only,
        )
        return TaxData(start, end, basis, lines)

    def drill(self, data: TaxData, **extra: Any) -> dict[str, Any]:
        return {
            "report": "tax_detail",
            "from": data.start,
            "to": data.end,
            "basis": data.basis,
            **extra,
        }


@dataclass(frozen=True)
class TaxData:
    start: dt.date
    end: dt.date
    basis: str
    lines: list[RecognisedLine]


def _values(rows: Sequence[RecognisedLine]) -> list[Decimal | None]:
    return [
        sum((r.basis for r in rows), ZERO),
        sum((r.tax for r in rows), ZERO),
        sum((r.recoverable for r in rows), ZERO),
        sum((r.non_recoverable for r in rows), ZERO),
    ]


@register
class TaxSummaryReport(TaxReport):
    id = "tax_summary"
    slug = "tax-summary"
    name = _("Tax summary")
    description = _("Tax collected and claimed by component and tax code, tied to the ledger.")
    keywords = (_("GST summary"), _("HST report"), _("sales tax"), "taxes")

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return amount_columns()

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        return self.load(organisation, params)

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        grouped: dict[str, dict[tuple[str, str], dict[str, list[RecognisedLine]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for line in data.lines:
            grouped[line.side][(line.kind, line.component)][line.code].append(line)
        out: list[ReportRow] = []
        for side in ("sales", "purchase"):
            if side not in grouped:
                continue
            out.append(ReportRow(f"side:{side}", str(SIDE_LABELS[side]), "section"))
            for (kind, component), codes in sorted(grouped[side].items()):
                out.append(
                    ReportRow(
                        f"component:{side}:{component}",
                        component_label(kind, component),
                        "section",
                        level=1,
                    )
                )
                for code, lines in sorted(codes.items()):
                    out.append(
                        ReportRow(
                            f"code:{side}:{component}:{code}",
                            code or str(_("No tax code")),
                            values=_values(lines),
                            level=2,
                            drill=self.drill(data, side=side, component=component, code=code),
                        )
                    )
        return out

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        def side_total(side: str) -> list[Decimal | None]:
            mine = [r for r in rows if r.key.startswith(f"code:{side}:")]
            return [sum((r.values[i] or ZERO for r in mine), ZERO) for i in range(4)]

        sales, purchases = side_total("sales"), side_total("purchase")
        net = (sales[1] or ZERO) - (purchases[2] or ZERO)
        return [
            ReportRow("total:sales", str(_("Total tax collected")), "total", sales),
            ReportRow("total:purchase", str(_("Total ITCs and ITRs")), "total", purchases),
            ReportRow(
                "total:net",
                str(_("Net tax (collected − recoverable)")),
                "total",
                [None, net, None, None],
            ),
        ]
