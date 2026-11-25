"""Tax reports in the K-01 engine (G-05): every figure from the posted tax lines (G-05-T02), on
the organisation's basis or an explicit override (G-05-T03). Specs: ``docs/specs/tax-reports.md``.

Every report takes ``date_from`` / ``date_to`` or a filing ``period`` — its public id, or the
presets ``current`` and ``last_filed`` (G-05-T10) — which sets the range; ``basis`` (empty: the
organisation's, G-06; or ``accrual`` / ``cash``); ``kind`` (``all``, ``gst_hst``, ``qst``,
``pst``) and ``side`` (``all``, ``sales``, ``purchase``). Feature key ``tax.reports.read``.

- ``tax_summary`` (G-05-T04) — per side, component and tax code: basis, tax, recoverable,
  non-recoverable; totals per side and the net tax (collected − recoverable);
- ``tax_detail`` (G-05-T05) — per component, one row per document with its link;
- ``tax_audit`` (G-05-T06) — every tax line with its flags;
- ``itc_detail`` (G-05-T07) — purchases: recoverable and non-recoverable tax per line;
- ``tax_tie_out`` (G-05-T08) — each control account's GL movement against the tax lines.
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
#: "" — the organisation's basis (G-06); or an explicit override for this run.
BASES = ("", "accrual", "cash")
TAX_KINDS = ("all", "gst_hst", "qst", "pst")
SIDES = ("all", "sales", "purchase")
SIDE_LABELS = {"sales": _("Sales — tax collected"), "purchase": _("Purchases — ITCs and ITRs")}
KIND_LABELS = {"gst": _("GST"), "hst": _("HST"), "qst": _("QST"), "pst": _("PST")}
COMMON_PARAMS: tuple[ParamSpec, ...] = (
    ParamSpec("date_from", "date"),
    ParamSpec("date_to", "date"),
    ParamSpec("period", "text", ""),
    ParamSpec("basis", "choice", "", BASES),
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


#: Tax presets of ``period`` (G-05-T10): the filing period containing today, the latest filed.
PERIOD_PRESETS = ("current", "last_filed")


def preset_period(organisation: Any, preset: str) -> tuple[dt.date, dt.date]:
    """The range of a tax preset: GST/HST periods first (then QST); ``ReportError`` when the
    organisation has none."""
    from django.utils import timezone

    from numo9.orgsettings.locks import local_date

    from .models import FilingPeriod, PeriodStatus

    today = local_date(organisation, timezone.now())
    periods = FilingPeriod.objects.filter(registration__deleted_at__isnull=True).order_by(
        "registration__type", "-start"
    )
    if preset == "current":
        found = periods.filter(start__lte=today, end__gte=today).first()
    else:
        found = (
            periods.filter(status__in=(PeriodStatus.FILED, PeriodStatus.PAID))
            .order_by("-end", "registration__type")
            .first()
        )
    if found is None:
        raise ReportError(
            "There's no such filing period yet: choose dates.", code="tax.reports.no_period"
        )
    return found.start, found.end


class TaxReport(ReportDefinition):
    """What every tax report shares: the range, the basis, the filters."""

    category = "tax"
    feature = FEATURE
    params: ClassVar[tuple[ParamSpec, ...]] = COMMON_PARAMS

    def range(self, organisation: Any, params: dict[str, Any]) -> tuple[dt.date, dt.date]:
        if params.get("period") in PERIOD_PRESETS:
            return preset_period(organisation, str(params["period"]))
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
        from .settings import report_basis

        return report_basis(organisation, params["basis"] or None)[0]

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


def flags_of(line: Any) -> list[str]:
    """The audit flags of a tax line (``docs/specs/tax-reports.md`` §3)."""
    stored = line.line if isinstance(line, RecognisedLine) else line
    out = []
    if stored.overridden:
        out.append("override")
    if stored.late:
        out.append("late_adjustment")
    if stored.source == "journal" or stored.entry.type == "manual":
        out.append("journal_source")
    if stored.restricted:
        out.append("restricted_itc")
    if stored.reverses_id is not None or stored.entry.status == "reversed":
        out.append("superseded")
    return out


@register
class TaxAuditReport(TaxReport):
    """``tax_audit`` (G-05-T06) — every tax line: posting date, journal and line, account, code,
    component, rate, basis, tax, who posted it, and its flags (override, late adjustment,
    journal source, restricted ITC, superseded)."""

    id = "tax_audit"
    slug = "tax-audit"
    name = _("Tax audit report")
    description = _("Every tax line with its code, rate and who posted it, flags as chips.")
    keywords = (_("GST audit"), _("tax audit trail"))
    params = DETAIL_PARAMS

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [
            Column("rate", str(_("Rate %"))),
            Column("basis", str(_("Basis"))),
            Column("tax", str(_("Tax"))),
            Column("recoverable", str(_("Recoverable"))),
        ]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        from numo9.ledger.models import JournalLine

        data = self.load(organisation, params)
        lines = [
            r
            for r in data.lines
            if (not params["component"] or r.component == params["component"])
            and (not params["code"] or r.code == params["code"])
        ]
        entries = {r.line.entry_id: r.line.entry for r in lines}
        accounts = {
            (entry_id, line_no): str(account)
            for entry_id, line_no, account in (
                (j.entry_id, j.line_no, j.account)
                for j in JournalLine.objects.filter(entry_id__in=entries).select_related("account")
            )
        }
        from numo9.accounts.models import User

        people = {
            u.pk: u.name or u.email
            for u in User.objects.filter(
                pk__in={e.posted_by_id for e in entries.values() if e.posted_by_id}
            )
        }
        return lines, documents_of(organisation, list(entries.values())), accounts, people

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        lines, documents, accounts, people = data
        out = []
        for line in lines:
            stored = line.line
            entry = stored.entry
            doc = documents[entry.pk]
            out.append(
                ReportRow(
                    f"line:{stored.pk}",
                    " · ".join(
                        part
                        for part in (
                            stored.date.isoformat(),
                            doc["journal"],
                            str(stored.line_no),
                            accounts.get((entry.pk, stored.line_no), ""),
                            stored.code,
                            component_label(stored.kind, stored.component)
                            if stored.component
                            else "",
                        )
                        if part
                    ),
                    values=[stored.rate, line.basis, line.tax, line.recoverable],
                    drill={
                        "flags": flags_of(line),
                        "posted_by": people.get(entry.posted_by_id, ""),
                        "posted_at": entry.posted_at.isoformat() if entry.posted_at else "",
                        "journal": doc["journal"],
                        "number": doc["number"],
                        "url": doc["url"],
                        "code": stored.code,
                        "component": stored.component,
                        "side": stored.side,
                    },
                )
            )
        return out

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        return [
            ReportRow(
                "total",
                str(_("Total")),
                "total",
                [None, *(sum((r.values[i] or ZERO for r in rows), ZERO) for i in (1, 2, 3))],
            )
        ]


@register
class ItcDetailReport(TaxReport):
    """``itc_detail`` (G-05-T07) — purchases only: each line's tax with what comes back (ITC /
    ITR) and what doesn't (added to the cost), and the restriction that keeps part of it (the
    account's or the code's claimable %, e.g. *Meals and entertainment — 50 % claimable*).
    Totals per component; the recoverable total is the return's ITCs / ITRs."""

    id = "itc_detail"
    slug = "itc-detail"
    name = _("ITC and ITR detail")
    description = _(
        "Input tax credits and refunds by line, with restricted and non-recoverable tax."
    )
    keywords = (_("input tax credits"), _("ITC"), _("ITR"), "CTI", "RTI")
    params = DETAIL_PARAMS

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [
            Column("tax", str(_("Tax"))),
            Column("recoverable", str(_("Recoverable"))),
            Column("non_recoverable", str(_("Non-recoverable"))),
        ]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        from numo9.ledger.models import JournalLine

        params = {**params, "side": "purchase"}
        data = self.load(organisation, params, current_only=True)
        lines = [
            r
            for r in data.lines
            if (not params["component"] or r.component == params["component"])
            and (not params["code"] or r.code == params["code"])
        ]
        entries = {r.line.entry_id: r.line.entry for r in lines}
        accounts = {
            (j.entry_id, j.line_no): j.account
            for j in JournalLine.objects.filter(entry_id__in=entries).select_related("account")
        }
        return lines, documents_of(organisation, list(entries.values())), accounts

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        lines, documents, accounts = data
        grouped: dict[tuple[str, str], list[RecognisedLine]] = defaultdict(list)
        for line in lines:
            grouped[(line.kind, line.component)].append(line)
        out: list[ReportRow] = []
        for (kind, component), mine in sorted(grouped.items()):
            out.append(
                ReportRow(f"component:{component}", component_label(kind, component), "section")
            )
            for line in mine:
                stored = line.line
                account = accounts.get((stored.entry_id, stored.line_no))
                doc = documents[stored.entry_id]
                restriction = ""
                if stored.restricted and line.tax:
                    share = (line.recoverable / line.tax * 100).quantize(Decimal("1"))
                    restriction = str(_("%(share)s %% claimable")) % {"share": share}
                elif line.tax and not line.recoverable:
                    restriction = str(_("Not recoverable"))
                out.append(
                    ReportRow(
                        f"line:{stored.pk}",
                        " · ".join(
                            part
                            for part in (
                                stored.date.isoformat(),
                                doc["number"],
                                doc["contact"],
                                str(account) if account else "",
                            )
                            if part
                        ),
                        values=[line.tax, line.recoverable, line.non_recoverable],
                        level=1,
                        drill={
                            "url": doc["url"],
                            "restriction": restriction,
                            "restricted": stored.restricted,
                            "code": stored.code,
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
                [sum((r.values[i] or ZERO for r in mine), ZERO) for i in range(3)],
            )
        ]


#: The control accounts tied out (G-05-T08): role → (tax kinds, side, the tax line amount, sign of
#: the GL movement — payables are credits, receivables debits).
CONTROLS: tuple[tuple[str, tuple[str, ...], str, str, int], ...] = (
    ("gst_hst_payable", ("gst", "hst"), "sales", "tax", -1),
    ("itc_receivable", ("gst", "hst"), "purchase", "recoverable", 1),
    ("qst_payable", ("qst",), "sales", "tax", -1),
    ("qst_itr", ("qst",), "purchase", "recoverable", 1),
    ("pst_payable", ("pst",), "sales", "tax", -1),
)


@register
class TaxTieOutReport(TaxReport):
    """``tax_tie_out`` (G-05-T08) — per tax control account: its GL movement in the range, the
    tax lines' total for it and the difference; every journal that posted to a control account
    without tax lines is listed (*Journals affecting tax accounts*) — the usual cause of a
    difference. A difference other than 0.00 is an ``error`` alert (the red card). Always on the
    accrual basis: the ledger is."""

    id = "tax_tie_out"
    slug = "tax-tie-out"
    name = _("Tax-to-GL tie-out")
    description = _("Each tax control account's movement against the tax reports, and why not.")
    keywords = (_("tax reconciliation"), _("GST reconciliation"))

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [
            Column("gl", str(_("GL movement"))),
            Column("report", str(_("Tax report"))),
            Column("difference", str(_("Difference"))),
        ]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        from numo9.ledger.models import LOCKED_STATUSES, Account, JournalLine
        from numo9.ledger.sequence import format_journal_number

        from .models import TaxLine

        start, end = self.range(organisation, params)
        accounts = {
            a.system_role: a
            for a in Account.objects.filter(system_role__in=[c[0] for c in CONTROLS])
        }
        lines = TaxLine.objects.filter(organisation=organisation, date__gte=start, date__lte=end)
        out = []
        for role, kinds, side, amount, sign in CONTROLS:
            account = accounts.get(role)
            if account is None:
                continue
            moved = JournalLine.objects.filter(
                account=account,
                entry__status__in=LOCKED_STATUSES,
                entry__date__gte=start,
                entry__date__lte=end,
                book__in=("both", "accounting"),
            ).aggregate(d=Coalesce(Sum("debit"), ZERO), c=Coalesce(Sum("credit"), ZERO))
            gl = (moved["d"] - moved["c"]) * sign
            report = lines.filter(kind__in=kinds, side=side).aggregate(
                v=Coalesce(Sum(amount), ZERO)
            )["v"]
            journals = []
            hitting = (
                JournalLine.objects.filter(
                    account=account,
                    entry__status__in=LOCKED_STATUSES,
                    entry__date__gte=start,
                    entry__date__lte=end,
                )
                .exclude(entry__in=TaxLine.objects.values("entry"))
                .select_related("entry")
                .order_by("entry__date", "entry_id", "line_no")
            )
            for line in hitting:
                entry = line.entry
                journals.append(
                    {
                        "journal": format_journal_number(organisation, entry.number),
                        "entry": str(entry.public_id),
                        "date": entry.date.isoformat(),
                        "narration": entry.narration,
                        "amount": f"{(line.debit - line.credit) * sign:.2f}",
                        "url": f"/o/{organisation.public_id}/accounting/journals/{entry.public_id}",
                    }
                )
            out.append((role, account, gl, report, journals))
        return start, end, out

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        start, end, controls = data
        return [
            ReportRow(
                f"control:{role}",
                str(account),
                values=[gl, report, gl - report],
                drill={
                    "account": account.code,
                    "from": start,
                    "to": end,
                    "ties": gl == report,
                    "journals": journals,
                },
            )
            for role, account, gl, report, journals in controls
        ]

    def totals(self, rows: Sequence[ReportRow], params: dict[str, Any]) -> list[ReportRow]:
        difference = sum((r.values[2] or ZERO for r in rows), ZERO)
        return [ReportRow("total", str(_("Total difference")), "total", [None, None, difference])]

    def alerts(self, organisation: Any, result: Any) -> list[dict[str, Any]]:
        off = [r for r in result.rows if r.values[2]]
        if not off:
            return [{"code": "tax.tie_out.ties", "level": "info", "message": str(_("Ties to GL"))}]
        return [
            {
                "code": "tax.tie_out.difference",
                "level": "error",
                "message": str(
                    _("The tax reports don't tie to the ledger: %(accounts)s.")
                    % {"accounts": "; ".join(f"{r.label} {r.values[2]:.2f}" for r in off)}
                ),
                "detail": {r.key: f"{r.values[2]:.2f}" for r in off},
            }
        ]
