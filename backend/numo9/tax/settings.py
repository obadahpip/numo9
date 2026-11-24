"""Tax settings access (G-06-T02): ``tax_settings(organisation)`` — the row, created with the
defaults (accrual basis, per-line rounding, no quick method, no default codes) the first time."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from numo9.tenancy.context import current_org, org_context

from .models import TaxSettings


def tax_settings(organisation: Any = None) -> TaxSettings:
    org = organisation or current_org()
    if org is None:
        raise RuntimeError("tax_settings() needs an active organisation.")
    existing: TaxSettings | None = TaxSettings._base_manager.filter(organisation=org).first()
    if existing is not None:
        return existing
    with org_context(org):
        row = TaxSettings(organisation=org)
        try:
            with transaction.atomic():
                row.save()
        except IntegrityError:  # created at the same moment by another request
            found: TaxSettings = TaxSettings._base_manager.get(organisation=org)
            return found
    return row


# ---- tax basis (G-06-T05) ------------------------------------------------------------------

MIN_BASIS_REASON = 10


def basis_change_check(organisation: Any, basis: str, today: Any) -> dict[str, Any]:
    """What changing the basis to ``basis`` on ``today`` means: ``mid_year`` — not on the first
    day of a fiscal year (returns of the year so far keep the old basis), with a warning."""
    from django.utils.translation import gettext as _

    from numo9.orgsettings.fiscal import fiscal_year
    from numo9.orgsettings.service import get_settings

    from .models import TaxBasis

    current = tax_settings(organisation)
    start, _end = fiscal_year(get_settings(organisation), today)
    mid_year = basis != current.basis and today != start
    warning = (
        _(
            "The fiscal year started on %(start)s: changing to the %(basis)s basis during the "
            "year leaves the returns already filed on the %(current)s basis."
        )
        % {
            "start": start.isoformat(),
            "basis": str(TaxBasis(basis).label).lower(),
            "current": str(TaxBasis(current.basis).label).lower(),
        }
        if mid_year
        else ""
    )
    return {"changes": basis != current.basis, "mid_year": mid_year, "warning": warning}


def change_basis(organisation: Any, basis: str, reason: str, *, user: Any, today: Any) -> Any:
    """Change the tax basis with a reason (≥ 10 characters) — refused without one; audited with
    the person, the reason and whether it was mid-year."""
    from django.core.exceptions import ValidationError
    from django.utils.translation import gettext as _

    from numo9.audit import service as audit
    from numo9.ledger.renumber import acting_as

    from .models import TaxBasis

    if basis not in TaxBasis.values:
        raise ValidationError(
            {"basis": ValidationError(_("Choose accrual or cash."), code="tax.settings.basis")}
        )
    text = " ".join((reason or "").split())
    if len(text) < MIN_BASIS_REASON:
        raise ValidationError(
            {
                "reason": ValidationError(
                    _("Say why the tax basis changes (at least %(min)d characters)."),
                    code="tax.settings.basis_reason_required",
                    params={"min": MIN_BASIS_REASON},
                )
            }
        )
    check = basis_change_check(organisation, basis, today)
    row = tax_settings(organisation)
    if not check["changes"]:
        return row
    with org_context(organisation), transaction.atomic(), acting_as(user):
        before = row.basis
        row.basis = basis
        row.save()
        audit.record(
            "tax.taxsettings.basis_changed",
            obj=row,
            changes={"basis": [before, basis]},
            meta={"reason": text, "mid_year": check["mid_year"]},
            actor=user if getattr(user, "is_authenticated", False) else None,
        )
    return row


def report_basis(organisation: Any, override: str | None = None) -> tuple[str, bool]:
    """The basis a report uses: ``(basis, from_default)`` — the per-report override when given
    (K-01), else the organisation's default."""
    from .models import TaxBasis

    if override in TaxBasis.values:
        return str(override), False
    return tax_settings(organisation).basis, True


def basis_label(organisation: Any, override: str | None = None) -> str:
    """The report header's label: "Basis: Cash (organisation default)" or "Basis: Accrual
    (this report)"."""
    from django.utils.translation import gettext as _

    from .models import TaxBasis

    basis, default = report_basis(organisation, override)
    name = str(TaxBasis(basis).label)
    return (
        _("Basis: %(basis)s (organisation default)") % {"basis": name}
        if default
        else _("Basis: %(basis)s (this report)") % {"basis": name}
    )
