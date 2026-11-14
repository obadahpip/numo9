"""Organisation settings (A-05).

``OrganisationSettings`` (A-05-T01) is the one settings row of an organisation: who it is (legal
and display name, industry, business structure), where it is (a Canadian mailing address and an
optional separate physical address — Province and Postal code, never "State" and "ZIP", gap-39),
how to reach it (phone, email, website), its fiscal year end, its base currency (CAD, locked), its
time zone and default time format, and the default payment terms of sales and purchases.

It is an organisation record (``OrgOwnedModel``: scoped to the active organisation, public UUID,
soft delete) with every change in the audit log (``AuditedModel``, A-04), so a change made by a
background job reads ``System: <job>`` (gap-44). There is exactly one row per organisation
(database constraint); ``numo9.orgsettings.service.get_settings()`` reads it, creating it from the
organisation on first use.

``display_name`` and ``time_zone`` are mirrored onto ``tenancy.Organisation`` (``name``,
``time_zone``) in the same transaction: the organisation directory, the org switcher, the audit log
and the job scheduler read the organisation, and the settings page is the one place to change them.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from numo9.accounts.models import TimeFormat
from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import DEFAULT_TIME_ZONE, OrgOwnedModel, validate_time_zone

from .validators import (
    PROGRAM_TYPES,
    display_registration_number,
    normalise_phone,
    normalise_postal_code,
    normalise_registration_number,
    validate_legal_name,
    validate_postal_code,
    validate_postal_code_province,
    validate_province,
)

#: Base currency of every Numo9 organisation (multi-currency adds foreign currencies, not a base).
BASE_CURRENCY = "CAD"
#: Default country of an address (ISO 3166-1 alpha-2).
CANADA = "CA"
#: Longest payment term, in days.
MAX_TERM_DAYS = 365


class BusinessStructure(models.TextChoices):
    SOLE_PROPRIETORSHIP = "sole_proprietorship", _("Sole proprietorship")
    PARTNERSHIP = "partnership", _("Partnership")
    CORPORATION = "corporation", _("Corporation")
    NON_PROFIT = "non_profit", _("Non-profit organisation")
    CHARITY = "charity", _("Registered charity")
    COOPERATIVE = "cooperative", _("Co-operative")
    TRUST = "trust", _("Trust")
    OTHER = "other", _("Other")


class TermsType(models.TextChoices):
    """How a default due date is worked out (Xero teardown §3.2: "n of the following month" …)."""

    DAYS_AFTER_DOCUMENT = "days_after_document", _("days after the document date")
    DAYS_AFTER_MONTH_END = "days_after_month_end", _("days after the end of the document month")
    DAY_OF_FOLLOWING_MONTH = "day_of_following_month", _("of the following month")
    DAY_OF_CURRENT_MONTH = "day_of_current_month", _("of the current month")


#: Terms that name a day of a month (1–31) rather than a number of days (0–365).
DAY_OF_MONTH_TERMS: frozenset[str] = frozenset(
    {TermsType.DAY_OF_FOLLOWING_MONTH, TermsType.DAY_OF_CURRENT_MONTH}
)

#: Last day of each month; 29 February means the last day of February (leap years or not).
MONTH_DAYS: dict[int, int] = {
    1: 31,
    2: 29,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}

#: Address parts, stored once per address kind as ``<kind>_<part>``.
ADDRESS_PARTS: tuple[str, ...] = (
    "attention",
    "line1",
    "line2",
    "city",
    "province",
    "postal_code",
    "country",
)
ADDRESS_KINDS: tuple[str, ...] = ("mailing", "physical")


def _in(field: str, choices: type[models.TextChoices]) -> models.Q:
    return models.Q(**{f"{field}__in": choices.values})


class OrganisationSettings(AuditedModel, OrgOwnedModel):
    # ---- who -----------------------------------------------------------------------------
    legal_name = models.CharField(
        _("legal name"),
        max_length=200,
        blank=True,
        validators=[validate_legal_name],
        help_text=_("As registered; printed on statements, invoices and tax forms."),
    )
    display_name = models.CharField(
        _("display name"), max_length=200, help_text=_("The name people see in Numo9.")
    )
    industry = models.CharField(_("industry"), max_length=100, blank=True)
    structure = models.CharField(
        _("business structure"),
        max_length=32,
        choices=BusinessStructure.choices,
        default=BusinessStructure.CORPORATION,
    )

    # ---- where: mailing_<part> and physical_<part> for each part of ADDRESS_PARTS ---------
    mailing_attention = models.CharField(_("attention"), max_length=100, blank=True)
    mailing_line1 = models.CharField(_("street address or PO box"), max_length=200, blank=True)
    mailing_line2 = models.CharField(_("address line 2"), max_length=200, blank=True)
    mailing_city = models.CharField(_("city"), max_length=100, blank=True)
    mailing_province = models.CharField(
        _("province or territory"),
        max_length=50,
        blank=True,
        help_text=_("Two-letter code (ON, QC…) for a Canadian address."),
    )
    mailing_postal_code = models.CharField(_("postal code"), max_length=16, blank=True)
    mailing_country = models.CharField(
        _("country"),
        max_length=2,
        default=CANADA,
        help_text=_("ISO 3166-1 two-letter code; CA for Canada."),
    )
    physical_same_as_mailing = models.BooleanField(
        _("physical address same as mailing address"), default=True
    )
    physical_attention = models.CharField(_("attention"), max_length=100, blank=True)
    physical_line1 = models.CharField(_("street address or PO box"), max_length=200, blank=True)
    physical_line2 = models.CharField(_("address line 2"), max_length=200, blank=True)
    physical_city = models.CharField(_("city"), max_length=100, blank=True)
    physical_province = models.CharField(
        _("province or territory"),
        max_length=50,
        blank=True,
        help_text=_("Two-letter code (ON, QC…) for a Canadian address."),
    )
    physical_postal_code = models.CharField(_("postal code"), max_length=16, blank=True)
    physical_country = models.CharField(
        _("country"),
        max_length=2,
        default=CANADA,
        help_text=_("ISO 3166-1 two-letter code; CA for Canada."),
    )

    # ---- contact -------------------------------------------------------------------------
    phone = models.CharField(_("telephone"), max_length=32, blank=True)
    email = models.EmailField(_("email address"), max_length=254, blank=True)
    website = models.URLField(_("website"), max_length=200, blank=True)

    # ---- accounting ----------------------------------------------------------------------
    fye_month = models.PositiveSmallIntegerField(
        _("fiscal year end month"),
        default=12,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    fye_day = models.PositiveSmallIntegerField(
        _("fiscal year end day"),
        default=31,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    base_currency = models.CharField(
        _("base currency"), max_length=3, default=BASE_CURRENCY, editable=False
    )
    time_zone = models.CharField(
        _("time zone"), max_length=64, default=DEFAULT_TIME_ZONE, validators=[validate_time_zone]
    )
    time_format = models.CharField(
        _("time format"),
        max_length=3,
        choices=TimeFormat.choices,
        default=TimeFormat.H12,
        help_text=_(
            "Times on the organisation's documents and emails; each person sees their own "
            "preference in the app."
        ),
    )

    # ---- default payment terms -------------------------------------------------------------
    sales_terms_type = models.CharField(
        _("sales: default due date"),
        max_length=32,
        choices=TermsType.choices,
        default=TermsType.DAYS_AFTER_DOCUMENT,
    )
    sales_terms_days = models.PositiveSmallIntegerField(
        _("sales: days or day"), default=30, validators=[MaxValueValidator(MAX_TERM_DAYS)]
    )
    purchase_terms_type = models.CharField(
        _("purchases: default due date"),
        max_length=32,
        choices=TermsType.choices,
        default=TermsType.DAYS_AFTER_DOCUMENT,
    )
    purchase_terms_days = models.PositiveSmallIntegerField(
        _("purchases: days or day"), default=30, validators=[MaxValueValidator(MAX_TERM_DAYS)]
    )

    class Meta:
        verbose_name = _("organisation settings")
        verbose_name_plural = _("organisation settings")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["organisation"], name="orgsettings_one_per_org"),
            models.CheckConstraint(
                condition=models.Q(base_currency=BASE_CURRENCY),
                name="orgsettings_base_currency_cad",
            ),
            models.CheckConstraint(
                condition=models.Q(fye_month__gte=1, fye_month__lte=12),
                name="orgsettings_fye_month_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(fye_day__gte=1, fye_day__lte=31),
                name="orgsettings_fye_day_valid",
            ),
            models.CheckConstraint(
                condition=_in("structure", BusinessStructure), name="orgsettings_structure_valid"
            ),
            models.CheckConstraint(
                condition=_in("time_format", TimeFormat), name="orgsettings_time_format_valid"
            ),
            models.CheckConstraint(
                condition=_in("sales_terms_type", TermsType)
                & _in("purchase_terms_type", TermsType),
                name="orgsettings_terms_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(sales_terms_days__lte=MAX_TERM_DAYS)
                & models.Q(purchase_terms_days__lte=MAX_TERM_DAYS),
                name="orgsettings_terms_days_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.display_name

    def audit_label(self) -> str:
        return self.display_name or self.legal_name

    # ---- derived -------------------------------------------------------------------------

    @property
    def printed_name(self) -> str:
        """The name on statements and tax forms: the legal name, else the display name."""
        return self.legal_name or self.display_name

    def address(self, kind: str) -> dict[str, str]:
        """One address as ``{part: value}``; the physical one follows the mailing one when
        ``physical_same_as_mailing``."""
        if kind not in ADDRESS_KINDS:
            raise ValueError(f"Unknown address kind {kind!r}.")
        source = "mailing" if kind == "physical" and self.physical_same_as_mailing else kind
        return {part: str(getattr(self, f"{source}_{part}")) for part in ADDRESS_PARTS}

    # ---- validation and save -------------------------------------------------------------

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}
        if self.fye_month in MONTH_DAYS and not 1 <= self.fye_day <= MONTH_DAYS[self.fye_month]:
            errors.setdefault("fye_day", []).append(
                ValidationError(
                    _("That month has no day %(day)d."),
                    code="orgsettings.fye_day_invalid",
                    params={"day": self.fye_day},
                )
            )
        for prefix in ("sales", "purchase"):
            kind = getattr(self, f"{prefix}_terms_type")
            days = getattr(self, f"{prefix}_terms_days")
            if kind in DAY_OF_MONTH_TERMS and not 1 <= days <= 31:
                errors.setdefault(f"{prefix}_terms_days", []).append(
                    ValidationError(
                        _("Choose a day of the month from 1 to 31."),
                        code="orgsettings.terms_day_invalid",
                    )
                )
        for kind in ADDRESS_KINDS:
            if kind == "physical" and self.physical_same_as_mailing:
                continue
            self._clean_address(kind, errors)
        if self.phone:
            try:
                self.phone = normalise_phone(self.phone)
            except ValidationError as error:
                errors.setdefault("phone", []).append(error)
        if errors:
            raise ValidationError(errors)

    def _clean_address(self, kind: str, errors: dict[str, list[ValidationError]]) -> None:
        """Canadian addresses: a known province, a ``A1A 1A1`` postal code in that province."""
        country = getattr(self, f"{kind}_country")
        if not re.fullmatch(r"[A-Z]{2}", country):
            errors.setdefault(f"{kind}_country", []).append(
                ValidationError(
                    _("Use the two-letter country code, e.g. CA."),
                    code="orgsettings.country.invalid",
                )
            )
            return
        if country != CANADA:
            return
        province = getattr(self, f"{kind}_province")
        postal_code = getattr(self, f"{kind}_postal_code")
        checks = (
            (f"{kind}_province", validate_province, (province,)),
            (f"{kind}_postal_code", validate_postal_code, (postal_code,)),
        )
        failed = False
        for field, check, args in checks:
            try:
                check(*args)
            except ValidationError as error:
                errors.setdefault(field, []).append(error)
                failed = True
        if not failed:
            try:
                validate_postal_code_province(postal_code, province)
            except ValidationError as error:
                errors.setdefault(f"{kind}_postal_code", []).append(error)

    def normalise(self) -> None:
        """Tidy user input before validation (surrounding spaces, the locked currency)."""
        for name in ("legal_name", "display_name", "industry", "email", "website", "phone"):
            setattr(self, name, (getattr(self, name) or "").strip())
        for kind in ADDRESS_KINDS:
            for part in ADDRESS_PARTS:
                name = f"{kind}_{part}"
                setattr(self, name, (getattr(self, name) or "").strip())
            country = getattr(self, f"{kind}_country").upper() or CANADA
            setattr(self, f"{kind}_country", country)
            if country == CANADA:
                province = getattr(self, f"{kind}_province").upper()
                setattr(self, f"{kind}_province", province)
                postal = normalise_postal_code(getattr(self, f"{kind}_postal_code"))
                setattr(self, f"{kind}_postal_code", postal)
        self.base_currency = BASE_CURRENCY

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.normalise()
        self.validate(update_fields=kwargs.get("update_fields"))
        with transaction.atomic():
            super().save(*args, **kwargs)
            self._mirror_to_organisation()

    def validate(self, update_fields: Any = None) -> None:
        """Field and cross-field rules; every problem is reported at once (one form, one pass)."""
        errors: dict[str, Any] = {}
        try:
            self.clean_fields(exclude=self._clean_exclude(update_fields))
        except ValidationError as error:
            errors = error.update_error_dict(errors)
        try:
            self.clean()
        except ValidationError as error:
            errors = error.update_error_dict(errors)
        if errors:
            raise ValidationError(errors)

    def _clean_exclude(self, update_fields: Any) -> list[str]:
        # Relations and bookkeeping are set by the platform, not validated as user input.
        exclude = ["organisation", "created_by", "public_id"]
        if update_fields is not None:
            names = {self._meta.get_field(n).name for n in update_fields}
            exclude += [f.name for f in self._meta.concrete_fields if f.name not in names]
        return exclude

    def _mirror_to_organisation(self) -> None:
        organisation = self.organisation
        changed = []
        if self.display_name and organisation.name != self.display_name:
            organisation.name = self.display_name
            changed.append("name")
        if organisation.time_zone != self.time_zone:
            organisation.time_zone = self.time_zone
            changed.append("time_zone")
        if changed:
            organisation.save(update_fields=[*changed, "updated_at"])


# ---- tax registrations (A-05-T03) ------------------------------------------------------------


class RegistrationType(models.TextChoices):
    """The statutory numbers on the one Tax Registrations page (gap-39)."""

    BN = "bn", _("Business Number (BN)")
    RT = "rt", _("GST/HST program account (RT)")
    RP = "rp", _("Payroll program account (RP)")
    RC = "rc", _("Corporate income tax program account (RC)")
    QST = "qst", _("Quebec QST number")
    PST_BC = "pst_bc", _("British Columbia PST number")
    PST_SK = "pst_sk", _("Saskatchewan PST number")
    RST_MB = "rst_mb", _("Manitoba RST number")


class RegistrationStatus(models.TextChoices):
    PENDING = "pending", _("Applied for")
    ACTIVE = "active", _("Registered")
    CLOSED = "closed", _("Closed")


def _periods_overlap(a: TaxRegistration, b: TaxRegistration) -> bool:
    """Effective periods overlap (an empty start or end is open-ended)."""
    a_starts_before_b_ends = (
        b.effective_to is None or a.effective_from is None or (a.effective_from <= b.effective_to)
    )
    b_starts_before_a_ends = (
        a.effective_to is None or b.effective_from is None or (b.effective_from <= a.effective_to)
    )
    return a_starts_before_b_ends and b_starts_before_a_ends


class TaxRegistration(AuditedModel, OrgOwnedModel):
    """One statutory registration of the organisation (A-05-T03): its Business Number, a CRA
    program account (RT GST/HST, RP payroll, RC corporate income tax), its Quebec QST number or a
    provincial sales tax number (BC PST, Saskatchewan PST, Manitoba RST).

    ``number`` is stored in a canonical form (``123456782RT0001``) and checked for its type —
    [EXTRA] including the Business Number's check digit, on its own and inside every program
    account; a program account must carry the organisation's BN when one is registered for the
    same dates (and a BN must match the program accounts already there). Periods of the same
    registration (the BN, or the same number) may not overlap. Every change — a
    status change above all — is in the audit log with its author (gap-44).
    """

    type = models.CharField(_("type"), max_length=16, choices=RegistrationType.choices)
    number = models.CharField(_("number"), max_length=20)
    effective_from = models.DateField(_("effective from"), null=True, blank=True)
    effective_to = models.DateField(_("effective to"), null=True, blank=True)
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.ACTIVE,
    )
    cra_approval_ref = models.CharField(
        _("CRA approval reference"),
        max_length=100,
        blank=True,
        help_text=_("Reference of the CRA or Revenu Québec letter approving the registration."),
    )

    class Meta:
        ordering = ("type", "number", "effective_from")
        verbose_name = _("tax registration")
        verbose_name_plural = _("tax registrations")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=_in("type", RegistrationType), name="orgsettings_registration_type_valid"
            ),
            models.CheckConstraint(
                condition=_in("status", RegistrationStatus),
                name="orgsettings_registration_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_from__isnull=True)
                | models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="orgsettings_registration_period_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "type"), name="orgsettings_reg_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.display_number}"

    def audit_label(self) -> str:
        return str(self)

    @property
    def display_number(self) -> str:
        return display_registration_number(self.type, self.number)

    @property
    def business_number(self) -> str:
        """The BN the registration belongs to (empty for QST and provincial numbers)."""
        if self.type == RegistrationType.BN or self.type in PROGRAM_TYPES:
            return self.number[:9]
        return ""

    # ---- validation and save -------------------------------------------------------------

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}
        if self.type in RegistrationType.values:
            try:
                self.number = normalise_registration_number(self.type, self.number)
            except ValidationError as error:
                errors.setdefault("number", []).append(error)
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            errors.setdefault("effective_to", []).append(
                ValidationError(
                    _("The end date is before the start date."),
                    code="orgsettings.registration.period_invalid",
                )
            )
        if not errors:
            self._check_against_others(errors)
        if errors:
            raise ValidationError(errors)

    def _others(self) -> models.QuerySet[TaxRegistration]:
        return (
            TaxRegistration._base_manager.filter(
                organisation_id=self.organisation_id, deleted_at__isnull=True
            )
            .exclude(pk=self.pk)
            .order_by("effective_from")
        )

    def _check_against_others(self, errors: dict[str, list[ValidationError]]) -> None:
        others = list(self._others())
        if self.deleted_at is None:
            same = [
                other
                for other in others
                if other.type == self.type
                and (self.type == RegistrationType.BN or other.number == self.number)
                and _periods_overlap(self, other)
            ]
            if same:
                errors.setdefault("effective_from", []).append(
                    ValidationError(
                        _(
                            "%(registration)s is already registered for these dates: end it "
                            "before adding another."
                        ),
                        code="orgsettings.registration.overlap",
                        params={"registration": str(same[0])},
                    )
                )
        if self.type == RegistrationType.BN:
            foreign = [
                o
                for o in others
                if o.type in PROGRAM_TYPES
                and o.business_number != self.number
                and _periods_overlap(self, o)
            ]
            if foreign:
                errors.setdefault("number", []).append(
                    ValidationError(
                        _(
                            "%(registration)s carries Business Number %(bn)s: the organisation's "
                            "BN and its program accounts must match."
                        ),
                        code="orgsettings.registration.bn_mismatch",
                        params={"registration": str(foreign[0]), "bn": foreign[0].business_number},
                    )
                )
        if self.type in PROGRAM_TYPES:
            bns = {
                o.number
                for o in others
                if o.type == RegistrationType.BN and _periods_overlap(self, o)
            }
            if bns and self.business_number not in bns:
                errors.setdefault("number", []).append(
                    ValidationError(
                        _(
                            "This program account belongs to BN %(bn)s, not to the "
                            "organisation's Business Number %(registered)s."
                        ),
                        code="orgsettings.registration.bn_mismatch",
                        params={"bn": self.business_number, "registered": ", ".join(sorted(bns))},
                    )
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.cra_approval_ref = (self.cra_approval_ref or "").strip()
        errors: dict[str, Any] = {}
        try:
            self.clean_fields(exclude=["organisation", "created_by", "public_id"])
        except ValidationError as error:
            errors = error.update_error_dict(errors)
        if not errors:
            try:
                self.clean()
            except ValidationError as error:
                errors = error.update_error_dict(errors)
        if errors:
            raise ValidationError(errors)
        super().save(*args, **kwargs)
