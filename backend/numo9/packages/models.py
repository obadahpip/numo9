"""Packages (U-02): what organisations subscribe to, built from whole catalogue products.

``Package`` — a bundle the Platform Owner sells ("Starter", "Growth", "Complete": names, product
mixes and prices are client data, never code):

- ``code`` — stable identifier (``growth``), unique, never changes: prices, Stripe products and
  subscriptions refer to it;
- ``name_i18n`` / ``description_i18n`` — the client's texts per language
  (``{"en-CA": "Growth", "fr-CA": "Croissance"}``); English is required, French falls back to
  English until it is entered (Phase 6);
- ``status`` — ``draft`` (being built, never offered) → ``active`` (offered at sign-up) →
  ``retired`` (hidden from sign-up; subscribers keep it). A package with no product can't be
  activated;
- ``is_founding_eligible`` — the founding-1,000 offer (U-08) applies to it;
- ``limits`` — per-package limits, ``{"max_org_users": 10}`` (``null`` or missing = unlimited).
  Practice users (accountants) are never counted.

``PackageProduct`` — the products in a package (the plan's ``Package.products`` M2M, with its
own row so every change is audited). Only billable products that are active can be added:
free sets (Practice, Client portal) are part of every package and never chosen; planned
companion apps can't be sold yet. An active package always keeps at least one product.

``PackagePrice`` — effective-dated price versions per billing interval (see its docstring).

``PromoCode`` — discounts entered at checkout, with a redemption counter; ``PromoRedemption`` —
an organisation's use of one (an organisation record).

Platform records (tenancy allow-list): no organisation's data. Every change writes its field
diff to the platform audit log (``PlatformAudited``, A-04).
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, ClassVar

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.catalogue.models import PlatformAudited, Product, ProductKind, ProductStatus
from numo9.tenancy.models import OrgOwnedModel

#: Lower-case letter first, then letters, digits and _ (2–40 characters).
PACKAGE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
#: Languages of the client's package texts; English is required.
LOCALES: tuple[str, ...] = ("en-CA", "fr-CA")
DEFAULT_LOCALE = "en-CA"
NAME_MAX = 60
DESCRIPTION_MAX = 300
#: Known per-package limits: value a positive whole number, or null = unlimited.
LIMIT_KEYS: frozenset[str] = frozenset({"max_org_users"})
LIMIT_MAX = 100_000


class PackageError(ValidationError):
    """A package change the rules refuse (activating without products, changing a code…)."""


class PackageStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    ACTIVE = "active", _("Active")
    RETIRED = "retired", _("Retired")


def localised(texts: dict[str, str] | None, locale: str, fallback: str = "") -> str:
    """The text for ``locale`` (``fr``/``fr-CA``…), else English, else ``fallback``."""
    texts = texts or {}
    wanted = "fr-CA" if locale.lower().startswith("fr") else DEFAULT_LOCALE
    return texts.get(wanted) or texts.get(DEFAULT_LOCALE) or fallback


def _texts_error(field: str, message: Any, code: str) -> PackageError:
    return PackageError({field: ValidationError(message, code=code)})


def validate_texts(field: str, value: Any, *, required: bool, max_length: int) -> None:
    if not isinstance(value, dict) or any(not isinstance(v, str) for v in value.values()):
        raise _texts_error(field, _("Enter the text for each language."), "packages.texts_invalid")
    unknown = set(value) - set(LOCALES)
    if unknown:
        raise _texts_error(
            field, _("Only English (en-CA) and French (fr-CA) are supported."), "packages.locale"
        )
    if required and not value.get(DEFAULT_LOCALE, "").strip():
        raise _texts_error(field, _("Enter the English text."), "packages.english_required")
    if any(len(v) > max_length for v in value.values()):
        raise _texts_error(
            field,
            _("Use at most %(max)s characters.") % {"max": max_length},
            "packages.text_too_long",
        )


def validate_limits(value: Any) -> None:
    if not isinstance(value, dict):
        raise _texts_error("limits", _("Limits must be a list of named values."), "packages.limits")
    unknown = set(value) - LIMIT_KEYS
    if unknown:
        raise _texts_error(
            "limits",
            _("Unknown limit: %(names)s.") % {"names": ", ".join(sorted(unknown))},
            "packages.unknown_limit",
        )
    for amount in value.values():
        if amount is None:
            continue
        if isinstance(amount, bool) or not isinstance(amount, int) or not 1 <= amount <= LIMIT_MAX:
            raise _texts_error(
                "limits",
                _("Enter a whole number from 1 to %(max)s, or leave it unlimited.")
                % {"max": f"{LIMIT_MAX:,}"},
                "packages.limit_value",
            )


class PackageQuerySet(models.QuerySet["Package"]):
    def offered(self) -> PackageQuerySet:
        """Packages offered at sign-up and on the pricing page: active ones only."""
        return self.filter(status=PackageStatus.ACTIVE)


class Package(PlatformAudited, models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(
        _("code"),
        max_length=40,
        unique=True,
        help_text=_("Stable identifier, e.g. 'growth'. Never changes once created."),
    )
    name_i18n = models.JSONField(
        _("name"), default=dict, help_text=_("Name per language: {'en-CA': …, 'fr-CA': …}.")
    )
    description_i18n = models.JSONField(
        _("description"), default=dict, blank=True, help_text=_("Description per language.")
    )
    status = models.CharField(
        _("status"), max_length=16, choices=PackageStatus.choices, default=PackageStatus.DRAFT
    )
    is_founding_eligible = models.BooleanField(
        _("founding offer"),
        default=False,
        help_text=_("The founding-1,000 offer applies to organisations on this package (U-08)."),
    )
    limits = models.JSONField(
        _("limits"),
        default=dict,
        blank=True,
        help_text=_(
            "{'max_org_users': 10}; null or missing = unlimited. Practice users never count."
        ),
    )
    sort = models.PositiveIntegerField(_("sort order"), default=0)
    stripe_product_id = models.CharField(
        _("Stripe product"),
        max_length=100,
        blank=True,
        editable=False,
        help_text=_("Set by the Stripe sync job (U-02-T12)."),
    )
    products = models.ManyToManyField(
        Product, through="PackageProduct", related_name="packages", verbose_name=_("products")
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects: ClassVar[models.Manager[Package]] = PackageQuerySet.as_manager()

    class Meta:
        ordering = ("sort", "code")
        verbose_name = _("package")
        verbose_name_plural = _("packages")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=PackageStatus.values), name="packages_package_status"
            ),
        ]

    def __str__(self) -> str:
        return self.code

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        if not self._state.adding:
            stored = type(self)._base_manager.filter(pk=self.pk).values_list("code", flat=True)
            if stored and stored[0] != self.code:
                message = _("A package's code never changes: prices and subscriptions use it.")
                raise _texts_error("code", message, "packages.code_immutable")
        if self.status == PackageStatus.ACTIVE and not self.has_products():
            raise PackageError(
                _("Add at least one product before activating this package."),
                code="packages.no_products",
            )
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        from .subscriptions import get_source  # the source may import this module

        if get_source().count(self):
            raise PackageError(
                _("A package with subscribers is never deleted: retire it instead."),
                code="packages.in_use",
            )
        return super().delete(*args, **kwargs)

    def name(self, locale: str = DEFAULT_LOCALE) -> str:
        return localised(self.name_i18n, locale, self.code)

    def description(self, locale: str = DEFAULT_LOCALE) -> str:
        return localised(self.description_i18n, locale)

    def has_products(self) -> bool:
        return not self._state.adding and self.package_products.exists()

    def clean(self) -> None:
        if not PACKAGE_CODE.match(self.code or ""):
            raise _texts_error(
                "code",
                _("Use 2–40 lower-case letters, digits and _, starting with a letter."),
                "packages.bad_code",
            )
        validate_texts("name_i18n", self.name_i18n, required=True, max_length=NAME_MAX)
        validate_texts(
            "description_i18n", self.description_i18n, required=False, max_length=DESCRIPTION_MAX
        )
        validate_limits(self.limits)

    def limit(self, key: str) -> int | None:
        """A limit's value; None = unlimited."""
        value = (self.limits or {}).get(key)
        return value if isinstance(value, int) else None


class PackageProduct(PlatformAudited, models.Model):
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name="package_products",
        verbose_name=_("package"),
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="package_links", verbose_name=_("product")
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ("product__sort", "product__code")
        verbose_name = _("product in a package")
        verbose_name_plural = _("products in packages")
        constraints = [
            models.UniqueConstraint(
                fields=("package", "product"), name="packages_packageproduct_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.package.code}: {self.product.code}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding:
            self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        product = self.product
        if product.kind == ProductKind.FREE_SET:
            raise _texts_error(
                "product",
                _("%(product)s is free and part of every package: it isn't added to one.")
                % {"product": product.code},
                "packages.free_product",
            )
        if product.status != ProductStatus.ACTIVE:
            raise _texts_error(
                "product",
                _("%(product)s isn't active yet, so it can't be put in a package.")
                % {"product": product.code},
                "packages.product_not_active",
            )

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        package = Package.objects.get(pk=self.package_id)
        if (
            package.status == PackageStatus.ACTIVE
            and package.package_products.exclude(pk=self.pk).count() == 0
        ):
            raise PackageError(
                _("An active package keeps at least one product. Add another product first."),
                code="packages.last_product",
            )
        return super().delete(*args, **kwargs)


# ---- prices (U-02-T03) ------------------------------------------------------------------------


class BillingInterval(models.TextChoices):
    MONTH = "month", _("Monthly")
    YEAR = "year", _("Annual")


class TaxBehaviour(models.TextChoices):
    #: GST/HST is added on top of the price (computed by the tax engine, Phase 1).
    EXCLUSIVE = "exclusive", _("Before tax")


CURRENCY = "CAD"


class DateRange(models.Func):
    """``daterange(from, to, '[)')`` — a price version's days; a null end is open."""

    function = "DATERANGE"
    output_field = DateRangeField()


class PackagePrice(PlatformAudited, models.Model):
    """One version of a package's price for one billing interval.

    A version is in force from ``effective_from`` (inclusive) until ``effective_to``
    (exclusive; null = open). Versions of the same package and interval never overlap — the
    database refuses it (``packages_price_no_overlap``, a btree_gist exclusion constraint), so
    on any day there is at most one price. Amounts are whole cents in CAD, before GST/HST
    (``tax_behaviour = exclusive``).

    A version is never edited: Stripe prices are immutable (U-02-T12), so a price change is a
    new version and the previous one gets its ``effective_to``. Only ``effective_to`` and, once,
    the Stripe price id may change on a stored row.
    """

    #: Fixed at creation. ``effective_to`` may be set later; ``stripe_price_id`` once (from blank).
    IMMUTABLE: ClassVar[tuple[str, ...]] = (
        "package_id",
        "interval",
        "amount_cents",
        "currency",
        "tax_behaviour",
        "effective_from",
    )

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    package = models.ForeignKey(
        Package, on_delete=models.CASCADE, related_name="prices", verbose_name=_("package")
    )
    interval = models.CharField(
        _("billing interval"), max_length=8, choices=BillingInterval.choices
    )
    amount_cents = models.PositiveIntegerField(
        _("amount (cents)"), help_text=_("Whole cents in CAD, before GST/HST.")
    )
    currency = models.CharField(_("currency"), max_length=3, default=CURRENCY)
    tax_behaviour = models.CharField(
        _("tax behaviour"),
        max_length=16,
        choices=TaxBehaviour.choices,
        default=TaxBehaviour.EXCLUSIVE,
    )
    effective_from = models.DateField(_("effective from"))
    effective_to = models.DateField(
        _("effective to"),
        null=True,
        blank=True,
        help_text=_("First day this version no longer applies; empty = no end date."),
    )
    stripe_price_id = models.CharField(
        _("Stripe price"),
        max_length=100,
        blank=True,
        editable=False,
        help_text=_("Set once by the Stripe sync job (U-02-T12); never changed afterwards."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        ordering = ("package", "interval", "effective_from")
        verbose_name = _("package price")
        verbose_name_plural = _("package prices")
        indexes = [
            models.Index(
                fields=("package", "interval", "effective_from"),
                name="packages_price_lookup",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(currency=CURRENCY), name="packages_price_currency_cad"
            ),
            models.CheckConstraint(
                condition=models.Q(interval__in=BillingInterval.values),
                name="packages_price_interval",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_behaviour__in=TaxBehaviour.values),
                name="packages_price_tax_behaviour",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="packages_price_window",
            ),
            # PostgreSQL only (btree_gist): added by PostgresOnlyAddConstraint in migration 0002.
            ExclusionConstraint(
                name="packages_price_no_overlap",
                index_type="GIST",
                expressions=[
                    ("package", RangeOperators.EQUAL),
                    ("interval", RangeOperators.EQUAL),
                    (
                        DateRange("effective_from", "effective_to", models.Value("[)")),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                violation_error_code="packages.price_overlap",
                violation_error_message=_(
                    "Another price is already in force on some of these days for this package "
                    "and billing interval."
                ),
            ),
        ]

    def __str__(self) -> str:
        end = self.effective_to.isoformat() if self.effective_to else "…"
        return (
            f"{self.package.code} {self.interval} {self.amount_cents / 100:.2f} {self.currency} "
            f"[{self.effective_from.isoformat()}, {end})"
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        if not self._state.adding:
            stored = (
                type(self)
                ._base_manager.filter(pk=self.pk)
                .values(*self.IMMUTABLE, "stripe_price_id")
                .first()
            )
            if stored and any(stored[f] != getattr(self, f) for f in self.IMMUTABLE):
                raise PackageError(
                    _(
                        "A price version never changes: schedule a new price instead "
                        "(Stripe prices can't be edited)."
                    ),
                    code="packages.price_immutable",
                )
            if stored and stored["stripe_price_id"] not in ("", self.stripe_price_id):
                raise PackageError(
                    _("A price's Stripe price never changes once it is set."),
                    code="packages.stripe_price_immutable",
                )
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.currency != CURRENCY:
            raise _texts_error(
                "currency",
                _("Prices are in Canadian dollars (CAD)."),
                "packages.currency_cad",
            )
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise _texts_error(
                "effective_to",
                _("The end date must be after the start date."),
                "packages.price_window",
            )

    def covers(self, day: date) -> bool:
        """Whether this version is in force on ``day``."""
        return self.effective_from <= day and (self.effective_to is None or day < self.effective_to)


# ---- promo codes (U-02-T06) -------------------------------------------------------------------

#: Stored upper-case: letters, digits, - and _ (3–40); entered case-insensitively.
PROMO_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")
PROMO_MONTHS_MAX = 36


def normalise_promo_code(code: str) -> str:
    return (code or "").strip().upper()


class PromoKind(models.TextChoices):
    PERCENT = "percent", _("Percent off")
    FIXED = "fixed", _("Fixed amount off")


class PromoDuration(models.TextChoices):
    ONCE = "once", _("Once")
    REPEATING = "repeating", _("Number of months")
    FOREVER = "forever", _("Forever")


class PromoStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    USED_UP = "used_up", _("Used up")
    EXPIRED = "expired", _("Expired")


class PromoCode(PlatformAudited, models.Model):
    """A discount organisations enter at checkout (U-04).

    Percent (1–100) or a fixed amount in CAD cents; applied once, for a number of months or
    forever; optionally limited to ``max_redemptions`` uses, an expiry moment and some packages
    (none = every package). ``redemptions_count`` is the redemption counter: ``redeem()``
    (``promos.py``) increments it under a row lock, and the database refuses a count above the
    maximum — so the last redemption can't be taken twice.
    """

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(
        _("code"),
        max_length=40,
        unique=True,
        help_text=_("Stored upper-case; organisations may type it in any case."),
    )
    description = models.CharField(_("description"), max_length=200, blank=True)
    kind = models.CharField(_("discount"), max_length=8, choices=PromoKind.choices)
    percent_off = models.PositiveSmallIntegerField(_("percent off"), null=True, blank=True)
    amount_off_cents = models.PositiveIntegerField(_("amount off (cents)"), null=True, blank=True)
    currency = models.CharField(_("currency"), max_length=3, default=CURRENCY)
    duration = models.CharField(_("duration"), max_length=10, choices=PromoDuration.choices)
    duration_months = models.PositiveSmallIntegerField(_("months"), null=True, blank=True)
    max_redemptions = models.PositiveIntegerField(
        _("maximum uses"), null=True, blank=True, help_text=_("Empty = no limit.")
    )
    redemptions_count = models.PositiveIntegerField(_("uses"), default=0, editable=False)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    packages = models.ManyToManyField(
        Package,
        blank=True,
        related_name="promo_codes",
        verbose_name=_("packages"),
        help_text=_("The packages the code applies to; none = every package."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    #: The counter moves with every redemption; redemptions are recorded on their own.
    audit_exclude: ClassVar[frozenset[str]] = frozenset({"redemptions_count"})

    class Meta:
        ordering = ("-created_at", "code")
        verbose_name = _("promo code")
        verbose_name_plural = _("promo codes")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=PromoKind.values), name="packages_promo_kind"
            ),
            models.CheckConstraint(
                condition=models.Q(duration__in=PromoDuration.values),
                name="packages_promo_duration",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind=PromoKind.PERCENT,
                    percent_off__gte=1,
                    percent_off__lte=100,
                    amount_off_cents__isnull=True,
                )
                | models.Q(kind=PromoKind.FIXED, amount_off_cents__gte=1, percent_off__isnull=True),
                name="packages_promo_discount",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    duration=PromoDuration.REPEATING,
                    duration_months__gte=1,
                    duration_months__lte=PROMO_MONTHS_MAX,
                )
                | (
                    ~models.Q(duration=PromoDuration.REPEATING)
                    & models.Q(duration_months__isnull=True)
                ),
                name="packages_promo_months",
            ),
            models.CheckConstraint(
                condition=models.Q(max_redemptions__isnull=True)
                | models.Q(
                    max_redemptions__gte=1, redemptions_count__lte=models.F("max_redemptions")
                ),
                name="packages_promo_max_redemptions",
            ),
            models.CheckConstraint(
                condition=models.Q(currency=CURRENCY), name="packages_promo_currency_cad"
            ),
        ]

    def __str__(self) -> str:
        return self.code

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.code = normalise_promo_code(self.code)
        self.clean()
        if not self._state.adding:
            stored = type(self)._base_manager.filter(pk=self.pk).values_list("code", flat=True)
            if stored and stored[0] != self.code:
                raise _texts_error(
                    "code",
                    _("A promo code never changes: create a new code instead."),
                    "packages.promo_code_immutable",
                )
        super().save(*args, **kwargs)

    def clean(self) -> None:
        errors: dict[str, ValidationError] = {}
        if not PROMO_CODE.match(self.code or ""):
            errors["code"] = ValidationError(
                _("Use 3–40 letters, digits, - and _."), code="packages.bad_promo_code"
            )
        if self.kind == PromoKind.PERCENT:
            if self.percent_off is None or not 1 <= self.percent_off <= 100:
                errors["percent_off"] = ValidationError(
                    _("Enter a percentage from 1 to 100."), code="packages.promo_percent"
                )
            self.amount_off_cents = None
        elif self.kind == PromoKind.FIXED:
            if not self.amount_off_cents:
                errors["amount_off_cents"] = ValidationError(
                    _("Enter an amount greater than $0.00."), code="packages.promo_amount"
                )
            self.percent_off = None
        else:
            errors["kind"] = ValidationError(
                _("Choose percent off or a fixed amount off."), code="packages.promo_kind"
            )
        if self.duration == PromoDuration.REPEATING:
            if self.duration_months is None or not 1 <= self.duration_months <= PROMO_MONTHS_MAX:
                errors["duration_months"] = ValidationError(
                    _("Enter a number of months from 1 to %(max)s.") % {"max": PROMO_MONTHS_MAX},
                    code="packages.promo_months",
                )
        elif self.duration in PromoDuration.values:
            self.duration_months = None
        else:
            errors["duration"] = ValidationError(
                _("Choose once, a number of months or forever."), code="packages.promo_duration"
            )
        if self.max_redemptions is not None and self.max_redemptions < max(
            1, self.redemptions_count
        ):
            errors["max_redemptions"] = ValidationError(
                _("The maximum can't be lower than the %(count)s uses already made (or 0).")
                % {"count": self.redemptions_count},
                code="packages.promo_max",
            )
        if self.currency != CURRENCY:
            errors["currency"] = ValidationError(
                _("Prices are in Canadian dollars (CAD)."), code="packages.currency_cad"
            )
        if errors:
            raise PackageError(errors)

    def status_at(self, moment: datetime) -> str:
        if self.expires_at is not None and self.expires_at <= moment:
            return PromoStatus.EXPIRED
        if self.max_redemptions is not None and self.redemptions_count >= self.max_redemptions:
            return PromoStatus.USED_UP
        return PromoStatus.ACTIVE


class PromoRedemption(AuditedModel, OrgOwnedModel):
    """An organisation used a promo code (once per code and organisation) — at checkout (U-04).

    An organisation record (its history), while the counter lives on the platform's
    ``PromoCode``.
    """

    promo = models.ForeignKey(
        PromoCode,
        on_delete=models.PROTECT,
        related_name="redemptions",
        verbose_name=_("promo code"),
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("package"),
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("promo code redemption")
        verbose_name_plural = _("promo code redemptions")
        constraints = [
            models.UniqueConstraint(
                fields=("promo", "organisation"), name="packages_promoredemption_once_per_org"
            ),
        ]

    def __str__(self) -> str:
        return self.promo.code
