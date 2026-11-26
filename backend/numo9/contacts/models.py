"""Contacts (B-01).

``Contact`` (B-01-T02) is one model for everyone the organisation deals with. Its **roles** are set
explicitly — customer, supplier, employee, contractor, government agency (a customer that is also
a supplier has both) — never inferred from transactions (gap-19). It is an organisation record
(``OrgOwnedModel``) with every change in the audit log (``AuditedModel``):

- ``number`` — the contact number (``C-0001``), unique per organisation (case-insensitive,
  database constraint); taken from the organisation's contact sequence (A-05-T08) when left empty;
- ``display_name`` (required) and ``legal_name`` (printed on statements and tax slips; never
  digits only);
- ``roles`` — at least one, each once, from ``ContactRole`` (checked by ``clean()`` and by the
  PostgreSQL check ``contacts_contact_roles_valid``, added as raw SQL by migration 0001 — array
  operators — and kept out of the model state so SQLite can still rebuild the table);
- ``bn`` — the CRA Business Number (9 digits, check digit) and ``tax_id`` — any other tax
  identifier printed on documents (a foreign registration number…);
- ``currency`` — ISO 4217, CAD by default (gap-20); documents for the contact default to it (R-01);
- ``credit_limit`` (empty = no limit) and ``credit_mode`` — ``warn`` shows a message, ``block``
  needs an override approval (B-01-T13, gap-20);
- ``t4a_flag`` — payments to the contact are reported on T4A slips (withholding flag, gap-20);
- ``portal_enabled`` — the contact may use the client portal; ``statement_pref`` — how statements
  reach it; ``language`` — the language of its documents and emails;
- ``status`` — active or archived. Archiving is the contact's "delete": an archived contact keeps
  its history and can be restored. ``deleted_at`` is left to the merge (B-01-T12), which retires
  the merged contact and keeps its number as an alias.

People (``ContactPerson``, B-01-T03) and addresses (``Address``, B-01-T04) belong to a contact.
"""

from __future__ import annotations

import re
import zoneinfo
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _

from numo9.accounts.models import Locale
from numo9.audit.mixins import AuditedModel
from numo9.orgsettings.models import DAY_OF_MONTH_TERMS, TermsType
from numo9.orgsettings.validators import (
    Province,
    normalise_phone,
    normalise_postal_code,
    validate_legal_name,
    validate_postal_code,
    validate_postal_code_province,
    validate_province,
)
from numo9.tenancy.models import DEFAULT_TIME_ZONE, OrgOwnedModel

from .duplicates import name_key
from .fields import PortableArrayField

if TYPE_CHECKING:
    from .tax import ProvinceTaxHint
from .validators import (
    DEFAULT_CURRENCY,
    normalise_bn,
    normalise_currency,
    normalise_roles,
    validate_bn,
    validate_currency,
    validate_roles,
)


class ContactRole(models.TextChoices):
    CUSTOMER = "customer", _("Customer")
    SUPPLIER = "supplier", _("Supplier")
    EMPLOYEE = "employee", _("Employee")
    CONTRACTOR = "contractor", _("Contractor")
    GOVERNMENT_AGENCY = "government_agency", _("Government agency")


class CreditMode(models.TextChoices):
    WARN = "warn", _("Warn")
    BLOCK = "block", _("Block (needs approval)")


class StatementPreference(models.TextChoices):
    NONE = "none", _("Don't send statements")
    EMAIL = "email", _("Email")
    POST = "post", _("Print and mail")
    PORTAL = "portal", _("Client portal")


class AmountsAre(models.TextChoices):
    """How amounts are entered on this contact's documents (B-01-T06)."""

    TAX_EXCLUSIVE = "tax_exclusive", _("Tax exclusive")
    TAX_INCLUSIVE = "tax_inclusive", _("Tax inclusive")
    NO_TAX = "no_tax", _("No tax")


class ContactStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    ARCHIVED = "archived", _("Archived")


NAME_MAX = 200
NUMBER_MAX = 20
SOURCE_LANGUAGE = "en-ca"
TAX_ID_MAX = 40


def _in(field: str, choices: type[models.TextChoices]) -> models.Q:
    return models.Q(**{f"{field}__in": choices.values})


def _province_codes() -> list[str]:
    return list(Province.values)


class Contact(AuditedModel, OrgOwnedModel):
    number = models.CharField(
        _("contact number"),
        max_length=NUMBER_MAX,
        blank=True,
        help_text=_("Unique in the organisation; the next number is used when left empty."),
    )
    external_id = models.CharField(
        _("external ID"),
        max_length=64,
        blank=True,
        db_default="",
        default="",
        help_text=_(
            "The contact's ID in another system (an import's match key, B-03-T05); unique in the "
            "organisation when set."
        ),
    )
    display_name = models.CharField(_("display name"), max_length=NAME_MAX)
    legal_name = models.CharField(
        _("legal name"),
        max_length=NAME_MAX,
        blank=True,
        validators=[validate_legal_name],
        help_text=_("As registered; printed on statements and tax slips."),
    )
    roles = PortableArrayField(
        models.CharField(max_length=32, choices=ContactRole.choices),
        verbose_name=_("roles"),
        default=list,
        help_text=_("At least one: customer, supplier, employee, contractor, government agency."),
    )
    bn = models.CharField(
        _("Business Number (BN)"), max_length=9, blank=True, validators=[validate_bn]
    )
    tax_id = models.CharField(
        _("tax ID"),
        max_length=TAX_ID_MAX,
        blank=True,
        help_text=_("Another tax number printed on documents, e.g. a foreign registration number."),
    )
    currency = models.CharField(
        _("currency"), max_length=3, default=DEFAULT_CURRENCY, validators=[validate_currency]
    )
    credit_limit = models.DecimalField(
        _("credit limit"),
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Empty means no limit."),
    )
    credit_mode = models.CharField(
        _("when the credit limit is reached"),
        max_length=8,
        choices=CreditMode.choices,
        default=CreditMode.WARN,
    )
    t4a_flag = models.BooleanField(
        _("issue T4A slips"),
        default=False,
        help_text=_("Payments to this contact are reported on T4A slips."),
    )
    portal_enabled = models.BooleanField(_("client portal access"), default=False)
    statement_pref = models.CharField(
        _("statements"),
        max_length=8,
        choices=StatementPreference.choices,
        default=StatementPreference.EMAIL,
    )
    language = models.CharField(
        _("language"), max_length=5, choices=Locale.choices, default=Locale.EN_CA
    )
    status = models.CharField(
        _("status"), max_length=10, choices=ContactStatus.choices, default=ContactStatus.ACTIVE
    )
    archived_at = models.DateTimeField(_("archived at"), null=True, blank=True)
    name_key = models.CharField(
        _("name key"),
        max_length=NAME_MAX,
        blank=True,
        editable=False,
        help_text=_("The display name without case, accents and company forms (duplicates)."),
    )
    custom_fields = models.JSONField(
        _("custom fields"),
        default=dict,
        blank=True,
        help_text=_("Values of the organisation's custom fields, by field key (B-01-T09)."),
    )

    # Merge (B-01-T12): a merged contact stays as an archived alias of the one it was merged into,
    # so its number still resolves and records that can't move (posted journals) still show it.
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="aliases",
        verbose_name=_("merged into"),
    )
    merged_at = models.DateTimeField(_("merged at"), null=True, blank=True)

    # Sales and purchase defaults (B-01-T06): suggested on this contact's invoices and bills.
    sales_account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("default sales account"),
    )
    sales_payment_term = models.ForeignKey(
        "contacts.PaymentTerm",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("default invoice terms"),
    )
    sales_amounts_are = models.CharField(
        _("invoice amounts are"),
        max_length=16,
        choices=AmountsAre.choices,
        default=AmountsAre.TAX_EXCLUSIVE,
        db_default=AmountsAre.TAX_EXCLUSIVE,
    )
    purchase_account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("default purchase account"),
    )
    purchase_payment_term = models.ForeignKey(
        "contacts.PaymentTerm",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("default bill terms"),
    )
    purchase_amounts_are = models.CharField(
        _("bill amounts are"),
        max_length=16,
        choices=AmountsAre.choices,
        default=AmountsAre.TAX_EXCLUSIVE,
        db_default=AmountsAre.TAX_EXCLUSIVE,
    )

    audit_exclude: ClassVar[frozenset[str]] = frozenset({"archived_at", "name_key"})

    class Meta:
        ordering = ("display_name", "number")
        verbose_name = _("contact")
        verbose_name_plural = _("contacts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "organisation", Lower("number"), name="contacts_contact_number_unique_per_org"
            ),
            models.CheckConstraint(
                condition=~models.Q(number=""), name="contacts_contact_number_required"
            ),
            models.CheckConstraint(
                condition=~models.Q(display_name=""), name="contacts_contact_name_required"
            ),
            models.CheckConstraint(
                condition=models.Q(currency__regex=r"^[A-Z]{3}$"),
                name="contacts_contact_currency_format",
            ),
            models.CheckConstraint(
                condition=models.Q(credit_limit__isnull=True) | models.Q(credit_limit__gte=0),
                name="contacts_contact_credit_limit_positive",
            ),
            models.CheckConstraint(
                condition=_in("credit_mode", CreditMode), name="contacts_contact_credit_mode_valid"
            ),
            models.CheckConstraint(
                condition=_in("statement_pref", StatementPreference),
                name="contacts_contact_statement_pref_valid",
            ),
            models.CheckConstraint(
                condition=_in("language", Locale), name="contacts_contact_language_valid"
            ),
            models.CheckConstraint(
                condition=_in("status", ContactStatus), name="contacts_contact_status_valid"
            ),
            models.UniqueConstraint(
                fields=("organisation", "external_id"),
                condition=~models.Q(external_id=""),
                name="contacts_contact_external_id_unique",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "status", "display_name"),
                name="contacts_contact_list_idx",
            ),
            models.Index(fields=("organisation", "bn"), name="contacts_contact_bn_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.number})" if self.number else self.display_name

    def audit_label(self) -> str:
        return str(self)

    # ---- roles ---------------------------------------------------------------------------

    def has_role(self, role: str) -> bool:
        return role in (self.roles or [])

    @property
    def is_customer(self) -> bool:
        return self.has_role(ContactRole.CUSTOMER)

    @property
    def is_supplier(self) -> bool:
        return self.has_role(ContactRole.SUPPLIER)

    @property
    def is_archived(self) -> bool:
        return self.status == ContactStatus.ARCHIVED

    @property
    def printed_name(self) -> str:
        """The name on statements and slips: the legal name, else the display name."""
        return self.legal_name or self.display_name

    @property
    def province_tax_hint(self) -> ProvinceTaxHint | None:
        """The sales-tax regime of the contact's province today (B-01-T07): QC → GST + QST."""
        from .tax import contact_tax_hint

        return contact_tax_hint(self)

    # ---- archive -------------------------------------------------------------------------

    def archive(self) -> None:
        """Archive the contact (its "delete"): hidden from pickers, history kept, restorable."""
        if self.status != ContactStatus.ARCHIVED:
            self.status = ContactStatus.ARCHIVED
            self.archived_at = timezone.now()
            self.save(update_fields=["status", "archived_at", "updated_at"])

    def unarchive(self) -> None:
        if self.status != ContactStatus.ACTIVE:
            self.status = ContactStatus.ACTIVE
            self.archived_at = None
            self.save(update_fields=["status", "archived_at", "updated_at"])

    # ---- validation and save -------------------------------------------------------------

    def normalise(self) -> None:
        """Tidy user input before validation."""
        for name in ("number", "display_name", "legal_name", "tax_id"):
            setattr(self, name, " ".join((getattr(self, name) or "").split()))
        self.bn = normalise_bn(self.bn)
        self.name_key = name_key(self.display_name)
        self.currency = normalise_currency(self.currency) or DEFAULT_CURRENCY
        self.roles = normalise_roles(self.roles, ContactRole.values)

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}
        try:
            validate_roles(self.roles, ContactRole.values)
        except ValidationError as error:
            errors.setdefault("roles", []).append(error)
        self._clean_custom_fields(errors)
        self._clean_defaults(errors)
        if self.number and self._number_taken():
            errors.setdefault("number", []).append(
                ValidationError(
                    _("Contact number %(number)s is already used in this organisation."),
                    code="contacts.number.taken",
                    params={"number": self.number},
                )
            )
        if errors:
            raise ValidationError(errors)

    def _clean_defaults(self, errors: dict[str, list[ValidationError]]) -> None:
        """Default accounts fit their side (sales: revenue…; purchase: expense or asset) and,
        like the payment terms, belong to this organisation (B-01-T06)."""
        from numo9.ledger.contexts import allowed_in_context

        for field, context, message in (
            (
                "sales_account",
                "sales",
                _(
                    "%(account)s can't be a sales account: choose a revenue or other income "
                    "account."
                ),
            ),
            (
                "purchase_account",
                "purchase",
                _(
                    "%(account)s can't be a purchase account: choose an expense or an asset "
                    "account."
                ),
            ),
        ):
            account = getattr(self, field)
            if account is None:
                continue
            if account.organisation_id != self.organisation_id or not allowed_in_context(
                account, context
            ):
                errors.setdefault(field, []).append(
                    ValidationError(
                        message, code=f"contacts.defaults.{field}", params={"account": str(account)}
                    )
                )
        for field in ("sales_payment_term", "purchase_payment_term"):
            term = getattr(self, field)
            if term is not None and (
                term.organisation_id != self.organisation_id or term.status != ContactStatus.ACTIVE
            ):
                errors.setdefault(field, []).append(
                    ValidationError(
                        _("Choose an active payment term of this organisation."),
                        code="contacts.defaults.payment_term",
                    )
                )

    def _clean_custom_fields(self, errors: dict[str, list[ValidationError]]) -> None:
        from .custom_fields import clean_custom_values

        definitions = {
            d.key: d
            for d in CustomFieldDefinition._base_manager.filter(
                organisation_id=self.organisation_id, record_type=CustomFieldRecordType.CONTACT
            )
        }
        previous: dict[str, Any] = {}
        if self.pk is not None:
            stored = Contact._base_manager.filter(pk=self.pk).values_list(
                "custom_fields", flat=True
            )
            previous = stored.first() or {}
        try:
            self.custom_fields = clean_custom_values(
                self.custom_fields, definitions, previous, creating=self.pk is None
            )
        except ValidationError as error:
            for field, problems in error.error_dict.items():
                errors.setdefault(field, []).extend(problems)

    def _number_taken(self) -> bool:
        return (
            Contact._base_manager.filter(
                organisation_id=self.organisation_id, number__iexact=self.number
            )
            .exclude(pk=self.pk)
            .exists()
        )

    def validate(self, update_fields: Any = None) -> None:
        """Field and cross-field rules; every problem is reported at once."""
        errors: dict[str, Any] = {}
        # Relations and bookkeeping are set by the platform; clean() checks roles and number.
        exclude = ["organisation", "created_by", "public_id", "number", "roles", "custom_fields"]
        if update_fields is not None:
            names = {self._meta.get_field(n).name for n in update_fields}
            exclude += [f.name for f in self._meta.concrete_fields if f.name not in names]
        try:
            self.clean_fields(exclude=exclude)
        except ValidationError as error:
            errors = error.update_error_dict(errors)
        if update_fields is None or {"roles", "number", "custom_fields"} & set(update_fields):
            try:
                self.clean()
            except ValidationError as error:
                errors = error.update_error_dict(errors)
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.normalise()
        update_fields = kwargs.get("update_fields")
        self.validate(update_fields=update_fields)
        if update_fields is not None and "display_name" in update_fields:
            kwargs["update_fields"] = [*update_fields, "name_key"]
        with transaction.atomic():
            if not self.number:
                self.number = self._next_free_number()
            super().save(*args, **kwargs)

    def _next_free_number(self) -> str:
        """The next number of the contact sequence, skipping numbers already typed by hand."""
        from numo9.orgsettings.models import DocType
        from numo9.orgsettings.numbering import allocate_number

        for _attempt in range(1000):
            self.number = allocate_number(DocType.CONTACT, organisation=self.organisation)
            if not self._number_taken():
                return self.number
        raise ValidationError(  # pragma: no cover - 1,000 hand-typed numbers in a row
            _("No free contact number: check the contact numbering settings."),
            code="contacts.number.exhausted",
        )


# ---- people (B-01-T03) -------------------------------------------------------------------------


class ContactPerson(AuditedModel, OrgOwnedModel):
    """A person at a contact (B-01-T03): as many as needed (no limit), one of them primary.

    - the first person of a contact becomes its primary person; marking another one primary
      unmarks the previous one in the same transaction, and removing the primary person promotes
      the earliest remaining one (as does unmarking the primary person) — so a contact with people
      always has exactly one primary (database constraint: at most one);
    - ``include_in_emails`` — the person is copied on emails of documents sent to the contact;
    - a person needs a name or an email; the email is stored in lower case, the telephone as
      E.164 (the organisation-settings rule, A-05-T02);
    - removing a person is a soft delete (the audit log keeps who they were).
    """

    contact = models.ForeignKey(
        Contact, on_delete=models.PROTECT, related_name="people", verbose_name=_("contact")
    )
    first_name = models.CharField(_("first name"), max_length=100, blank=True)
    last_name = models.CharField(_("last name"), max_length=100, blank=True)
    email = models.EmailField(_("email address"), max_length=254, blank=True)
    # Set by the email provider's bounce / complaint webhook (A-07-T08): "bounced", "complained";
    # empty = no delivery problem known.
    email_status = models.CharField(
        _("email delivery"), max_length=16, blank=True, default="", db_default=""
    )
    email_status_at = models.DateTimeField(_("email delivery problem at"), null=True, blank=True)
    phone = models.CharField(_("telephone"), max_length=32, blank=True)
    job_title = models.CharField(_("job title"), max_length=100, blank=True)
    is_primary = models.BooleanField(_("primary person"), default=False)
    include_in_emails = models.BooleanField(
        _("include in emails"),
        default=True,
        help_text=_("Copied on emails of invoices, statements and other documents."),
    )

    class Meta:
        ordering = ("-is_primary", "created_at", "id")
        verbose_name = _("contact person")
        verbose_name_plural = _("contact people")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("contact",),
                condition=models.Q(is_primary=True, deleted_at__isnull=True),
                name="contacts_person_one_primary",
            ),
            models.CheckConstraint(
                condition=~models.Q(first_name="", last_name="", email=""),
                name="contacts_person_name_or_email",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "contact"), name="contacts_person_contact_idx"),
            models.Index(fields=("organisation", "email"), name="contacts_person_email_idx"),
        ]

    def __str__(self) -> str:
        return self.full_name or self.email

    def audit_label(self) -> str:
        return f"{self} · {self.contact.display_name}" if self.contact_id else str(self)

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)

    def _siblings(self) -> models.QuerySet[ContactPerson]:
        return ContactPerson._base_manager.filter(
            contact_id=self.contact_id, deleted_at__isnull=True
        ).exclude(pk=self.pk)

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}
        if not (self.first_name or self.last_name or self.email):
            errors.setdefault("first_name", []).append(
                ValidationError(
                    _("Enter the person's name or email address."),
                    code="contacts.person.name_or_email",
                )
            )
        if self.phone:
            try:
                self.phone = normalise_phone(self.phone)
            except ValidationError as error:
                errors.setdefault("phone", []).append(error)
        if self.contact_id and self.contact.organisation_id != self.organisation_id:
            errors.setdefault("contact", []).append(
                ValidationError(
                    _("Choose a contact of this organisation."), code="contacts.person.contact"
                )
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.contact_id and not self.organisation_id:
            self.organisation_id = self.contact.organisation_id
        for name in ("first_name", "last_name", "job_title", "phone"):
            setattr(self, name, " ".join((getattr(self, name) or "").split()))
        self.email = (self.email or "").strip().lower()
        update_fields = kwargs.get("update_fields")
        if update_fields is None or {"first_name", "last_name", "email", "phone"} & set(
            update_fields
        ):
            errors: dict[str, Any] = {}
            try:
                self.clean_fields(exclude=["organisation", "contact", "created_by", "public_id"])
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            try:
                self.clean()
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            if errors:
                raise ValidationError(errors)
        with transaction.atomic():
            # One person changes the contact's primary at a time.
            Contact._base_manager.select_for_update().filter(pk=self.contact_id).first()
            siblings = self._siblings()
            successor: ContactPerson | None = None
            if self.deleted_at is not None:
                self.is_primary = False
            if self.is_primary:
                for other in siblings.filter(is_primary=True):
                    other.is_primary = False
                    other._save_primary_flag()
            elif not siblings.filter(is_primary=True).exists():
                successor = siblings.order_by("created_at", "id").first()
                if successor is None and self.deleted_at is None:
                    self.is_primary = True  # the first or only person is the primary one
            if update_fields is not None and "is_primary" not in update_fields:
                kwargs["update_fields"] = [*update_fields, "is_primary"]
            super().save(*args, **kwargs)
            if successor is not None:  # removed or unmarked: the earliest other person takes over
                successor.is_primary = True
                successor._save_primary_flag()

    def _save_primary_flag(self) -> None:
        """Save only the primary flag, audited, without re-running the primary rules."""
        super().save(update_fields=["is_primary", "updated_at"])

    def make_primary(self) -> None:
        self.is_primary = True
        self.save(update_fields=["is_primary", "updated_at"])


# ---- addresses (B-01-T04) ----------------------------------------------------------------------


class AddressKind(models.TextChoices):
    BILLING = "billing", _("Billing address")
    SHIPPING = "shipping", _("Shipping address")


class Address(AuditedModel, OrgOwnedModel):
    """A contact's billing or shipping address (B-01-T04), one of each per contact.

    Canadian addresses (``country="CA"``, the default) use the Canadian terms and rules (gap-39):
    ``province`` is one of the 13 provinces and territories (two-letter code) and ``postal_code``
    the Canada Post format ``A1A 1A1`` — typed in any case, with or without the space, stored as
    ``M5V 2T6`` — whose first letter belongs to the province (the A-05-T02 validators). Other
    countries keep their own conventions: ``region`` (region, county…) and ``postal_code`` are free
    text and ``province`` stays empty.
    """

    contact = models.ForeignKey(
        Contact, on_delete=models.PROTECT, related_name="addresses", verbose_name=_("contact")
    )
    kind = models.CharField(_("type"), max_length=10, choices=AddressKind.choices)
    attention = models.CharField(_("attention"), max_length=100, blank=True)
    line1 = models.CharField(_("street address or PO box"), max_length=200, blank=True)
    line2 = models.CharField(_("address line 2"), max_length=200, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    province = models.CharField(
        _("province or territory"),
        max_length=2,
        blank=True,
        help_text=_("Two-letter code (ON, QC…) for a Canadian address."),
    )
    region = models.CharField(
        _("region"),
        max_length=100,
        blank=True,
        help_text=_("Region or county of an address outside Canada."),
    )
    postal_code = models.CharField(_("postal code"), max_length=16, blank=True)
    country = models.CharField(
        _("country"),
        max_length=2,
        default="CA",
        help_text=_("ISO 3166-1 two-letter code; CA for Canada."),
    )

    class Meta:
        ordering = ("kind",)
        verbose_name = _("address")
        verbose_name_plural = _("addresses")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("contact", "kind"),
                condition=models.Q(deleted_at__isnull=True),
                name="contacts_address_one_per_kind",
            ),
            models.CheckConstraint(
                condition=_in("kind", AddressKind), name="contacts_address_kind_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(country__regex=r"^[A-Z]{2}$"),
                name="contacts_address_country_format",
            ),
            models.CheckConstraint(
                condition=models.Q(province="")
                | models.Q(country="CA", province__in=_province_codes()),
                name="contacts_address_province_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "contact"), name="contacts_address_contact_idx"),
        ]

    def __str__(self) -> str:
        return ", ".join(self.lines())

    def audit_label(self) -> str:
        name = self.contact.display_name if self.contact_id else ""
        return f"{self.get_kind_display()} · {name}" if name else str(self.get_kind_display())

    @property
    def is_canadian(self) -> bool:
        return self.country == "CA"

    def lines(self) -> list[str]:
        """The address as printed: street lines, then "City PROV  A1A 1A1", then the country
        when it isn't Canada."""
        locality = " ".join(
            p for p in (self.city, self.province or self.region, self.postal_code) if p
        )
        out = [p for p in (self.attention, self.line1, self.line2, locality) if p]
        if not self.is_canadian:
            out.append(self.country)
        return out

    def normalise(self) -> None:
        for name in ("attention", "line1", "line2", "city", "region", "postal_code"):
            setattr(self, name, " ".join((getattr(self, name) or "").split()))
        self.country = (self.country or "").strip().upper() or "CA"
        self.province = (self.province or "").strip().upper()
        if self.is_canadian:
            self.postal_code = normalise_postal_code(self.postal_code)
            self.region = ""

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}
        if not re.fullmatch(r"[A-Z]{2}", self.country):
            errors.setdefault("country", []).append(
                ValidationError(
                    _("Use the two-letter country code, e.g. CA."),
                    code="orgsettings.country.invalid",
                )
            )
        elif self.is_canadian:
            failed = False
            for field, check, value in (
                ("province", validate_province, self.province),
                ("postal_code", validate_postal_code, self.postal_code),
            ):
                try:
                    check(value)
                except ValidationError as error:
                    errors.setdefault(field, []).append(error)
                    failed = True
            if not failed:
                try:
                    validate_postal_code_province(self.postal_code, self.province)
                except ValidationError as error:
                    errors.setdefault("postal_code", []).append(error)
        elif self.province:
            errors.setdefault("province", []).append(
                ValidationError(
                    _("Provinces are for Canadian addresses: use Region for %(country)s."),
                    code="contacts.address.province_outside_canada",
                    params={"country": self.country},
                )
            )
        if self.contact_id and self.contact.organisation_id != self.organisation_id:
            errors.setdefault("contact", []).append(
                ValidationError(
                    _("Choose a contact of this organisation."), code="contacts.address.contact"
                )
            )
        if self.deleted_at is None and self._kind_taken():
            errors.setdefault("kind", []).append(
                ValidationError(
                    _("This contact already has a %(kind)s."),
                    code="contacts.address.kind_taken",
                    params={"kind": self.get_kind_display().lower()},
                )
            )
        if errors:
            raise ValidationError(errors)

    def _kind_taken(self) -> bool:
        return (
            Address._base_manager.filter(
                contact_id=self.contact_id, kind=self.kind, deleted_at__isnull=True
            )
            .exclude(pk=self.pk)
            .exists()
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.contact_id and not self.organisation_id:
            self.organisation_id = self.contact.organisation_id
        self.normalise()
        update_fields = kwargs.get("update_fields")
        if update_fields is None or set(update_fields) - {"deleted_at", "updated_at"}:
            errors: dict[str, Any] = {}
            try:
                self.clean_fields(exclude=["organisation", "contact", "created_by", "public_id"])
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            try:
                self.clean()
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            if errors:
                raise ValidationError(errors)
        super().save(*args, **kwargs)


# ---- custom fields (B-01-T09) ------------------------------------------------------------------


class CustomFieldType(models.TextChoices):
    TEXT = "text", _("Text")
    NUMBER = "number", _("Number")
    DATE = "date", _("Date")
    SELECT = "select", _("Choice list")


class CustomFieldRecordType(models.TextChoices):
    """Records that carry custom fields (later modules add theirs: items, projects…)."""

    CONTACT = "contact", _("Contacts")


class CustomFieldDefinition(AuditedModel, OrgOwnedModel):
    """One custom field of an organisation (B-01-T09, gap-43): its key, labels in English and
    French, type, choices (select), whether it is required and its place on the form. At most 30
    per record type; removing a field is a soft delete (values already stored are kept). The key
    and, once a record has a value, the type never change. Values are checked by
    ``numo9.contacts.custom_fields``."""

    record_type = models.CharField(
        _("record type"),
        max_length=16,
        choices=CustomFieldRecordType.choices,
        default=CustomFieldRecordType.CONTACT,
    )
    key = models.CharField(
        _("key"),
        max_length=40,
        help_text=_("Lower-case letters, digits and _; starts with a letter; never changes."),
    )
    label_i18n = models.JSONField(
        _("label"), default=dict, help_text=_('The label per language, e.g. {"en-ca": "Industry"}.')
    )
    field_type = models.CharField(_("type"), max_length=8, choices=CustomFieldType.choices)
    options = models.JSONField(
        _("choices"),
        default=list,
        blank=True,
        help_text=_('For a choice list: [{"value": "construction", "labels": {"en-ca": …}}].'),
    )
    required = models.BooleanField(_("required"), default=False)
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("record_type", "position", "id")
        verbose_name = _("custom field")
        verbose_name_plural = _("custom fields")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "record_type", "key"),
                name="contacts_custom_field_key_unique",
            ),
            models.CheckConstraint(
                condition=_in("record_type", CustomFieldRecordType),
                name="contacts_custom_field_record_type_valid",
            ),
            models.CheckConstraint(
                condition=_in("field_type", CustomFieldType),
                name="contacts_custom_field_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(key__regex=r"^[a-z][a-z0-9_]{0,39}$"),
                name="contacts_custom_field_key_format",
            ),
        ]

    def __str__(self) -> str:
        return self.label or self.key

    def audit_label(self) -> str:
        return str(self)

    @property
    def label(self) -> str:
        return self.label_in(translation.get_language() or SOURCE_LANGUAGE)

    def label_in(self, language: str) -> str:
        labels = self.label_i18n or {}
        return str(labels.get(language.lower()) or labels.get(SOURCE_LANGUAGE) or self.key)

    def option_label(self, value: str, language: str = SOURCE_LANGUAGE) -> str:
        for option in self.options or []:
            if option.get("value") == value:
                labels = option.get("labels") or {}
                return str(labels.get(language.lower()) or labels.get(SOURCE_LANGUAGE) or value)
        return value

    def values_in_use(self) -> bool:
        """A record of the organisation has a value for this field."""
        return Contact._base_manager.filter(
            organisation_id=self.organisation_id, custom_fields__has_key=self.key
        ).exists()

    # ---- validation and save -------------------------------------------------------------

    def normalise(self) -> None:
        self.key = (self.key or "").strip().lower()
        self.label_i18n = {
            str(k).lower(): " ".join(str(v).split())
            for k, v in (self.label_i18n or {}).items()
            if str(v).strip()
        }
        if self.field_type != CustomFieldType.SELECT:
            self.options = []

    def clean(self) -> None:
        from .custom_fields import KEY, MAX_FIELDS_PER_RECORD_TYPE, MAX_OPTIONS

        errors: dict[str, list[ValidationError]] = {}

        def add(field: str, message: Any, code: str, **params: Any) -> None:
            errors.setdefault(field, []).append(ValidationError(message, code=code, params=params))

        if not KEY.match(self.key):
            add(
                "key",
                _("Use lower-case letters, digits and _, starting with a letter (e.g. industry)."),
                "contacts.custom_field.key_format",
            )
        if not self.label_i18n.get(SOURCE_LANGUAGE):
            add("label_i18n", _("Enter the English label."), "contacts.custom_field.label_required")
        elif any(len(v) > 100 for v in self.label_i18n.values()):
            add(
                "label_i18n",
                _("Labels are limited to 100 characters."),
                "contacts.custom_field.label_long",
            )
        if self.field_type == CustomFieldType.SELECT:
            self._clean_options(add, MAX_OPTIONS)
        siblings = CustomFieldDefinition._base_manager.filter(
            organisation_id=self.organisation_id, record_type=self.record_type
        ).exclude(pk=self.pk)
        if siblings.filter(key=self.key).exists():
            add(
                "key",
                _("Another custom field already uses the key %(key)s."),
                "contacts.custom_field.key_taken",
                key=self.key,
            )
        if self.deleted_at is None and siblings.filter(deleted_at__isnull=True).count() >= (
            MAX_FIELDS_PER_RECORD_TYPE
        ):
            add(
                "key",
                _("An organisation can have up to %(max)d custom fields on %(records)s."),
                "contacts.custom_field.limit",
                max=MAX_FIELDS_PER_RECORD_TYPE,
                records=CustomFieldRecordType(self.record_type).label.lower(),
            )
        if self.pk is not None:
            stored = CustomFieldDefinition._base_manager.filter(pk=self.pk).values(
                "key", "field_type"
            )
            before = next(iter(stored), None)
            if before is not None and before["key"] != self.key:
                add("key", _("A field's key never changes."), "contacts.custom_field.key_locked")
            elif (
                before is not None and before["field_type"] != self.field_type
            ) and self.values_in_use():
                add(
                    "field_type",
                    _("Records already have values for this field: its type can't change."),
                    "contacts.custom_field.type_locked",
                )
        if errors:
            raise ValidationError(errors)

    def _clean_options(self, add: Any, max_options: int) -> None:
        options = self.options
        if not isinstance(options, list) or not options:
            add("options", _("Add at least one choice."), "contacts.custom_field.options_required")
            return
        if len(options) > max_options:
            add(
                "options",
                _("A choice list has up to %(max)d choices."),
                "contacts.custom_field.options_limit",
                max=max_options,
            )
            return
        cleaned, seen = [], set()
        for option in options:
            value = str(option.get("value", "")).strip() if isinstance(option, dict) else ""
            labels = option.get("labels") if isinstance(option, dict) else None
            if not value or not isinstance(labels, dict) or not labels.get(SOURCE_LANGUAGE):
                add(
                    "options",
                    _("Each choice needs a value and an English label."),
                    "contacts.custom_field.option_invalid",
                )
                return
            if value in seen:
                add(
                    "options",
                    _("The choice %(value)s is listed twice."),
                    "contacts.custom_field.option_duplicate",
                    value=value,
                )
                return
            seen.add(value)
            cleaned.append(
                {"value": value, "labels": {str(k).lower(): str(v) for k, v in labels.items()}}
            )
        self.options = cleaned

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.normalise()
        update_fields = kwargs.get("update_fields")
        if update_fields is None or set(update_fields) - {"deleted_at", "updated_at", "position"}:
            errors: dict[str, Any] = {}
            try:
                self.clean_fields(
                    exclude=["organisation", "created_by", "public_id", "label_i18n", "options"]
                )
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            try:
                self.clean()
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            if errors:
                raise ValidationError(errors)
        super().save(*args, **kwargs)


# ---- payment terms master (B-01-T05) -----------------------------------------------------------

#: Longest term and the percent limits.
TERM_DAYS_MAX = 365


class DiscountBase(models.TextChoices):
    """What an early-payment discount is a percent of (E-07-T01)."""

    TOTAL = "total", _("Document total (with tax)")
    PRE_TAX = "pre_tax", _("Amount before tax")


class PaymentTerm(AuditedModel, OrgOwnedModel):
    """A payment term of the organisation's master list (B-01-T05, gap-20): picked on contacts,
    invoices and bills instead of typing terms on every contact (Xero teardown §3.2).

    - ``terms_type`` + ``days`` — how the due date is worked out, the same four types as the
      organisation's default terms (A-05): *n* days after the document date (Net 30; Due on receipt
      is 0), *n* days after the end of the document month (EOM is 0), the *n*th of the following
      month, the *n*th of the current month;
    - ``discount_pct`` / ``discount_days`` — early-payment discount (2/10 net 30: 2 % if paid within
      10 days), applied by E-07; the discount window is shorter than the term; ``discount_base``
      — a percent of the document total (with tax, the default) or of the amount before tax
      (E-07-T01);
    - ``late_interest_pct`` — annual interest on overdue amounts (FN-04 adds how it is charged);
    - ``code`` — the seed's stable key (``net_30``) for terms created with the organisation; empty
      for terms people add. Names are per language (``name_i18n``) like account names.

    Every new organisation gets the defaults (``DEFAULT_TERMS``): Due on receipt, Net 15, Net 30,
    Net 60, 2/10 net 30 and EOM. Terms are archived, never deleted (documents refer to them).
    """

    code = models.CharField(_("code"), max_length=32, blank=True)
    name_i18n = models.JSONField(
        _("name"), default=dict, help_text=_('The name per language, e.g. {"en-ca": "Net 30"}.')
    )
    terms_type = models.CharField(
        _("due date"),
        max_length=32,
        choices=TermsType.choices,
        default=TermsType.DAYS_AFTER_DOCUMENT,
    )
    days = models.PositiveSmallIntegerField(_("days or day"), default=30)
    discount_pct = models.DecimalField(
        _("early-payment discount (%)"), max_digits=5, decimal_places=2, default=Decimal("0")
    )
    discount_days = models.PositiveSmallIntegerField(_("discount if paid within (days)"), default=0)
    discount_base = models.CharField(
        _("discount is a percent of"),
        max_length=8,
        choices=DiscountBase.choices,
        default=DiscountBase.TOTAL,
        db_default=DiscountBase.TOTAL,
    )
    late_interest_pct = models.DecimalField(
        _("late interest (% a year)"), max_digits=6, decimal_places=3, default=Decimal("0")
    )
    status = models.CharField(
        _("status"), max_length=10, choices=ContactStatus.choices, default=ContactStatus.ACTIVE
    )
    position = models.PositiveSmallIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "id")
        verbose_name = _("payment term")
        verbose_name_plural = _("payment terms")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "code"),
                condition=~models.Q(code=""),
                name="contacts_payment_term_code_unique",
            ),
            models.CheckConstraint(
                condition=_in("terms_type", TermsType), name="contacts_payment_term_type_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(days__lte=TERM_DAYS_MAX),
                name="contacts_payment_term_days_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_pct__gte=0, discount_pct__lt=100),
                name="contacts_payment_term_discount_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(late_interest_pct__gte=0, late_interest_pct__lte=100),
                name="contacts_payment_term_interest_valid",
            ),
            models.CheckConstraint(
                condition=_in("status", ContactStatus), name="contacts_payment_term_status_valid"
            ),
            models.CheckConstraint(
                condition=_in("discount_base", DiscountBase),
                name="contacts_payment_term_discount_base_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def audit_label(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        return self.name_in(translation.get_language() or SOURCE_LANGUAGE)

    def name_in(self, language: str) -> str:
        names = self.name_i18n or {}
        return str(names.get(language.lower()) or names.get(SOURCE_LANGUAGE) or self.code)

    @property
    def has_discount(self) -> bool:
        return self.discount_pct > 0

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}

        def add(field: str, message: Any, code: str, **params: Any) -> None:
            errors.setdefault(field, []).append(ValidationError(message, code=code, params=params))

        names = {k: " ".join(str(v).split()) for k, v in (self.name_i18n or {}).items() if v}
        self.name_i18n = {str(k).lower(): v for k, v in names.items() if v}
        name = self.name_i18n.get(SOURCE_LANGUAGE, "")
        if not name:
            add("name_i18n", _("Enter the English name."), "contacts.payment_term.name_required")
        elif self._name_taken(name):
            add(
                "name_i18n",
                _("Another payment term is already called %(name)s."),
                "contacts.payment_term.name_taken",
                name=name,
            )
        if self.terms_type in DAY_OF_MONTH_TERMS and not 1 <= self.days <= 31:
            add("days", _("Choose a day of the month from 1 to 31."), "contacts.payment_term.day")
        elif self.days > TERM_DAYS_MAX:
            add(
                "days",
                _("A payment term is at most %(max)d days."),
                "contacts.payment_term.days",
                max=TERM_DAYS_MAX,
            )
        if self.discount_pct < 0 or self.discount_pct >= 100:
            add(
                "discount_pct",
                _("A discount is from 0 to 99.99 %."),
                "contacts.payment_term.discount_range",
            )
        elif self.discount_pct > 0:
            if self.discount_days < 1:
                add(
                    "discount_days",
                    _("Say within how many days the discount applies."),
                    "contacts.payment_term.discount_days_required",
                )
            elif (
                self.terms_type == TermsType.DAYS_AFTER_DOCUMENT and self.discount_days >= self.days
            ):
                add(
                    "discount_days",
                    _("The discount window must end before the payment is due (%(days)d days)."),
                    "contacts.payment_term.discount_window",
                    days=self.days,
                )
        elif self.discount_days:
            self.discount_days = 0  # no discount, no window
        if self.late_interest_pct < 0 or self.late_interest_pct > 100:
            add(
                "late_interest_pct",
                _("Late interest is from 0 to 100 % a year."),
                "contacts.payment_term.interest_range",
            )
        if errors:
            raise ValidationError(errors)

    def _name_taken(self, name: str) -> bool:
        others = PaymentTerm._base_manager.filter(
            organisation_id=self.organisation_id, deleted_at__isnull=True
        ).exclude(pk=self.pk)
        return any(o.name_in(SOURCE_LANGUAGE).lower() == name.lower() for o in others)

    def save(self, *args: Any, **kwargs: Any) -> None:
        update_fields = kwargs.get("update_fields")
        if update_fields is None or set(update_fields) - {
            "status",
            "updated_at",
            "deleted_at",
            "position",
        }:
            errors: dict[str, Any] = {}
            try:
                self.clean_fields(exclude=["organisation", "created_by", "public_id", "name_i18n"])
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            try:
                self.clean()
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            if errors:
                raise ValidationError(errors)
        super().save(*args, **kwargs)

    def archive(self) -> None:
        if self.status != ContactStatus.ARCHIVED:
            self.status = ContactStatus.ARCHIVED
            self.save(update_fields=["status", "updated_at"])

    def unarchive(self) -> None:
        if self.status != ContactStatus.ACTIVE:
            self.status = ContactStatus.ACTIVE
            self.save(update_fields=["status", "updated_at"])


#: The terms every new organisation starts with: (code, English name, type, days, discount %,
#: discount days). French names arrive with Phase 6.
DEFAULT_TERMS: tuple[tuple[str, str, str, int, str, int], ...] = (
    ("due_on_receipt", "Due on receipt", TermsType.DAYS_AFTER_DOCUMENT, 0, "0", 0),
    ("net_15", "Net 15", TermsType.DAYS_AFTER_DOCUMENT, 15, "0", 0),
    ("net_30", "Net 30", TermsType.DAYS_AFTER_DOCUMENT, 30, "0", 0),
    ("net_60", "Net 60", TermsType.DAYS_AFTER_DOCUMENT, 60, "0", 0),
    ("2_10_net_30", "2/10 net 30", TermsType.DAYS_AFTER_DOCUMENT, 30, "2", 10),
    ("eom", "End of month (EOM)", TermsType.DAYS_AFTER_MONTH_END, 0, "0", 0),
)


def seed_payment_terms(organisation: Any, model: Any = None) -> int:
    """Create the default terms an organisation lacks (by ``code``); returns how many were made.

    Defaults are written as one bulk insert by the platform (no audit event per row, like the
    numbering allocations): they are part of creating the organisation, not someone's change.
    ``model`` lets a data migration pass its historical model.
    """
    model = model or PaymentTerm
    existing = set(
        model._base_manager.filter(organisation_id=organisation.pk).values_list("code", flat=True)
    )
    rows = [
        model(
            organisation_id=organisation.pk,
            code=code,
            name_i18n={SOURCE_LANGUAGE: name},
            terms_type=terms_type,
            days=days,
            discount_pct=Decimal(discount),
            discount_days=discount_days,
            position=position,
        )
        for position, (code, name, terms_type, days, discount, discount_days) in enumerate(
            DEFAULT_TERMS
        )
        if code not in existing
    ]
    model._base_manager.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


# ---- exemption certificates (B-01-T08) ---------------------------------------------------------

#: A reminder goes out this many days before a certificate expires (and again once it has).
EXEMPTION_REMINDER_DAYS = 30
EXEMPTION_NUMBER_MAX = 60


class ExemptionState(models.TextChoices):
    VALID = "valid", _("Valid")
    EXPIRING = "expiring", _("Expires soon")
    EXPIRED = "expired", _("Expired")


def organisation_today(organisation: Any, now: Any = None) -> date:
    """Today's date where the organisation is (its time zone), not the server's."""
    zone = zoneinfo.ZoneInfo(getattr(organisation, "time_zone", "") or DEFAULT_TIME_ZONE)
    moment = now or timezone.now()
    day: date = moment.astimezone(zone).date()
    return day


class ExemptionCertificate(AuditedModel, OrgOwnedModel):
    """A sales-tax exemption certificate a contact gave the organisation (B-01-T08, gap-20).

    Xero keeps no exemption certificate on a contact (teardown §3.2): a customer exempt from PST
    or QST (a reseller, a First Nations band, a farmer…) is handled with a tax rate and the paper
    lives elsewhere. Numo9 records it on the contact:

    - ``number`` — the certificate or exemption number as printed (required; one certificate per
      number on a contact);
    - ``document`` — the scanned certificate, a document of the organisation's file store (A-06):
      never a quarantined file;
    - ``issued_on`` / ``expires_on`` — empty ``expires_on`` = no expiry date on the certificate;
      an expiry date is never before the issue date;
    - ``state(on)`` — ``valid``, ``expiring`` (within ``EXEMPTION_REMINDER_DAYS`` of the expiry
      date) or ``expired`` (the day after ``expires_on``, in the organisation's time zone). An
      expired certificate is flagged everywhere it is shown; the tax engine (G-02) stops applying
      it from that day;
    - ``reminded_state`` / ``reminded_for`` — which reminder the daily job (``exemptions.py``)
      already sent for which expiry date, so each reminder goes out once; renewing the certificate
      (a new expiry date) starts again.

    Removing a certificate is a soft delete (the audit log keeps it).
    """

    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="exemption_certificates",
        verbose_name=_("contact"),
    )
    number = models.CharField(_("certificate number"), max_length=EXEMPTION_NUMBER_MAX, blank=True)
    document = models.ForeignKey(
        "files.Document",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("certificate file"),
    )
    issued_on = models.DateField(_("issued on"), null=True, blank=True)
    expires_on = models.DateField(
        _("expires on"),
        null=True,
        blank=True,
        help_text=_("Leave empty when the certificate has no expiry date."),
    )
    notes = models.CharField(_("notes"), max_length=500, blank=True)
    reminded_state = models.CharField(_("reminder sent"), max_length=10, blank=True, editable=False)
    reminded_for = models.DateField(
        _("reminder sent for expiry date"), null=True, blank=True, editable=False
    )

    class Meta:
        ordering = ("-expires_on", "-id")
        verbose_name = _("exemption certificate")
        verbose_name_plural = _("exemption certificates")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                Lower("number"),
                "contact",
                condition=models.Q(deleted_at__isnull=True),
                name="contacts_exemption_number_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(number=""), name="contacts_exemption_number_required"
            ),
            models.CheckConstraint(
                condition=models.Q(issued_on__isnull=True)
                | models.Q(expires_on__isnull=True)
                | models.Q(expires_on__gte=models.F("issued_on")),
                name="contacts_exemption_dates_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(reminded_state="")
                | models.Q(reminded_state__in=ExemptionState.values),
                name="contacts_exemption_reminded_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "contact"), name="contacts_exemption_contact_idx"),
            models.Index(fields=("expires_on",), name="contacts_exemption_expiry_idx"),
        ]

    def __str__(self) -> str:
        return self.number

    def audit_label(self) -> str:
        name = self.contact.display_name if self.contact_id else ""
        return f"{self.number} · {name}" if name else self.number

    def state(self, on: date | None = None) -> str:
        """``valid``, ``expiring`` or ``expired`` on ``on`` (default: today in the organisation)."""
        if self.expires_on is None:
            return ExemptionState.VALID
        today = on or organisation_today(self.organisation)
        if today > self.expires_on:
            return ExemptionState.EXPIRED
        if (self.expires_on - today).days <= EXEMPTION_REMINDER_DAYS:
            return ExemptionState.EXPIRING
        return ExemptionState.VALID

    def is_expired(self, on: date | None = None) -> bool:
        return self.state(on) == ExemptionState.EXPIRED

    def days_left(self, on: date | None = None) -> int | None:
        """Days until the expiry date (negative once expired); None without an expiry date."""
        if self.expires_on is None:
            return None
        return (self.expires_on - (on or organisation_today(self.organisation))).days

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}

        def add(field: str, message: Any, code: str, **params: Any) -> None:
            errors.setdefault(field, []).append(ValidationError(message, code=code, params=params))

        if not self.number:
            add("number", _("Enter the certificate number."), "contacts.exemption.number_required")
        elif self._number_taken():
            add(
                "number",
                _("This contact already has certificate %(number)s."),
                "contacts.exemption.number_taken",
                number=self.number,
            )
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            add(
                "expires_on",
                _("The expiry date can't be before the issue date."),
                "contacts.exemption.expiry_before_issue",
            )
        if self.contact_id and self.contact.organisation_id != self.organisation_id:
            add(
                "contact", _("Choose a contact of this organisation."), "contacts.exemption.contact"
            )
        if self.document_id is not None:
            from numo9.files.models import DocumentStatus

            document = self.document
            if document is None or document.organisation_id != self.organisation_id:
                add(
                    "document",
                    _("Choose a document of this organisation."),
                    "contacts.exemption.document",
                )
            elif document.deleted_at is not None:
                add(
                    "document",
                    _("This document was deleted: upload the certificate again."),
                    "contacts.exemption.document_deleted",
                )
            elif document.status == DocumentStatus.INFECTED:
                add(
                    "document",
                    _("%(name)s is quarantined (virus found): upload a clean copy."),
                    "contacts.exemption.document_quarantined",
                    name=document.name,
                )
        if errors:
            raise ValidationError(errors)

    def _number_taken(self) -> bool:
        return (
            ExemptionCertificate._base_manager.filter(
                contact_id=self.contact_id, number__iexact=self.number, deleted_at__isnull=True
            )
            .exclude(pk=self.pk)
            .exists()
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.contact_id and not self.organisation_id:
            self.organisation_id = self.contact.organisation_id
        self.number = " ".join((self.number or "").split())
        self.notes = " ".join((self.notes or "").split())
        update_fields = kwargs.get("update_fields")
        if update_fields is None or set(update_fields) - {
            "deleted_at",
            "updated_at",
            "reminded_state",
            "reminded_for",
        }:
            errors: dict[str, Any] = {}
            try:
                self.clean_fields(
                    exclude=["organisation", "contact", "document", "created_by", "public_id"]
                )
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            try:
                self.clean()
            except ValidationError as error:
                errors = error.update_error_dict(errors)
            if errors:
                raise ValidationError(errors)
        if self.reminded_for is not None and self.reminded_for != self.expires_on:
            # Renewed (new expiry date) or expiry removed: the next reminder is due afresh.
            self.reminded_state, self.reminded_for = "", None
            if update_fields is not None:
                kwargs["update_fields"] = [*update_fields, "reminded_state", "reminded_for"]
        super().save(*args, **kwargs)


class CreditOverrideStatus(models.TextChoices):
    PENDING = "pending", _("Waiting for approval")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Declined")
    USED = "used", _("Used")


#: Days an override request (and an approval not yet used) stays valid.
CREDIT_OVERRIDE_DAYS = 7


class CreditOverride(AuditedModel, OrgOwnedModel):
    """A request to go over a customer's credit limit, and its decision (B-01-T13, gap-20).

    When a contact's ``credit_mode`` is ``block`` and a document would take what the contact owes
    over its ``credit_limit``, the document can only be saved with an **approved override**
    (``numo9.contacts.credit``):

    - ``amount`` — the document total asked for (the contact's currency); ``exposure`` and
      ``limit`` — what the contact owed and its limit when the request was made;
    - ``document_type`` / ``document_ref`` — the document it is for (``invoice`` and the invoice's
      id, …); an approval only covers that document, up to that amount;
    - ``created_by`` — who asked; ``decided_by`` — who approved or declined: someone holding
      ``contacts.credit_limit.override``, never the requester;
    - ``status`` — waiting → approved or declined; an approval is **used once** (``used_at``);
      a request or an unused approval expires after ``CREDIT_OVERRIDE_DAYS`` (``expires_at``).
    """

    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="credit_overrides",
        verbose_name=_("contact"),
    )
    amount = models.DecimalField(_("amount"), max_digits=18, decimal_places=2)
    exposure = models.DecimalField(_("owed when requested"), max_digits=18, decimal_places=2)
    limit = models.DecimalField(_("credit limit"), max_digits=18, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default=DEFAULT_CURRENCY)
    document_type = models.CharField(_("document type"), max_length=40)
    document_ref = models.CharField(_("document"), max_length=64, blank=True)
    reason = models.CharField(_("reason"), max_length=500)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=CreditOverrideStatus.choices,
        default=CreditOverrideStatus.PENDING,
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("decided by"),
    )
    decided_at = models.DateTimeField(_("decided at"), null=True, blank=True)
    decision_note = models.CharField(_("note"), max_length=500, blank=True)
    expires_at = models.DateTimeField(_("expires at"))
    used_at = models.DateTimeField(_("used at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("credit limit override")
        verbose_name_plural = _("credit limit overrides")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="contacts_credit_override_amount_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="contacts_credit_override_reason_required"
            ),
            models.CheckConstraint(
                condition=_in("status", CreditOverrideStatus),
                name="contacts_credit_override_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["contact", "status"], name="contacts_credit_override_open"),
        ]

    def __str__(self) -> str:
        return f"{self.contact} {self.amount} ({self.status})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.contact_id and not self.organisation_id:
            self.organisation_id = self.contact.organisation_id
        self.reason = " ".join((self.reason or "").split())
        self.decision_note = " ".join((self.decision_note or "").split())
        super().save(*args, **kwargs)


# ---- statements sent (B-02-T06) ----------------------------------------------------------------


class StatementSendKind(models.TextChoices):
    OUTSTANDING = "outstanding", _("Outstanding")
    ACTIVITY = "activity", _("Activity")


class StatementSend(OrgOwnedModel):
    """A statement sent to a contact by email (B-02-T06) — the contact's statement history.

    What was sent stays as it was: kind and dates, the amount due and currency, the recipients,
    the language, the PDF (``file_key``: the organisation's object storage, A-06) and the email
    messages (A-07 message log, by public id). Never edited after sending.
    """

    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="statements_sent",
        verbose_name=_("contact"),
    )
    kind = models.CharField(_("type"), max_length=12, choices=StatementSendKind.choices)
    as_at = models.DateField(_("as at"))
    period_start = models.DateField(_("period start"), null=True, blank=True)
    amount_due = models.DecimalField(_("amount due"), max_digits=18, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default=DEFAULT_CURRENCY)
    language = models.CharField(_("language"), max_length=5, choices=Locale.choices)
    recipients = models.JSONField(_("sent to"), default=list)
    subject = models.CharField(_("subject"), max_length=998)
    file_key = models.CharField(_("file"), max_length=512)
    file_name = models.CharField(_("file name"), max_length=255)
    email_messages = models.JSONField(_("email messages"), default=list, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("sent by"),
    )
    sent_at = models.DateTimeField(_("sent at"), default=timezone.now)

    class Meta:
        ordering = ("-sent_at", "-pk")
        verbose_name = _("statement sent")
        verbose_name_plural = _("statements sent")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=_in("kind", StatementSendKind), name="contacts_statement_send_kind_valid"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "contact", "-sent_at"), name="contacts_stmt_sent_idx"
            )
        ]

    def __str__(self) -> str:
        return f"{self.contact} · {self.kind} {self.as_at:%Y-%m-%d}"


# ---- supplier statements (B-02-T07) ------------------------------------------------------------


class SupplierStatementSource(models.TextChoices):
    FILE = "file", _("Imported file")
    MANUAL = "manual", _("Typed in")


class SupplierStatement(OrgOwnedModel):
    """A statement a supplier sent us (B-02-T07): their lines, to reconcile against our bills
    (B-02-T08). Imported from CSV/XLSX with a column mapping, or typed in."""

    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="supplier_statements",
        verbose_name=_("supplier"),
    )
    statement_date = models.DateField(_("statement date"))
    their_balance = models.DecimalField(
        _("their balance"), max_digits=18, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(_("currency"), max_length=3, default=DEFAULT_CURRENCY)
    source = models.CharField(_("source"), max_length=8, choices=SupplierStatementSource.choices)
    file_name = models.CharField(_("file name"), max_length=255, blank=True)
    columns = models.JSONField(
        _("column mapping"), default=dict, blank=True, help_text=_("File header → line field.")
    )

    class Meta:
        ordering = ("-statement_date", "-pk")
        verbose_name = _("supplier statement")
        verbose_name_plural = _("supplier statements")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=_in("source", SupplierStatementSource),
                name="contacts_supplier_statement_source_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.contact} · {self.statement_date:%Y-%m-%d}"


class SupplierStatementLine(OrgOwnedModel):
    """One line of a supplier's statement: their document, its date and amount (positive: we
    owe it; negative: their credit or our payment)."""

    statement = models.ForeignKey(
        SupplierStatement,
        on_delete=models.CASCADE,  # the lines are the statement's content
        related_name="lines",
        verbose_name=_("supplier statement"),
    )
    position = models.PositiveIntegerField(_("position"))
    date = models.DateField(_("date"))
    invoice_number = models.CharField(_("invoice number"), max_length=100, blank=True)
    reference = models.CharField(_("reference"), max_length=200, blank=True)
    description = models.CharField(_("description"), max_length=500, blank=True)
    amount = models.DecimalField(_("amount"), max_digits=18, decimal_places=2)
    source_row = models.PositiveIntegerField(_("file row"), null=True, blank=True)
    note = models.CharField(_("note"), max_length=500, blank=True)
    # Reconciliation (B-02-T08/T12): a document of ours matched by hand ("" = automatic matching).
    manual_ref = models.CharField(
        _("matched by hand to"), max_length=100, blank=True, db_default="", default=""
    )

    class Meta:
        ordering = ("statement", "position")
        verbose_name = _("supplier statement line")
        verbose_name_plural = _("supplier statement lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("statement", "position"), name="contacts_supplier_line_position_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice_number or self.reference} {self.amount}"


# ---- contact activity timeline (B-02-T02) --------------------------------------------------------


class ActivityType(models.TextChoices):
    INVOICE = "invoice", _("Invoice")
    CREDIT_NOTE = "credit_note", _("Credit note")
    BILL = "bill", _("Bill")
    PAYMENT = "payment", _("Payment")
    STATEMENT = "statement", _("Statement sent")
    EMAIL = "email", _("Email")
    NOTE = "note", _("Note")
    CHANGE = "change", _("Contact changed")


class ActivityEvent(OrgOwnedModel):
    """One thing that happened with a contact, for its Activity tab (B-02-T02).

    Written by modules through ``numo9.contacts.activity.emit`` (documents and payments from
    Phase 1, statements sent, notes); read newest first. ``ref_type``/``ref_id`` point at the record
    (an invoice, a statement send), ``amount`` is in the contact's currency (empty for notes and
    changes). Kept on merge: a merged contact's events move to the surviving contact (B-01-T12).
    """

    contact = models.ForeignKey(
        Contact, on_delete=models.PROTECT, related_name="activity", verbose_name=_("contact")
    )
    type = models.CharField(_("type"), max_length=20, choices=ActivityType.choices)
    title = models.CharField(_("what"), max_length=300)
    ref_type = models.CharField(_("record type"), max_length=60, blank=True)
    ref_id = models.CharField(_("record"), max_length=64, blank=True)
    amount = models.DecimalField(
        _("amount"), max_digits=18, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(_("currency"), max_length=3, blank=True)
    occurred_at = models.DateTimeField(_("when"))
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("by"),
    )
    actor_label = models.CharField(_("by"), max_length=300, blank=True)
    meta = models.JSONField(_("details"), default=dict, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        verbose_name = _("contact activity")
        verbose_name_plural = _("contact activity")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("organisation", "contact", "-occurred_at"), name="contacts_activity_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.contact_id} {self.type} {self.occurred_at:%Y-%m-%d}"


class StatementRunStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    RUNNING = "running", _("Sending")
    DONE = "done", _("Sent")
    FAILED = "failed", _("Failed")


class StatementRun(AuditedModel, OrgOwnedModel):
    """A bulk statement run (D-07-T08): one statement of ``kind`` (outstanding as at ``as_at``,
    or activity from ``period_start`` to ``as_at``) for each chosen contact — ``contacts`` (public
    ids) or, when empty, every customer with a balance whose statement preference is email —
    emailed as a PDF (B-02). ``results`` keeps, per contact, what happened: ``sent`` (with the
    ``StatementSend``), ``skipped`` (no balance, no one to email, statements off) or ``failed``."""

    kind = models.CharField(_("type"), max_length=12, choices=StatementSendKind.choices)
    as_at = models.DateField(_("as at"))
    period_start = models.DateField(_("period start"), null=True, blank=True)
    contacts = models.JSONField(_("contacts"), default=list, blank=True)
    include_zero = models.BooleanField(_("include contacts with no balance"), default=False)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=StatementRunStatus.choices,
        default=StatementRunStatus.DRAFT,
    )
    results = models.JSONField(_("results"), default=list, blank=True)
    sent_count = models.PositiveIntegerField(_("sent"), default=0)
    skipped_count = models.PositiveIntegerField(_("skipped"), default=0)
    failed_count = models.PositiveIntegerField(_("failed"), default=0)
    job_run = models.ForeignKey(
        "jobs.JobRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("background job"),
    )
    run_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("run by"),
    )
    run_at = models.DateTimeField(_("run at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = _("statement run")
        verbose_name_plural = _("statement runs")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(kind__in=StatementSendKind.values),
                name="contacts_statementrun_kind_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind=StatementSendKind.ACTIVITY)
                | (
                    models.Q(period_start__isnull=False)
                    & models.Q(period_start__lte=models.F("as_at"))
                ),
                name="contacts_statementrun_activity_period",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=StatementRunStatus.values),
                name="contacts_statementrun_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.as_at:%Y-%m-%d}"
