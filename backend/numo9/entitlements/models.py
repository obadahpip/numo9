"""Subscriptions, entitlement overrides and product history (U-03-T02, T03, T05).

``Subscription`` (U-03-T02) — the organisation's place in the commercial life-cycle: its package
and status. It is the skeleton U-04 extends with the Stripe billing fields (customer, subscription,
interval, cancel at period end, payment method). An organisation has **at most one subscription
that is not cancelled** (partial unique index ``entitlements_one_current_subscription``); cancelled
ones stay as history. Fields:

- ``package`` — the package subscribed to (empty for a trial or demo started before a package is
  chosen: the engine uses the configured trial/demo package);
- ``status`` — ``trialing`` (U-05), ``active``, ``past_due`` (payment failed: full access until
  ``grace_until``), ``read_only`` (after grace, or after a trial ended unpaid), ``cancelled`` (read
  and export only), ``demo`` (U-07);
- ``current_period_end`` — end of the paid (or trial) period; ``grace_until`` — end of the grace
  period of a ``past_due`` subscription (required then);
- ``founding`` — the founding-1,000 offer (U-08): every active product, whatever the package;
- ``override`` — platform adjustments of this subscription (JSON): ``products`` — extra product
  codes for the life of the subscription; ``limits`` — limits over the package's (U-06);
- ``status_changed_at`` / ``status_reason`` — when the status last changed and why
  (``trial_ended``, ``payment_failed``, ``cancelled``, ``platform``): the read-only banner shows
  them (U-03-T12).

Saving a subscription mirrors its status on ``Organisation.status`` (trialing → trial, past_due →
grace…), the commercial state the tenancy screens already show.

``EntitlementOverride`` (U-03-T03) — the Platform Owner grants one product to one organisation until
``expires_at`` (time-boxed) with a reason: a trial of Payroll for a prospect, a goodwill extension.
An expired or removed override is ignored. Organisation records, audited (the grant shows in the
organisation's audit log, U-03-T14).

``OrgProductHistory`` (U-03-T05) — every product an organisation has ever been entitled to, first
and last seen: read retention keeps the product's ``*.read`` keys after a downgrade, so data
created while entitled stays readable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.catalogue.models import Product
from numo9.packages.models import BillingInterval, Package, PackageStatus
from numo9.tenancy.models import Organisation, OrganisationStatus, OrgOwnedModel


class SubscriptionStatus(models.TextChoices):
    TRIALING = "trialing", _("Trial")
    ACTIVE = "active", _("Active")
    PAST_DUE = "past_due", _("Payment overdue (grace period)")
    READ_ONLY = "read_only", _("Read-only")
    CANCELLED = "cancelled", _("Cancelled")
    DEMO = "demo", _("Demo")


class StatusReason(models.TextChoices):
    TRIAL_ENDED = "trial_ended", _("The trial ended")
    PAYMENT_FAILED = "payment_failed", _("The payment failed")
    CANCELLED = "cancelled", _("The subscription was cancelled")
    PLATFORM = "platform", _("Set by Numo9")


#: Subscription status → the organisation's commercial status (tenancy).
ORGANISATION_STATUS: dict[str, str] = {
    SubscriptionStatus.TRIALING: OrganisationStatus.TRIAL,
    SubscriptionStatus.ACTIVE: OrganisationStatus.ACTIVE,
    SubscriptionStatus.PAST_DUE: OrganisationStatus.GRACE,
    SubscriptionStatus.READ_ONLY: OrganisationStatus.READ_ONLY,
    SubscriptionStatus.CANCELLED: OrganisationStatus.CANCELLED,
    SubscriptionStatus.DEMO: OrganisationStatus.DEMO,
}
#: Keys of ``Subscription.override`` the engine and U-06 read.
OVERRIDE_KEYS: frozenset[str] = frozenset({"products", "limits"})


def _in(field: str, choices: type[models.TextChoices]) -> models.Q:
    return models.Q(**{f"{field}__in": choices.values})


def _validation(field: str, message: Any, code: str, **params: Any) -> ValidationError:
    return ValidationError({field: ValidationError(message, code=code, params=params)})


def current_subscription(organisation: Organisation | None) -> Subscription | None:
    """The organisation's subscription that hasn't ended, else its latest cancelled one."""
    if organisation is None:
        return None
    rows = Subscription._base_manager.filter(
        organisation_id=organisation.pk, deleted_at__isnull=True
    ).select_related("package")
    live: Subscription | None = rows.exclude(status=SubscriptionStatus.CANCELLED).first()
    if live is not None:
        return live
    ended: Subscription | None = rows.order_by("-status_changed_at", "-id").first()
    return ended


class PaymentMethodType(models.TextChoices):
    """How the organisation pays (U-04-T02): the method's details stay at Stripe."""

    CARD = "card", _("Card")
    ACSS_DEBIT = "acss_debit", _("Pre-authorised debit (PAD)")


class Subscription(AuditedModel, OrgOwnedModel):
    package = models.ForeignKey(
        Package,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subscriptions",
        verbose_name=_("package"),
    )
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIALING,
    )
    current_period_end = models.DateTimeField(_("current period ends"), null=True, blank=True)
    grace_until = models.DateTimeField(
        _("grace period ends"),
        null=True,
        blank=True,
        help_text=_("A past-due subscription keeps full access until then."),
    )
    founding = models.BooleanField(
        _("founding organisation"),
        default=False,
        help_text=_("Founding-1,000 offer (U-08): every product, whatever the package."),
    )
    override = models.JSONField(
        _("platform adjustments"),
        default=dict,
        blank=True,
        help_text=_('{"products": ["payroll"], "limits": {"max_org_users": 20}}'),
    )
    status_changed_at = models.DateTimeField(_("status changed at"), default=timezone.now)
    status_reason = models.CharField(
        _("reason"), max_length=20, choices=StatusReason.choices, blank=True
    )
    # ---- billing (U-04-T02): Stripe's ids; the card and the PAD mandate stay at Stripe ----
    stripe_customer_id = models.CharField(
        _("Stripe customer"),
        max_length=64,
        blank=True,
        db_default="",
        help_text=_("One Stripe customer per organisation (cus_…)."),
    )
    stripe_subscription_id = models.CharField(
        _("Stripe subscription"), max_length=64, blank=True, db_default=""
    )
    interval = models.CharField(
        _("billing interval"),
        max_length=8,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTH,
        db_default=BillingInterval.MONTH,
    )
    cancel_at_period_end = models.BooleanField(
        _("cancels at the end of the period"),
        default=False,
        db_default=False,
        help_text=_("Cancelled by the owner: access continues until the period ends."),
    )
    payment_method_type = models.CharField(
        _("payment method"),
        max_length=16,
        choices=PaymentMethodType.choices,
        blank=True,
        db_default="",
    )
    #: Stripe ``created`` of the latest billing event applied (U-04-T15): an older event that
    #: arrives late never overwrites a newer state.
    stripe_event_created = models.DateTimeField(_("last billing event at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation",),
                condition=models.Q(deleted_at__isnull=True)
                & ~models.Q(status=SubscriptionStatus.CANCELLED),
                name="entitlements_one_current_subscription",
            ),
            models.CheckConstraint(
                condition=_in("status", SubscriptionStatus),
                name="entitlements_subscription_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status_reason="") | _in("status_reason", StatusReason),
                name="entitlements_subscription_reason_valid",
            ),
            models.UniqueConstraint(
                fields=("stripe_subscription_id",),
                condition=~models.Q(stripe_subscription_id=""),
                name="entitlements_stripe_subscription_unique",
            ),
            models.CheckConstraint(
                condition=_in("interval", BillingInterval),
                name="entitlements_subscription_interval_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(payment_method_type="")
                | _in("payment_method_type", PaymentMethodType),
                name="entitlements_subscription_method_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=SubscriptionStatus.PAST_DUE)
                | models.Q(grace_until__isnull=False),
                name="entitlements_subscription_grace_required",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("package", "status"), name="entitlements_sub_package_idx"),
            models.Index(fields=("stripe_customer_id",), name="entitlements_sub_customer_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.package.code if self.package else '—'} · {self.status}"

    def audit_label(self) -> str:
        return str(self)

    @property
    def extra_products(self) -> list[str]:
        products = (self.override or {}).get("products") or []
        return [str(code) for code in products]

    def clean(self) -> None:
        if self.status == SubscriptionStatus.PAST_DUE and self.grace_until is None:
            raise _validation(
                "grace_until",
                _("A past-due subscription needs the date its grace period ends."),
                "entitlements.subscription.grace_required",
            )
        if self.package is not None and self.package.status == PackageStatus.DRAFT:
            raise _validation(
                "package",
                _("%(package)s is a draft: activate it before subscribing to it."),
                "entitlements.subscription.package_draft",
                package=self.package.code,
            )
        override = self.override if isinstance(self.override, dict) else None
        if override is None or set(override) - OVERRIDE_KEYS:
            raise _validation(
                "override",
                _("Use the keys products and limits only."),
                "entitlements.subscription.override_keys",
            )
        products = override.get("products", [])
        if not isinstance(products, list) or not all(isinstance(p, str) for p in products):
            raise _validation(
                "override",
                _("products is a list of product codes."),
                "entitlements.subscription.override_products",
            )
        unknown = sorted(set(products) - set(Product.objects.values_list("code", flat=True)))
        if unknown:
            raise _validation(
                "override",
                _("Unknown product: %(codes)s."),
                "entitlements.subscription.override_unknown_product",
                codes=", ".join(unknown),
            )
        if self._another_current():
            raise _validation(
                "status",
                _("This organisation already has a subscription: change it instead."),
                "entitlements.subscription.one_current",
            )

    def _another_current(self) -> bool:
        if self.status == SubscriptionStatus.CANCELLED or self.deleted_at is not None:
            return False
        return (
            Subscription._base_manager.filter(organisation_id=self.organisation_id)
            .filter(deleted_at__isnull=True)
            .exclude(status=SubscriptionStatus.CANCELLED)
            .exclude(pk=self.pk)
            .exists()
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        update_fields = kwargs.get("update_fields")
        if update_fields is None or set(update_fields) - {"deleted_at", "updated_at"}:
            self.clean()
        stored = (
            None
            if self._state.adding
            else Subscription._base_manager.filter(pk=self.pk)
            .values_list("status", flat=True)
            .first()
        )
        if stored is not None and stored != self.status:
            self.status_changed_at = timezone.now()
            if update_fields is not None:
                kwargs["update_fields"] = [*update_fields, "status_changed_at"]
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.deleted_at is None:
                Organisation.objects.filter(pk=self.organisation_id).update(
                    status=ORGANISATION_STATUS[self.status]
                )


class EntitlementOverride(AuditedModel, OrgOwnedModel):
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="+", verbose_name=_("product")
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("granted by"),
    )
    expires_at = models.DateTimeField(_("expires at"))
    reason = models.CharField(_("reason"), max_length=300)

    class Meta:
        ordering = ("-expires_at", "-id")
        verbose_name = _("entitlement override")
        verbose_name_plural = _("entitlement overrides")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="entitlements_override_reason_required"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "expires_at"), name="entitlements_override_org_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product.code} until {self.expires_at:%Y-%m-%d}"

    def audit_label(self) -> str:
        return str(self)

    def is_active(self, now: datetime | None = None) -> bool:
        """Granting now: not removed, not expired (``expires_at`` is the first moment it isn't)."""
        return self.deleted_at is None and self.expires_at > (now or timezone.now())

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.reason = " ".join((self.reason or "").split())
        update_fields = kwargs.get("update_fields")
        if update_fields is None or set(update_fields) - {"deleted_at", "updated_at"}:
            if not self.reason:
                raise _validation(
                    "reason",
                    _("Say why the product is granted: the reason is in the audit log."),
                    "entitlements.override.reason_required",
                )
            if self._state.adding and self.expires_at <= timezone.now():
                raise _validation(
                    "expires_at",
                    _("Choose an end date in the future."),
                    "entitlements.override.expires_past",
                )
        super().save(*args, **kwargs)


def active_overrides(
    organisation: Organisation, now: datetime
) -> models.QuerySet[EntitlementOverride]:
    return EntitlementOverride._base_manager.filter(
        organisation_id=organisation.pk, deleted_at__isnull=True, expires_at__gt=now
    ).select_related("product")


class OrgProductHistory(OrgOwnedModel):
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="+", verbose_name=_("product")
    )
    first_entitled_at = models.DateTimeField(_("first entitled"), default=timezone.now)
    last_entitled_at = models.DateTimeField(_("last entitled"), default=timezone.now)

    class Meta:
        ordering = ("product__sort", "product__code")
        verbose_name = _("product history")
        verbose_name_plural = _("product history")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "product"), name="entitlements_history_once"
            ),
        ]

    def __str__(self) -> str:
        return self.product.code


# ---- free trial (U-05) -------------------------------------------------------------------------

#: Trial length when nothing else is configured (U-05 business rule).
TRIAL_DAYS = 30
TRIAL_MAX_DAYS = 90


class TrialConfig(models.Model):
    """The free trial every new organisation starts (U-05-T01): which package it tries and for
    how many days. **One row** (``pk = 1``, a database check): ``TrialConfig.current()`` reads it,
    creating the default (no package — the engine's ``NUMO9_TRIAL_PACKAGE`` or every product —,
    30 days) the first time. The Platform Owner changes it in the console (U-06). Platform data,
    not an organisation's."""

    SINGLETON_ID = 1

    package = models.ForeignKey(
        Package,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("trial package"),
        help_text=_("Empty: the configured trial package, else every product."),
    )
    days = models.PositiveSmallIntegerField(_("trial length (days)"), default=TRIAL_DAYS)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("updated by"),
    )

    class Meta:
        verbose_name = _("trial settings")
        verbose_name_plural = _("trial settings")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="entitlements_trial_config_single"
            ),
            models.CheckConstraint(
                condition=models.Q(days__gte=1, days__lte=TRIAL_MAX_DAYS),
                name="entitlements_trial_config_days",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.days} days · {self.package or '—'}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if not 1 <= int(self.days or 0) <= TRIAL_MAX_DAYS:
            raise ValidationError(
                {"days": _("A trial lasts 1 to %(max)d days.") % {"max": TRIAL_MAX_DAYS}},
                code="trial_days",
            )
        if self.package is not None and self.package.status == PackageStatus.DRAFT:
            raise ValidationError(
                {"package": _("Choose a published package for the trial.")}, code="trial_package"
            )

    @classmethod
    def current(cls) -> TrialConfig:
        config, _created = cls.objects.get_or_create(pk=cls.SINGLETON_ID)
        return config


class TrialRegistry(models.Model):
    """Every free trial started (U-05-T02): which organisation, and the normalised Business
    Number and owner email it was started with. **One trial per BN and per email**: both are
    unique when present (partial unique indexes), so a second trial with the same BN or email is
    refused by the database even if two sign-ups race. Values are stored normalised
    (``trials.normalise_bn`` / ``normalise_email``); empty when unknown (an accountant-created
    organisation has no owner yet; the BN is often entered later, U-05 edge case). Platform data:
    it outlives the organisation's trial and is never shown to tenants."""

    normalised_bn = models.CharField(_("Business Number (9 digits)"), max_length=9, blank=True)
    normalised_email = models.CharField(_("owner email"), max_length=254, blank=True)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="+", verbose_name=_("organisation")
    )
    started_at = models.DateTimeField(_("trial started"), default=timezone.now)

    class Meta:
        verbose_name = _("trial started")
        verbose_name_plural = _("trials started")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("normalised_bn",),
                condition=~models.Q(normalised_bn=""),
                name="entitlements_trial_one_per_bn",
            ),
            models.UniqueConstraint(
                fields=("normalised_email",),
                condition=~models.Q(normalised_email=""),
                name="entitlements_trial_one_per_email",
            ),
            models.CheckConstraint(
                condition=models.Q(normalised_bn="") | models.Q(normalised_bn__regex=r"^[0-9]{9}$"),
                name="entitlements_trial_bn_digits",
            ),
            models.CheckConstraint(
                condition=models.Q(normalised_email=models.functions.Lower("normalised_email")),
                name="entitlements_trial_email_lower",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation",), name="entitlements_trial_org_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.organisation} · {self.started_at:%Y-%m-%d}"


class TrialReminder(OrgOwnedModel):
    """One trial reminder sent (U-05-T07): 7, 3 and 1 days before the trial ends and the day it
    ended (0). Unique per subscription and milestone, so the reminder job is idempotent: running
    it twice, or late, never sends a milestone twice."""

    MILESTONES = (7, 3, 1, 0)

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="trial_reminders",
        verbose_name=_("subscription"),
    )
    milestone = models.PositiveSmallIntegerField(_("days left"))
    sent_at = models.DateTimeField(_("sent at"), default=timezone.now)
    recipients = models.PositiveSmallIntegerField(_("recipients"), default=0)

    class Meta:
        ordering = ("subscription", "-milestone")
        verbose_name = _("trial reminder")
        verbose_name_plural = _("trial reminders")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("subscription", "milestone"), name="entitlements_trial_reminder_once"
            ),
            models.CheckConstraint(
                condition=models.Q(milestone__in=(7, 3, 1, 0)),
                name="entitlements_trial_reminder_milestone",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.subscription} · {self.milestone} d"
