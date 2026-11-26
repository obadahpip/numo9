"""GST/HST return workflow (G-03): prepare → review → file, the filing lock, amendments.

- ``prepare(period, user)`` (G-03-T06) — the period's return in progress, created as a draft
  when there is none (version 1, or refused with ``tax.return.already_filed`` once a return is
  filed: amend it instead). The preparer is the person who created it.
- ``review(tax_return, user)`` — draft → reviewed. **The reviewer is not the preparer**
  (segregation of duties, A-03-T08: ``approval.self_approval``, 403). ``send_back`` returns a
  reviewed return to draft with a reason.
- ``file(tax_return, user, confirmation_no=, filed_on=)`` — reviewed → filed with the CRA /
  Revenu Québec confirmation number (required). Filing (G-03-T07) also

  * sets the period's status to **filed** in the filing-cycle engine (G-03a: it never changes
    again), and
  * moves the **Tax lock** (A-05, everyone) to the period's end when it is earlier, so a
    document with tax dated in the period is refused naming the lock (``tax_lock_guard``).

- ``amend(tax_return, user, reason)`` (G-03-T09) — from a filed return, version n + 1 as a draft
  with the reason; the filed one becomes ``amended`` when the new version is filed and stays
  viewable. ``versions(period)`` lists them, the latest marked current.

Every step writes an audit event on the return (``tax.return.prepared`` / ``reviewed`` /
``sent_back`` / ``filed`` / ``amended``) with the person.

Late adjustments (G-03-T08) are described where they are implemented, below.

``tax_lock_guard`` is registered as a ledger posting guard (``ledger.services.POSTING_GUARDS``):
a journal that posts to a sales-tax control account, or carries a tax code, is checked against
the Tax lock as well as its own module's.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    OPEN_RETURN_STATUSES,
    FilingPeriod,
    PeriodStatus,
    ReturnStatus,
    TaxError,
    TaxReturn,
)


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _record(action: str, tax_return: TaxReturn, user: Any, **meta: Any) -> None:
    from numo9.audit.service import record

    record(action, obj=tax_return, actor=_person(user), meta=meta)


def _acting(user: Any) -> Any:
    from numo9.ledger.renumber import acting_as

    return acting_as(user)


def _org(obj: Any) -> Any:
    from numo9.tenancy.context import org_context

    return org_context(obj.organisation)


def current_return(period: FilingPeriod) -> TaxReturn | None:
    """The period's latest version (what a list shows)."""
    found: TaxReturn | None = (
        TaxReturn.objects.filter(period=period, deleted_at__isnull=True)
        .order_by("-version")
        .first()
    )
    return found


def current_return_of(period: FilingPeriod) -> TaxReturn:
    """``current_return`` inside the period's organisation; refuses a period without a return."""
    with _org(period):
        found = current_return(period)
    if found is None:
        raise TaxError(_("No return is prepared for this period."), code="tax.return.none")
    return found


def versions(period: FilingPeriod) -> list[dict[str, Any]]:
    """Every version of the period's return, newest first; the latest is ``current``."""
    with _org(period):
        rows = list(
            TaxReturn.objects.filter(period=period, deleted_at__isnull=True).order_by("-version")
        )
        return [
            {
                "id": str(row.public_id),
                "version": row.version,
                "status": row.status,
                "current": index == 0,
                "filed_on": row.filed_on.isoformat() if row.filed_on else None,
                "confirmation_no": row.confirmation_no,
                "amend_reason": row.amend_reason,
            }
            for index, row in enumerate(rows)
        ]


def prepare(period: FilingPeriod, user: Any = None, *, method: str = "regular") -> TaxReturn:
    """The return in progress of ``period`` (created as a draft when none)."""
    with _org(period), transaction.atomic(), _acting(user):
        returns = TaxReturn.objects.select_for_update().filter(
            period=period, deleted_at__isnull=True
        )
        open_one: TaxReturn | None = returns.filter(status__in=OPEN_RETURN_STATUSES).first()
        if open_one is not None:
            return open_one
        if returns.filter(status=ReturnStatus.FILED).exists():
            raise TaxError(
                _("The return for %(period)s is filed. Amend it to change it.")
                % {"period": str(period)},
                code="tax.return.already_filed",
            )
        tax_return = TaxReturn(
            organisation=period.organisation,
            registration=period.registration,
            period=period,
            version=(returns.order_by("-version").values_list("version", flat=True).first() or 0)
            + 1,
            method=method,
            prepared_by=_person(user),
            prepared_at=timezone.now(),
            created_by=_person(user),
        )
        tax_return.lines = computed_lines(tax_return)
        tax_return.save()
        _record("tax.return.prepared", tax_return, user, version=tax_return.version)
        return tax_return


def computed_lines(tax_return: TaxReturn, entries: dict[str, Any] | None = None) -> dict[str, Any]:
    """The return's lines from the books (G-03-T03 regular, T04 quick) and its entries — the
    amounts entered by hand (104, 107, 110, 111, 113B; kept under ``entries``)."""
    from .return_lines import ENTRY_LINES, as_text, regular_lines

    kept = (tax_return.lines or {}).get("entries") or {}
    given = {k: v for k, v in {**kept, **(entries or {})}.items() if k in ENTRY_LINES}
    if tax_return.method == "quick":
        raise TaxError(
            _("The quick method isn't available yet."), code="tax.return.quick_unavailable"
        )
    values = regular_lines(tax_return.period, entries=given)
    return {
        **as_text(values),
        "entries": {k: f"{Decimal(str(v or 0)):.2f}" for k, v in given.items()},
    }


def recalculate(
    tax_return: TaxReturn, user: Any = None, *, entries: dict[str, Any] | None = None
) -> TaxReturn:
    """Recalculate a draft return from the books (G-03-T03); a reviewed or filed one is
    refused — send it back, or amend it."""
    with _org(tax_return), transaction.atomic(), _acting(user):
        locked: TaxReturn = TaxReturn.objects.select_for_update().get(pk=tax_return.pk)
        _expect(locked, ReturnStatus.DRAFT, _("Only a draft return is recalculated."))
        locked.lines = computed_lines(locked, entries)
        locked.save()
        _record("tax.return.recalculated", locked, user, version=locked.version)
        return locked


def _expect(tax_return: TaxReturn, status: str, message: str) -> None:
    if tax_return.status != status:
        raise TaxError(message, code="tax.return.status")


def review(tax_return: TaxReturn, user: Any) -> TaxReturn:
    """Draft → reviewed, by someone other than the preparer."""
    from numo9.rbac.duties import assert_not_creator

    with _org(tax_return), transaction.atomic(), _acting(user):
        _expect(tax_return, ReturnStatus.DRAFT, _("Only a draft return can be reviewed."))
        assert_not_creator(user, tax_return, fields=("prepared_by",), record=_("return"))
        tax_return.status = ReturnStatus.REVIEWED
        tax_return.reviewed_by = _person(user)
        tax_return.reviewed_at = timezone.now()
        tax_return.save()
        _record("tax.return.reviewed", tax_return, user)
        return tax_return


def send_back(tax_return: TaxReturn, user: Any, reason: str) -> TaxReturn:
    """Reviewed → draft, with the reason."""
    with _org(tax_return), transaction.atomic(), _acting(user):
        _expect(tax_return, ReturnStatus.REVIEWED, _("Only a reviewed return can be sent back."))
        text = " ".join((reason or "").split())
        if not text:
            raise TaxError(_("Say why the return goes back."), code="tax.return.reason_required")
        tax_return.status = ReturnStatus.DRAFT
        tax_return.reviewed_by = None
        tax_return.reviewed_at = None
        tax_return.save()
        _record("tax.return.sent_back", tax_return, user, reason=text)
        return tax_return


def _lock_tax(tax_return: TaxReturn, user: Any) -> None:
    """Move the Tax lock (everyone) to the period's end when it is earlier (G-03-T07)."""
    from numo9.orgsettings.models import LockDate, LockLevel, LockModule

    period = tax_return.period
    lock = LockDate.objects.filter(
        module=LockModule.TAX, level=LockLevel.EVERYONE, deleted_at__isnull=True
    ).first() or LockDate(
        organisation=tax_return.organisation, module=LockModule.TAX, level=LockLevel.EVERYONE
    )
    if lock.date is not None and lock.date >= period.end:
        return
    lock.set_lock(
        period.end,
        _("Return for %(period)s filed (confirmation %(number)s).")
        % {"period": str(period), "number": tax_return.confirmation_no},
    )
    lock.save()


def file(
    tax_return: TaxReturn,
    user: Any,
    *,
    confirmation_no: str,
    filed_on: dt.date | None = None,
) -> TaxReturn:
    """Reviewed → filed with its confirmation number; locks the period (module docstring)."""
    with _org(tax_return), transaction.atomic(), _acting(user):
        _expect(tax_return, ReturnStatus.REVIEWED, _("Review the return before filing it."))
        number = " ".join((confirmation_no or "").split())
        if not number:
            raise TaxError(
                _("Enter the confirmation number the CRA or Revenu Québec gave when you filed."),
                code="tax.return.confirmation_required",
            )
        now = timezone.now()
        if tax_return.amends_id is not None:  # the return it replaces stays, marked amended
            TaxReturn.objects.filter(pk=tax_return.amends_id, status=ReturnStatus.FILED).update(
                status=ReturnStatus.AMENDED
            )
        tax_return.status = ReturnStatus.FILED
        tax_return.confirmation_no = number
        tax_return.filed_on = filed_on or timezone.localdate()
        tax_return.filed_by = _person(user)
        tax_return.filed_at = now
        tax_return.save()
        period = FilingPeriod.objects.select_for_update().get(pk=tax_return.period_id)
        if period.status != PeriodStatus.PAID:
            period.status = PeriodStatus.FILED
        period.filed_at = period.filed_at or now
        period.attention = ""
        period.save(update_fields=["status", "filed_at", "attention"])
        tax_return.period = period
        _lock_tax(tax_return, user)
        _record(
            "tax.return.filed",
            tax_return,
            user,
            confirmation_no=number,
            filed_on=tax_return.filed_on.isoformat(),
            version=tax_return.version,
        )
        return tax_return


def amend(tax_return: TaxReturn, user: Any, reason: str) -> TaxReturn:
    """Version n + 1 (a draft) of a filed return, with the reason (G-03-T09)."""
    with _org(tax_return), transaction.atomic(), _acting(user):
        _expect(tax_return, ReturnStatus.FILED, _("Only a filed return can be amended."))
        text = " ".join((reason or "").split())
        if not text:
            raise TaxError(_("Say why the return is amended."), code="tax.return.reason_required")
        returns = TaxReturn.objects.select_for_update().filter(
            period_id=tax_return.period_id, deleted_at__isnull=True
        )
        if returns.filter(status__in=OPEN_RETURN_STATUSES).exists():
            raise TaxError(
                _("An amendment of this return is already in progress."),
                code="tax.return.amendment_open",
            )
        latest = returns.order_by("-version").values_list("version", flat=True).first() or 0
        amendment = TaxReturn(
            organisation=tax_return.organisation,
            registration=tax_return.registration,
            period=tax_return.period,
            version=latest + 1,
            method=tax_return.method,
            lines=dict(tax_return.lines or {}),
            prepared_by=_person(user),
            prepared_at=timezone.now(),
            created_by=_person(user),
            amends=tax_return,
            amend_reason=text,
        )
        amendment.save()
        _record(
            "tax.return.amended", amendment, user, reason=text, amends_version=tax_return.version
        )
        return amendment


# ---- the Tax lock on postings (G-03-T07) ------------------------------------------------------

TAX_ROLES = ("gst_hst_payable", "itc_receivable", "qst_payable", "qst_itr", "pst_payable")


def touches_tax(checked: Any) -> bool:
    """Does the validated journal post to a sales-tax control account or carry a tax code?"""
    return any(
        line.spec.tax_code or line.account.system_role in TAX_ROLES for line in checked.lines
    )


# ---- late adjustments (G-03-T08) --------------------------------------------------------------
#
# A document dated inside a filed period is refused by the Tax lock — unless it is posted as a
# **late adjustment** (``JournalSpec(late_adjustment=True)``, or inside ``late_adjustments()``
# for a document's own posting service; the bills API takes ``late_adjustment: true``). The
# journal posts on its own date; its net GST/HST (or QST) is recorded as a ``LateAdjustment`` of
# the registration's **next period that isn't filed** — an increase of net tax on line 104, a
# decrease on line 107 — and written on that period's return in progress. A flagged journal
# whose date is not in a filed period is treated like any other. The module's own lock and the
# general-ledger lock still apply.

_LATE: Any = None


def _late_flag() -> Any:
    global _LATE  # noqa: PLW0603 - created once, on first use
    if _LATE is None:
        from contextvars import ContextVar

        _LATE = ContextVar("numo9_tax_late_adjustment", default=False)
    return _LATE


class late_adjustments:  # noqa: N801 - used as ``with late_adjustments():``
    """Postings inside the block are late adjustments when their date is in a filed period."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.token: Any = None

    def __enter__(self) -> None:
        self.token = _late_flag().set(bool(self.enabled))

    def __exit__(self, *exc: object) -> None:
        _late_flag().reset(self.token)


#: Control-account roles of each filing registration type: (payable, receivable).
REGISTRATION_ROLES = {
    "rt": ("gst_hst_payable", "itc_receivable"),
    "qst": ("qst_payable", "qst_itr"),
}


def _is_late(spec: Any) -> bool:
    return bool(getattr(spec, "late_adjustment", False) or _late_flag().get())


def _filed_period(organisation: Any, kind: str, day: dt.date) -> FilingPeriod | None:
    """The filed period of the organisation's ``kind`` registration containing ``day``."""
    found: FilingPeriod | None = (
        FilingPeriod.objects.filter(
            registration__type=kind,
            registration__deleted_at__isnull=True,
            start__lte=day,
            end__gte=day,
            status__in=(PeriodStatus.FILED, PeriodStatus.PAID),
        )
        .select_related("registration")
        .first()
    )
    return found


def _net_tax(checked: Any, kind: str) -> Any:
    """Net tax the journal adds for a registration type: collected − claimable."""
    from decimal import Decimal

    payable, receivable = REGISTRATION_ROLES[kind]
    total = Decimal("0.00")
    for line in checked.lines:
        role = line.account.system_role
        if role == payable:
            total += line.credit - line.debit
        elif role == receivable:
            total -= line.debit - line.credit
    return total


def _late_targets(
    checked: Any, spec: Any, organisation: Any
) -> list[tuple[str, FilingPeriod, Any]]:
    """(registration type, filed period, net tax) for each registration the journal is late for."""
    out = []
    for kind in REGISTRATION_ROLES:
        delta = _net_tax(checked, kind)
        if not delta:
            continue
        period = _filed_period(organisation, kind, spec.date)
        if period is not None:
            out.append((kind, period, delta))
    return out


def tax_lock_guard(checked: Any, spec: Any, organisation: Any, person: Any) -> None:
    """Ledger posting guard: a journal with tax is refused in a Tax-locked period, unless it is
    posted as a late adjustment of a filed period (then the next open period must exist)."""
    from numo9.orgsettings.locks import assert_not_locked
    from numo9.orgsettings.models import LockModule

    if not touches_tax(checked):
        return
    if _is_late(spec):
        targets = _late_targets(checked, spec, organisation)
        if targets:
            for _kind, period, _delta in targets:
                next_open(period)  # refuses when no period can carry it
            return
    assert_not_locked(organisation, LockModule.TAX, spec.date, person)


def next_open(period: FilingPeriod) -> FilingPeriod:
    """The registration's first period after ``period`` that isn't filed."""
    found: FilingPeriod | None = (
        FilingPeriod.objects.filter(registration_id=period.registration_id, start__gt=period.end)
        .exclude(status__in=(PeriodStatus.FILED, PeriodStatus.PAID))
        .order_by("start")
        .first()
    )
    if found is None:
        raise TaxError(
            _("No open period after %(period)s can carry the adjustment.")
            % {"period": str(period)},
            code="tax.return.no_open_period",
        )
    return found


def adjustment_lines(period: FilingPeriod) -> dict[str, str]:
    """Lines 104 and 107 of ``period`` from its late adjustments."""
    from decimal import Decimal

    from .models import LateAdjustment

    totals = {"104": Decimal("0.00"), "107": Decimal("0.00")}
    with _org(period):
        for row in LateAdjustment.objects.filter(target_period=period):
            totals[row.line] += row.amount
    return {line: f"{amount:.2f}" for line, amount in totals.items()}


def late_adjustment_rows(period: FilingPeriod) -> list[dict[str, Any]]:
    """The late adjustments listed on ``period``'s return, in document-date order."""
    from .models import LateAdjustment

    with _org(period):
        rows = LateAdjustment.objects.filter(target_period=period).select_related(
            "journal", "filed_period"
        )
        return [
            {
                "journal": str(row.journal.public_id),
                "journal_number": row.journal.number,
                "source_type": row.journal.source_type,
                "source_id": row.journal.source_id,
                "document_date": row.document_date.isoformat(),
                "filed_period": str(row.filed_period),
                "line": row.line,
                "amount": f"{row.amount:.2f}",
            }
            for row in rows
        ]


def _write_adjustments(period: FilingPeriod) -> None:
    """Put lines 104 / 107 on the period's return in progress (if any)."""
    open_one = TaxReturn.objects.filter(
        period=period, status__in=OPEN_RETURN_STATUSES, deleted_at__isnull=True
    ).first()
    if open_one is not None:
        if open_one.status == ReturnStatus.DRAFT:
            open_one.lines = computed_lines(open_one)
        else:
            open_one.lines = {**(open_one.lines or {}), **adjustment_lines(period)}
        open_one.save()


def record_late_adjustment(
    entry: Any, checked: Any, spec: Any, organisation: Any, person: Any
) -> None:
    """Ledger posted hook: record the late adjustments of a flagged journal (docstring above)."""
    from .models import LateAdjustment

    if not _is_late(spec) or not touches_tax(checked):
        return
    for _kind, period, delta in _late_targets(checked, spec, organisation):
        target = next_open(period)
        LateAdjustment.objects.create(
            organisation=organisation,
            registration=period.registration,
            journal=entry,
            document_date=spec.date,
            filed_period=period,
            target_period=target,
            line="104" if delta > 0 else "107",
            amount=abs(delta),
            created_by=_person(person),
        )
        _write_adjustments(target)
        from numo9.audit.service import record

        record(
            "tax.return.late_adjustment",
            obj=period.registration,
            actor=_person(person),
            meta={
                "journal": str(entry.public_id),
                "document_date": spec.date.isoformat(),
                "filed_period": str(period),
                "reported_in": str(target),
                "line": "104" if delta > 0 else "107",
                "amount": f"{abs(delta):.2f}",
            },
        )
