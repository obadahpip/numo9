"""Tax reports in the K-01 engine (G-05): every figure from the posted tax lines (G-05-T02), on
the organisation's basis or an explicit override (G-05-T03). Specs: ``docs/specs/tax-reports.md``.

Every report takes ``date_from`` / ``date_to`` or a filing ``period`` (its public id, which sets
the range), ``basis`` (``settings`` — the organisation's, G-06 — ``accrual`` or ``cash``),
``kind`` (``all``, ``gst_hst``, ``qst``, ``pst``) and ``side`` (``all``, ``sales``,
``purchase``). Feature key ``tax.reports.read``.

- ``tax_detail`` (G-05-T05) — per component, one row per document with its link;
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
from typing import Any, ClassVar

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
COMMON_PARAMS: tuple[ParamSpec, ...] = (
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
    params: ClassVar[tuple[ParamSpec, ...]] = COMMON_PARAMS

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


#: Source document of a journal: (app label, model, number field) — the detail's labels.
DOCUMENTS = {
    "sales.invoice": ("sales", "Invoice", "number"),
    "sales.credit_note": ("sales", "CreditNote", "number"),
    "purchases.bill": ("purchases", "Bill", "number"),
    "purchases.supplier_credit": ("purchases", "SupplierCredit", "number"),
}
DETAIL_PARAMS: tuple[ParamSpec, ...] = (
    *COMMON_PARAMS,
    ParamSpec("component", "text", ""),
    ParamSpec("code", "text", ""),
)


def documents_of(organisation: Any, entries: Sequence[Any]) -> dict[int, dict[str, str]]:
    """Each entry's document: its label (number), contact and link (K-01 drill links)."""
    from django.apps import apps

    from numo9.ledger.sequence import format_journal_number
    from numo9.reports.drill import source_link

    wanted: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        if entry.source_type in DOCUMENTS and entry.source_id:
            wanted[entry.source_type].add(entry.source_id)
    found: dict[tuple[str, str], tuple[str, str]] = {}
    for source_type, ids in wanted.items():
        app, model_name, field = DOCUMENTS[source_type]
        model = apps.get_model(app, model_name)
        for public_id, number, contact in model._base_manager.filter(
            organisation=organisation, public_id__in=ids
        ).values_list("public_id", field, "contact__display_name"):
            found[(source_type, str(public_id))] = (str(number or ""), str(contact or ""))
    out = {}
    for entry in entries:
        number, contact = found.get((entry.source_type, entry.source_id), ("", ""))
        journal = format_journal_number(organisation, entry.number)
        out[entry.pk] = {
            "number": number or journal,
            "journal": journal,
            "contact": contact,
            **source_link(organisation, entry),
        }
    return out


@register
class TaxDetailReport(TaxReport):
    """``tax_detail`` (G-05-T05) — one row per document and component, in date order, grouped by
    component; each row drills to its document. ``component`` / ``code`` narrow it (the
    summary's drill-down)."""

    id = "tax_detail"
    slug = "tax-detail"
    name = _("Tax detail by document")
    description = _("Every document's tax, by component, with a link to the document.")
    keywords = (_("GST detail"), _("tax by invoice"))
    params: ClassVar[tuple[ParamSpec, ...]] = DETAIL_PARAMS

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return amount_columns()

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        data = self.load(organisation, params, current_only=True)
        lines = [
            r
            for r in data.lines
            if (not params["component"] or r.component == params["component"])
            and (not params["code"] or r.code == params["code"])
        ]
        entries = list({r.line.entry_id: r.line.entry for r in lines}.values())
        return TaxData(data.start, data.end, data.basis, lines), documents_of(organisation, entries)

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        tax, documents = data
        grouped: dict[tuple[str, str], dict[int, list[RecognisedLine]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for line in tax.lines:
            grouped[(line.kind, line.component)][line.line.entry_id].append(line)
        out: list[ReportRow] = []
        for (kind, component), by_entry in sorted(grouped.items()):
            out.append(
                ReportRow(f"component:{component}", component_label(kind, component), "section")
            )
            for entry_id, lines in sorted(
                by_entry.items(), key=lambda item: (item[1][0].line.date, item[0])
            ):
                doc = documents[entry_id]
                first = lines[0].line
                label = " · ".join(
                    part for part in (first.date.isoformat(), doc["number"], doc["contact"]) if part
                )
                out.append(
                    ReportRow(
                        f"document:{component}:{entry_id}",
                        label,
                        values=_values(lines),
                        level=1,
                        drill={
                            "url": doc["url"],
                            "journal_url": doc["journal_url"],
                            "type": doc["type"],
                            "number": doc["number"],
                            "journal": doc["journal"],
                            "codes": ", ".join(sorted({line.code for line in lines})),
                            "side": first.side,
                        },
                    )
                )
        return out

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        mine = [r for r in rows if r.kind == "row"]
        return [
            ReportRow(
                "total",
                str(_("Total")),
                "total",
                [sum((r.values[i] or ZERO for r in mine), ZERO) for i in range(4)],
            )
        ]
