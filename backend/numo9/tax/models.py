"""Sales-tax table (G-01): authorities, effective-dated components, tax codes.

Every organisation has its own table (``OrgOwnedModel``): rates are the same for everyone, but
each organisation's components post to **its** control accounts and an organisation can add or
version its own codes. The Canadian table is installed from ``data/tax_ca.json`` (G-01-T04).

``TaxAuthority`` (G-01-T02) — who levies the tax: CRA (GST/HST), Revenu Québec (QST), British
Columbia, Manitoba and Saskatchewan (PST / RST).

``TaxComponent`` (G-01-T02) — one rate of one tax for one period:

- ``key`` — what the rate is (``gst``, ``hst_on``, ``qst``, ``pst_bc``, ``rst_mb``…); a key's
  versions follow each other in time and **never overlap** (database exclusion constraint
  ``tax_component_no_overlap``): NS HST 15 % to 31 Mar 2025, then 14 % from 1 Apr 2025;
- ``rate`` — percent, numeric(7,4) (``9.9750``);
- ``effective_from`` / ``effective_to`` — first and **last** day in force (``effective_to`` null =
  open); a rate is offered and accepted only on documents dated inside its range;
- ``kind`` — GST, HST, PST or QST: decides the control account by default (GST/HST payable /
  receivable, PST payable, QST payable / ITR) when no explicit account is set;
- ``recoverable`` — on purchases, the tax comes back as an input tax credit (GST/HST) or refund
  (QST ITR); PST is never recoverable (it is added to the cost);
- ``side`` — the documents it may appear on: both, sales only or purchases only;
- ``control_account_sales`` / ``control_account_purchase`` — the organisation's accounts the
  collected / paid tax posts to (null → the system account of the kind's role).

Filing cycles (G-03a, ``docs/specs/filing-cycles.md``):

- ``FilingCycle`` (G-03a-T04) — a registration's filing frequency (monthly / quarterly / annual)
  from ``effective_from`` until the next cycle, with the CRA or Revenu Québec approval reference
  and date, a note and its author; unique per (registration, effective_from);
- ``FilingPeriod`` (G-03a-T05) — one reporting period: start and end (both inclusive), kind
  (regular / custom / stub), sequence number, return and payment due dates, status (open /
  closed / filed / paid). The periods of a registration **never overlap** — a PostgreSQL
  ``daterange`` exclusion constraint (GiST) refuses an overlapping row.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel

SOURCE_LANGUAGE = "en-ca"


def active_on(start: Any, end: Any, day: Any) -> bool:
    """``day`` is inside ``[start, end]`` (``end`` null = open)."""
    return bool(start <= day and (end is None or day <= end))


def _overlaps(start: Any, end: Any, other_start: Any, other_end: Any) -> bool:
    return (other_end is None or start <= other_end) and (end is None or end >= other_start)


class TaxError(ValidationError):
    """A tax-table rule refused the change (``code`` names it)."""


class DateRange(models.Func):
    """``daterange(from, to, '[]')`` — a component's days; both ends inclusive, null = open."""

    function = "DATERANGE"
    output_field = DateRangeField()


class NamedMixin(models.Model):
    name_i18n = models.JSONField(_("name"), default=dict)

    class Meta:
        abstract = True

    @property
    def name(self) -> str:
        return self.name_in(translation.get_language() or SOURCE_LANGUAGE)

    def name_in(self, language: str) -> str:
        names = self.name_i18n or {}
        return str(names.get(language.lower()) or names.get(SOURCE_LANGUAGE) or "")


class TaxAuthority(NamedMixin, OrgOwnedModel):
    """CRA, Revenu Québec, British Columbia, Manitoba, Saskatchewan."""

    code = models.CharField(_("code"), max_length=10)

    class Meta:
        ordering = ("code",)
        verbose_name = _("tax authority")
        verbose_name_plural = _("tax authorities")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["organisation", "code"], name="tax_authority_code")
        ]

    def __str__(self) -> str:
        return self.code


class TaxKind(models.TextChoices):
    GST = "gst", _("GST")
    HST = "hst", _("HST")
    PST = "pst", _("PST")
    QST = "qst", _("QST")


class TaxSide(models.TextChoices):
    SALES = "sales", _("Sales")
    PURCHASE = "purchase", _("Purchases")


class ComponentSide(models.TextChoices):
    BOTH = "both", _("Sales and purchases")
    SALES = "sales", _("Sales only")
    PURCHASE = "purchase", _("Purchases only")


class TaxComponent(NamedMixin, AuditedModel, OrgOwnedModel):
    authority = models.ForeignKey(
        TaxAuthority,
        on_delete=models.PROTECT,
        related_name="components",
        verbose_name=_("authority"),
    )
    key = models.CharField(_("key"), max_length=40)
    kind = models.CharField(_("tax"), max_length=4, choices=TaxKind.choices)
    rate = models.DecimalField(
        _("rate (%)"),
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    effective_from = models.DateField(_("effective from"))
    effective_to = models.DateField(_("effective to"), null=True, blank=True)
    recoverable = models.BooleanField(_("recoverable on purchases"), default=True)
    side = models.CharField(
        _("used on"), max_length=10, choices=ComponentSide.choices, default=ComponentSide.BOTH
    )
    control_account_sales = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("control account (sales)"),
    )
    control_account_purchase = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("control account (purchases)"),
    )

    class Meta:
        ordering = ("key", "effective_from")
        verbose_name = _("tax component")
        verbose_name_plural = _("tax components")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="tax_component_range_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(rate__gte=0) & models.Q(rate__lte=100),
                name="tax_component_rate_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=TaxKind.values), name="tax_component_kind_valid"
            ),
            # PostgreSQL only (btree_gist): added by PostgresOnlyAddConstraint in migration 0001.
            ExclusionConstraint(
                name="tax_component_no_overlap",
                index_type="GIST",
                expressions=[
                    ("organisation", RangeOperators.EQUAL),
                    ("key", RangeOperators.EQUAL),
                    (
                        DateRange("effective_from", "effective_to", models.Value("[]")),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                violation_error_code="tax.component.overlap",
                violation_error_message=_(
                    "Another version of this tax component is already in force on some of these "
                    "days."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} {self.rate.normalize():f} %"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def is_active_on(self, day: Any) -> bool:
        return active_on(self.effective_from, self.effective_to, day)

    def clean(self) -> None:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise TaxError(
                _("A component can't end before it starts."), code="tax.component.range_invalid"
            )
        overlapping = TaxComponent._base_manager.filter(
            organisation_id=self.organisation_id, key=self.key
        ).exclude(pk=self.pk)
        for other in overlapping:
            starts_before_other_ends = (
                other.effective_to is None or self.effective_from <= other.effective_to
            )
            ends_after_other_starts = (
                self.effective_to is None or self.effective_to >= other.effective_from
            )
            if starts_before_other_ends and ends_after_other_starts:
                raise TaxError(
                    _(
                        "%(component)s already has a version in force from %(start)s: versions of "
                        "a component can't overlap."
                    ),
                    code="tax.component.overlap",
                    params={"component": self.key, "start": other.effective_from.isoformat()},
                )


# ---- tax codes (G-01-T03) ----------------------------------------------------------------------


class TaxCodeType(models.TextChoices):
    TAXABLE = "taxable", _("Taxable")
    ZERO_RATED = "zero_rated", _("Zero-rated")
    EXEMPT = "exempt", _("Exempt")
    OUT_OF_SCOPE = "out_of_scope", _("Out of scope")


class TaxCode(NamedMixin, AuditedModel, OrgOwnedModel):
    """A tax code as a document line picks it: a group of components with a type and a side.

    ``code`` is the stable key (``sales.ON.standard``, ``purchase.QC.standard``,
    ``sales.zero_rated``); a code has **versions** (``version`` 1, 2…), each in force over
    ``effective_from`` … ``effective_to`` (inclusive, null = open) with its own components —
    versions of a code never overlap. A document line stores the version it used, so changing a
    code later never changes posted documents (G-01-T10). ``province`` is the jurisdiction the
    code is for (blank for codes that apply anywhere: zero-rated, exempt, out of scope).

    - ``TAXABLE`` — at least one component;
    - ``ZERO_RATED`` — taxable at 0 %: components at a 0 % rate only (reported on the return);
    - ``EXEMPT`` / ``OUT_OF_SCOPE`` — no component.
    """

    code = models.CharField(_("code"), max_length=60)
    version = models.PositiveSmallIntegerField(_("version"), default=1)
    side = models.CharField(_("side"), max_length=10, choices=TaxSide.choices)
    type = models.CharField(_("type"), max_length=12, choices=TaxCodeType.choices)
    province = models.CharField(_("province"), max_length=2, blank=True)
    effective_from = models.DateField(_("effective from"))
    effective_to = models.DateField(_("effective to"), null=True, blank=True)
    #: Share of the ITC/ITR claimable on purchases with this code (50 = half; G-01-T05);
    #: null = each component's own rule. An account's or a line's own % wins.
    itc_restriction_pct = models.DecimalField(
        _("claimable ITC %"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    archived_at = models.DateTimeField(_("archived at"), null=True, blank=True)

    class Meta:
        ordering = ("side", "code", "version")
        verbose_name = _("tax code")
        verbose_name_plural = _("tax codes")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "code", "version"], name="tax_code_version_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(side__in=TaxSide.values), name="tax_code_side_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(type__in=TaxCodeType.values), name="tax_code_type_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="tax_code_range_valid",
            ),
            # PostgreSQL only (btree_gist): added by PostgresOnlyAddConstraint in migration 0002.
            ExclusionConstraint(
                name="tax_code_no_overlap",
                index_type="GIST",
                expressions=[
                    ("organisation", RangeOperators.EQUAL),
                    ("code", RangeOperators.EQUAL),
                    (
                        DateRange("effective_from", "effective_to", models.Value("[]")),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                violation_error_code="tax.code.overlap",
                violation_error_message=_(
                    "Another version of this tax code is already in force on some of these days."
                ),
            ),
        ]

    def __str__(self) -> str:
        return self.name or self.code

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def is_active_on(self, day: Any) -> bool:
        return active_on(self.effective_from, self.effective_to, day)

    def clean(self) -> None:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise TaxError(
                _("A tax code can't end before it starts."), code="tax.code.range_invalid"
            )
        others = TaxCode._base_manager.filter(
            organisation_id=self.organisation_id, code=self.code
        ).exclude(pk=self.pk)
        for other in others:
            if _overlaps(
                self.effective_from, self.effective_to, other.effective_from, other.effective_to
            ):
                raise TaxError(
                    _(
                        "%(code)s already has version %(version)d in force from %(start)s: "
                        "versions of a tax code can't overlap."
                    ),
                    code="tax.code.overlap",
                    params={
                        "code": self.code,
                        "version": other.version,
                        "start": other.effective_from.isoformat(),
                    },
                )


def _locked_components(code: TaxCode) -> TaxError:
    return TaxError(
        _(
            "The components of %(code)s version %(version)d can't change: create a new version "
            "from a date instead (posted lines keep this one)."
        ),
        code="tax.code.component_locked",
        params={"code": code.code, "version": code.version},
    )


class TaxCodeComponent(OrgOwnedModel):
    """One component of a tax code version, with an optional recoverable % override.

    ``recoverable_pct`` — on purchases, the share of the component's tax that comes back (an ITC
    / ITR): null = the component's own rule (100 % when ``recoverable``, else 0 %); 50 for meals
    and entertainment. The component must fit the code: its ``side`` allows the code's side (a
    sales code can't hold a purchases-only component) and it is in force over the code version's
    whole range."""

    tax_code = models.ForeignKey(
        TaxCode, on_delete=models.CASCADE, related_name="components", verbose_name=_("tax code")
    )
    component = models.ForeignKey(
        TaxComponent, on_delete=models.PROTECT, related_name="codes", verbose_name=_("component")
    )
    position = models.PositiveSmallIntegerField(_("position"), default=1)
    recoverable_pct = models.DecimalField(
        _("recoverable %"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )

    class Meta:
        ordering = ("tax_code", "position")
        verbose_name = _("tax code component")
        verbose_name_plural = _("tax code components")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["tax_code", "component"], name="tax_code_component"),
            models.CheckConstraint(
                condition=models.Q(recoverable_pct__isnull=True)
                | (models.Q(recoverable_pct__gte=0) & models.Q(recoverable_pct__lte=100)),
                name="tax_code_component_pct_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tax_code.code} · {self.component.key}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise _locked_components(self.tax_code)
        self.clean()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise _locked_components(self.tax_code)

    def clean(self) -> None:
        code, part = self.tax_code, self.component
        if part.side != ComponentSide.BOTH and part.side != code.side:
            raise TaxError(
                _("%(component)s is used on %(side)s only: it can't be part of %(code)s."),
                code="tax.code.component_side",
                params={
                    "component": str(part),
                    "side": TaxSide(part.side).label.lower(),
                    "code": code.code,
                },
            )
        starts_late = part.effective_from > code.effective_from
        ends_early = part.effective_to is not None and (
            code.effective_to is None or part.effective_to < code.effective_to
        )
        if starts_late or ends_early:
            raise TaxError(
                _("%(component)s isn't in force over the whole of %(code)s version %(version)d."),
                code="tax.code.component_range",
                params={"component": str(part), "code": code.code, "version": code.version},
            )
        if code.type in (TaxCodeType.EXEMPT, TaxCodeType.OUT_OF_SCOPE):
            raise TaxError(
                _("An exempt or out-of-scope code has no tax component."),
                code="tax.code.components_not_allowed",
            )
        if code.type == TaxCodeType.ZERO_RATED and part.rate != 0:
            raise TaxError(
                _("A zero-rated code only holds components with a rate of zero."),
                code="tax.code.zero_rate",
            )

    @property
    def effective_recoverable_pct(self) -> Decimal:
        """The claimable % for this component with no line or account rule (G-01-T05)."""
        from .recovery import claimable_pct

        return claimable_pct(self)


# ---- tax settings (G-06-T02) ------------------------------------------------------------------


class TaxBasis(models.TextChoices):
    """When sales tax is reported: when invoiced (accrual) or when paid (cash)."""

    ACCRUAL = "accrual", _("Accrual")
    CASH = "cash", _("Cash")


class RoundingMode(models.TextChoices):
    """Where tax is rounded to the cent (G-01-T06 rounds per line by default)."""

    LINE = "line", _("Per line")
    DOCUMENT = "document", _("Per document")


#: Account types a default code is kept for, per side (G-06; the account's own code wins).
DEFAULT_CODE_TYPES: dict[str, tuple[str, ...]] = {
    "sales": ("revenue", "asset"),
    "purchase": ("expense", "asset", "liability"),
}


class TaxSettings(AuditedModel, OrgOwnedModel):
    """The organisation's sales-tax settings (G-06-T02), one row per organisation, on the single
    "Tax registrations & settings" page:

    - ``basis`` — accrual or cash; the default basis of tax reports (K-01 may override per
      report and says so);
    - ``rounding_mode`` — per line (default) or per document;
    - ``quick_method`` / ``quick_method_from`` — the GST/HST quick-method election and its date;
    - ``default_codes`` — ``{"sales": {"revenue": "<code key>"}, "purchase": {"expense": …}}``: the
      code new lines get per account type when the account has none (keys as ``TaxCode.code``).

    Registrations and numbers stay on ``orgsettings.TaxRegistration`` (A-05); every change here is
    audited with its author.
    """

    basis = models.CharField(
        _("tax basis"), max_length=10, choices=TaxBasis.choices, default=TaxBasis.ACCRUAL
    )
    rounding_mode = models.CharField(
        _("rounding"), max_length=10, choices=RoundingMode.choices, default=RoundingMode.LINE
    )
    quick_method = models.BooleanField(_("quick method elected"), default=False)
    out_of_scope_after_stop = models.BooleanField(
        _("sales after a GST/HST stop default to out of scope"),
        default=True,
        db_default=True,
        help_text=_(
            "After filing stops (G-03b), new sales lines default to Out of scope instead of "
            "charging GST/HST."
        ),
    )
    quick_method_from = models.DateField(_("quick method from"), null=True, blank=True)
    default_codes = models.JSONField(_("default codes"), default=dict, blank=True)

    class Meta:
        verbose_name = _("tax settings")
        verbose_name_plural = _("tax settings")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["organisation"], name="tax_settings_one_per_org"),
            models.CheckConstraint(
                condition=models.Q(basis__in=TaxBasis.values), name="tax_settings_basis_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(rounding_mode__in=RoundingMode.values),
                name="tax_settings_rounding_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(quick_method=False) | models.Q(quick_method_from__isnull=False),
                name="tax_settings_quick_method_dated",
            ),
        ]

    def __str__(self) -> str:
        return str(_("Tax settings"))

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}
        if self.quick_method and self.quick_method_from is None:
            errors.setdefault("quick_method_from", []).append(
                ValidationError(
                    _("Give the date the quick method starts."),
                    code="tax.settings.quick_method_date",
                )
            )
        codes = self.default_codes or {}
        if not isinstance(codes, dict) or set(codes) - set(DEFAULT_CODE_TYPES):
            errors.setdefault("default_codes", []).append(
                ValidationError(
                    _("Default codes are kept for the sales and purchase sides only."),
                    code="tax.settings.default_codes_invalid",
                )
            )
        else:
            known = set(
                TaxCode._base_manager.filter(organisation_id=self.organisation_id).values_list(
                    "code", "side"
                )
            )
            for side, by_type in codes.items():
                if not isinstance(by_type, dict):
                    by_type = {}
                for account_type, key in by_type.items():
                    if account_type not in DEFAULT_CODE_TYPES[side]:
                        errors.setdefault("default_codes", []).append(
                            ValidationError(
                                _("No default %(side)s code is kept for %(type)s accounts."),
                                code="tax.settings.default_codes_invalid",
                                params={"side": side, "type": account_type},
                            )
                        )
                    elif (key, side) not in known:
                        errors.setdefault("default_codes", []).append(
                            ValidationError(
                                _("There's no %(side)s tax code %(code)s."),
                                code="tax.code.unknown",
                                params={"side": side, "code": key},
                            )
                        )
        if errors:
            raise ValidationError(errors)

    def default_code(self, side: str, account_type: str) -> str:
        """The default code key of ``side`` for ``account_type`` ('' when none is set)."""
        return str(((self.default_codes or {}).get(side) or {}).get(account_type) or "")


# ---- filing cycles (G-03a) ---------------------------------------------------------------------


class FilingFrequency(models.TextChoices):
    MONTHLY = "monthly", _("Monthly")
    QUARTERLY = "quarterly", _("Quarterly")
    ANNUAL = "annual", _("Annual")


class FilingCycle(OrgOwnedModel):
    registration = models.ForeignKey(
        "orgsettings.TaxRegistration",
        on_delete=models.CASCADE,
        related_name="filing_cycles",
        verbose_name=_("registration"),
    )
    frequency = models.CharField(_("frequency"), max_length=10, choices=FilingFrequency.choices)
    effective_from = models.DateField(_("effective from"))
    approval_ref = models.CharField(_("approval reference"), max_length=100, blank=True)
    approval_date = models.DateField(_("approval date"), null=True, blank=True)
    note = models.TextField(_("note"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ("registration", "effective_from")
        verbose_name = _("filing cycle")
        verbose_name_plural = _("filing cycles")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("registration", "effective_from"), name="tax_filingcycle_unique_start"
            ),
            models.CheckConstraint(
                condition=models.Q(frequency__in=FilingFrequency.values),
                name="tax_filingcycle_frequency_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_frequency_display()} from {self.effective_from:%Y-%m-%d}"


class PeriodKind(models.TextChoices):
    REGULAR = "regular", _("Regular")
    CUSTOM = "custom", _("Out of cycle")
    STUB = "stub", _("Stub")


class PeriodStatus(models.TextChoices):
    OPEN = "open", _("Open")
    CLOSED = "closed", _("Closed")
    FILED = "filed", _("Filed")
    PAID = "paid", _("Paid")


class PeriodAttention(models.TextChoices):
    """What an unfiled period needs (recomputed nightly, G-03a-T17)."""

    DUE_SOON = "due_soon", _("Due soon")
    OVERDUE = "overdue", _("Overdue")


#: Filed and paid periods are immutable (never deleted, moved or regenerated).
LOCKED_PERIOD_STATUSES: frozenset[str] = frozenset({PeriodStatus.FILED, PeriodStatus.PAID})


class FilingPeriod(OrgOwnedModel):
    registration = models.ForeignKey(
        "orgsettings.TaxRegistration",
        on_delete=models.CASCADE,
        related_name="filing_periods",
        verbose_name=_("registration"),
    )
    start = models.DateField(_("start"))
    end = models.DateField(_("end"))
    kind = models.CharField(
        _("kind"), max_length=10, choices=PeriodKind.choices, default=PeriodKind.REGULAR
    )
    frequency = models.CharField(
        _("frequency"), max_length=10, choices=FilingFrequency.choices, blank=True
    )
    sequence_no = models.PositiveIntegerField(_("sequence number"))
    due_date = models.DateField(_("return due"))
    payment_due_date = models.DateField(_("payment due"))
    status = models.CharField(
        _("status"), max_length=10, choices=PeriodStatus.choices, default=PeriodStatus.OPEN
    )
    attention = models.CharField(
        _("attention"),
        max_length=10,
        choices=PeriodAttention.choices,
        blank=True,
        default="",
        db_default="",  # a database default: rows written by the previous release stay valid
    )
    note = models.TextField(_("note"), blank=True)
    filed_at = models.DateTimeField(_("filed at"), null=True, blank=True)

    class Meta:
        ordering = ("registration", "start")
        verbose_name = _("filing period")
        verbose_name_plural = _("filing periods")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(end__gte=models.F("start")), name="tax_filingperiod_dates"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=PeriodKind.values), name="tax_filingperiod_kind_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=PeriodStatus.values),
                name="tax_filingperiod_status_valid",
            ),
            ExclusionConstraint(
                name="tax_filingperiod_no_overlap",
                index_type="GIST",
                expressions=[
                    ("registration", RangeOperators.EQUAL),
                    (DateRange("start", "end", models.Value("[]")), RangeOperators.OVERLAPS),
                ],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.start:%Y-%m-%d} – {self.end:%Y-%m-%d}"

    @property
    def is_locked(self) -> bool:
        return self.status in LOCKED_PERIOD_STATUSES


# ---- stop & restart filing (G-03b) ---------------------------------------------------------------


class RegistrationAction(models.TextChoices):
    STOP = "stop", _("Stopped filing")
    RESTART = "restart", _("Restarted filing")


class StopReason(models.TextChoices):
    DEREGISTRATION = "deregistration", _("Registration cancelled")
    SMALL_SUPPLIER = "small_supplier", _("Small supplier")
    SUSPENSION = "suspension", _("Suspended by the CRA or Revenu Québec")
    OTHER = "other", _("Other")


class RegistrationStatusEvent(OrgOwnedModel):
    """A stop or restart of a filing registration (G-03b-T02), always by a person (gap-44: never
    "System Generated").

    - ``action`` — ``stop``: ``date`` is the **last day registered**; ``restart``: ``date`` is the
      first day registered again, with the ``frequency`` it files from then;
    - ``reason_code`` (stops: deregistration, small supplier, suspension, other) and
      ``reason_text``.

    The events of a registration alternate stop, restart, stop… in date order; between a stop and
    the next restart the registration has no periods (the "Not registered" gap).
    """

    registration = models.ForeignKey(
        "orgsettings.TaxRegistration",
        on_delete=models.CASCADE,
        related_name="status_events",
        verbose_name=_("registration"),
    )
    action = models.CharField(_("action"), max_length=8, choices=RegistrationAction.choices)
    date = models.DateField(_("date"))
    reason_code = models.CharField(
        _("reason"), max_length=16, choices=StopReason.choices, blank=True
    )
    reason_text = models.TextField(_("note"), blank=True)
    frequency = models.CharField(
        _("frequency"), max_length=10, choices=FilingFrequency.choices, blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("by"),
    )
    created_at = models.DateTimeField(_("recorded at"), auto_now_add=True)

    class Meta:
        ordering = ("registration", "date", "created_at", "pk")
        verbose_name = _("registration status change")
        verbose_name_plural = _("registration status changes")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(action__in=RegistrationAction.values),
                name="tax_regevent_action_valid",
            ),
            # A stop has a reason; a restart has a frequency.
            models.CheckConstraint(
                condition=(
                    models.Q(action=RegistrationAction.STOP, reason_code__in=StopReason.values)
                    | models.Q(
                        action=RegistrationAction.RESTART, frequency__in=FilingFrequency.values
                    )
                ),
                name="tax_regevent_fields_match_action",
            ),
            models.UniqueConstraint(
                fields=("registration", "action", "date"), name="tax_regevent_unique_day"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("registration", "date"), name="tax_regevent_reg_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.date:%Y-%m-%d}"


# ---- GST/HST return (G-03) ---------------------------------------------------------------------


class ReturnStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    REVIEWED = "reviewed", _("Reviewed")
    FILED = "filed", _("Filed")
    #: A filed return replaced by a later version (G-03-T09); it stays viewable.
    AMENDED = "amended", _("Amended")


class ReturnMethod(models.TextChoices):
    REGULAR = "regular", _("Regular method")
    QUICK = "quick", _("Quick method")


#: A return being worked on (one at a time per period).
OPEN_RETURN_STATUSES: frozenset[str] = frozenset({ReturnStatus.DRAFT, ReturnStatus.REVIEWED})


class TaxReturn(AuditedModel, OrgOwnedModel):
    """The return of one filing period of a registration (G-03-T02): its line values (101–115,
    as text amounts keyed by line), its method, and the preparer → reviewer → filed workflow
    (G-03-T06). ``version`` counts from 1; an amendment is the next version, and the filed
    return it replaces becomes ``amended`` (G-03-T09).

    Per period: versions are unique, **one filed return that isn't amended**, and one return in
    progress (draft or reviewed) at a time.
    """

    registration = models.ForeignKey(
        "orgsettings.TaxRegistration",
        on_delete=models.PROTECT,
        related_name="tax_returns",
        verbose_name=_("registration"),
    )
    period = models.ForeignKey(
        FilingPeriod, on_delete=models.PROTECT, related_name="returns", verbose_name=_("period")
    )
    version = models.PositiveIntegerField(_("version"), default=1)
    status = models.CharField(
        _("status"), max_length=10, choices=ReturnStatus.choices, default=ReturnStatus.DRAFT
    )
    method = models.CharField(
        _("method"), max_length=10, choices=ReturnMethod.choices, default=ReturnMethod.REGULAR
    )
    lines = models.JSONField(_("line values"), default=dict, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("prepared by"),
    )
    prepared_at = models.DateTimeField(_("prepared at"), null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("reviewed by"),
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    filed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("filed by"),
    )
    filed_at = models.DateTimeField(_("filed at"), null=True, blank=True)
    filed_on = models.DateField(_("filed on"), null=True, blank=True)
    confirmation_no = models.CharField(_("confirmation number"), max_length=40, blank=True)
    amends = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="amendments",
        verbose_name=_("amends"),
    )
    amend_reason = models.TextField(_("reason for the amendment"), blank=True)

    class Meta:
        ordering = ("registration", "period", "version")
        verbose_name = _("tax return")
        verbose_name_plural = _("tax returns")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("period", "version"), name="tax_return_version_unique"),
            models.UniqueConstraint(
                fields=("period",),
                condition=models.Q(status=ReturnStatus.FILED),
                name="tax_return_one_filed_per_period",
            ),
            models.UniqueConstraint(
                fields=("period",),
                condition=models.Q(status__in=sorted(OPEN_RETURN_STATUSES)),
                name="tax_return_one_open_per_period",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ReturnStatus.values), name="tax_return_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(method__in=ReturnMethod.values), name="tax_return_method_valid"
            ),
            models.CheckConstraint(
                condition=~models.Q(status=ReturnStatus.FILED)
                | (models.Q(filed_on__isnull=False) & ~models.Q(confirmation_no="")),
                name="tax_return_filed_has_confirmation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.period} v{self.version}"

    def audit_label(self) -> str:
        return str(self)

    @property
    def is_current(self) -> bool:
        """The latest version of its period."""
        latest = (
            TaxReturn._base_manager.filter(period_id=self.period_id, deleted_at__isnull=True)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
        return latest == self.version

    def clean(self) -> None:
        if self.period_id and self.registration_id:
            period = FilingPeriod._base_manager.filter(pk=self.period_id).first()
            if period is not None and period.registration_id != self.registration_id:
                raise ValidationError(
                    {
                        "period": ValidationError(
                            _("The period belongs to another registration."),
                            code="tax.return.period",
                        )
                    }
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not kwargs.get("update_fields"):
            self.clean()
        super().save(*args, **kwargs)


class LateAdjustment(OrgOwnedModel):
    """The tax of a document dated inside a **filed** period (G-03-T08): it could not change the
    filed return, so its net tax — positive on line 104, negative as a positive amount on line
    107 — is carried by ``target_period``, the registration's next period that isn't filed."""

    registration = models.ForeignKey(
        "orgsettings.TaxRegistration",
        on_delete=models.PROTECT,
        related_name="late_adjustments",
        verbose_name=_("registration"),
    )
    journal = models.ForeignKey(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        related_name="late_adjustments",
        verbose_name=_("journal"),
    )
    document_date = models.DateField(_("document date"))
    filed_period = models.ForeignKey(
        FilingPeriod, on_delete=models.PROTECT, related_name="+", verbose_name=_("filed period")
    )
    target_period = models.ForeignKey(
        FilingPeriod,
        on_delete=models.PROTECT,
        related_name="late_adjustments",
        verbose_name=_("reported in"),
    )
    line = models.CharField(_("return line"), max_length=3)
    amount = models.DecimalField(_("amount"), max_digits=18, decimal_places=2)

    class Meta:
        ordering = ("target_period", "document_date", "pk")
        verbose_name = _("late adjustment")
        verbose_name_plural = _("late adjustments")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("journal", "registration"), name="tax_lateadjustment_once_per_journal"
            ),
            models.CheckConstraint(
                condition=models.Q(line__in=("104", "107")), name="tax_lateadjustment_line_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="tax_lateadjustment_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.document_date:%Y-%m-%d} → {self.line}: {self.amount}"


class TaxLineSource(models.TextChoices):
    """Where a posted tax line comes from (G-05-T02)."""

    DOCUMENT = "document", _("Document")
    JOURNAL = "journal", _("Journal")


class TaxLine(OrgOwnedModel):
    """One posted line's tax for one component (G-05-T02): what the tax reports read.

    Written in the posting transaction (a ledger posted hook) from the tax the line carried
    (``ledger.validation.TaxPart``): ``basis`` (net amount taxed), ``tax``, ``recoverable``
    (ITC / ITR) and ``non_recoverable`` (added to the cost), signed like the document. A reversal
    copies its original's lines negated (``reverses``). ``source`` is ``journal`` for a manual
    journal's tax-coded line (no calculated tax); ``late`` marks a posting into a filed period
    (G-03-T08)."""

    entry = models.ForeignKey(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        related_name="tax_lines",
        verbose_name=_("journal entry"),
    )
    line_no = models.PositiveSmallIntegerField(_("line"))
    date = models.DateField(_("tax point"))
    side = models.CharField(_("side"), max_length=8, choices=TaxSide.choices)
    code = models.CharField(_("tax code"), max_length=60, blank=True)
    component = models.CharField(_("component"), max_length=40, blank=True)
    kind = models.CharField(_("tax"), max_length=4, blank=True)
    rate = models.DecimalField(_("rate"), max_digits=7, decimal_places=4, null=True, blank=True)
    basis = models.DecimalField(_("basis"), max_digits=18, decimal_places=2, default=Decimal("0"))
    tax = models.DecimalField(_("tax"), max_digits=18, decimal_places=2, default=Decimal("0"))
    recoverable = models.DecimalField(
        _("recoverable"), max_digits=18, decimal_places=2, default=Decimal("0")
    )
    non_recoverable = models.DecimalField(
        _("non-recoverable"), max_digits=18, decimal_places=2, default=Decimal("0")
    )
    source = models.CharField(
        _("source"), max_length=8, choices=TaxLineSource.choices, default=TaxLineSource.DOCUMENT
    )
    overridden = models.BooleanField(_("code changed from the default"), default=False)
    restricted = models.BooleanField(_("restricted ITC/ITR"), default=False)
    late = models.BooleanField(_("late adjustment"), default=False)
    reverses = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("reverses"),
    )

    class Meta:
        ordering = ("date", "entry_id", "line_no", "pk")
        verbose_name = _("posted tax line")
        verbose_name_plural = _("posted tax lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(side__in=TaxSide.values), name="tax_taxline_side_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=TaxLineSource.values),
                name="tax_taxline_source_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "date"), name="tax_taxline_date_idx"),
            models.Index(fields=("organisation", "entry"), name="tax_taxline_entry_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.date:%Y-%m-%d} {self.code} {self.component} {self.tax}"
