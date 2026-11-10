"""Tenancy models (A-01-T01).

Two tenant levels:

- ``Practice`` — an accounting firm or a sole accountant. Always free. Its staff are
  ``PracticeMember`` rows (one practice role each).
- ``Organisation`` — the paying business whose books live in Numo9. Its own users are
  ``OrganisationMember`` rows (one organisation role each).
- ``PracticeAssignment`` links a practice to an organisation it serves. An organisation can have
  zero practices (self-managed), one, or several (e.g. a bookkeeper and a tax accountant), but a
  practice is assigned to a given organisation at most once. ``assigned_staff`` names the practice
  members who work on that organisation; ``active`` switches the whole assignment off without
  losing its history.

These are platform models, not organisation-owned business records, so they do not inherit
``OrgOwnedModel`` (A-01-T02) and are allow-listed by the A-01-T08 check. Who may access what is
decided by the resolver in A-01-T05; permissions per role arrive with A-03.

Rows are never cascade-deleted: deleting a practice, organisation or user that still has
memberships or assignments is refused (records are kept for the CRA six-year period).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
import zoneinfo
from datetime import timedelta
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.accounts.models import Locale, normalise_email

from .managers import OrgScopedManager

DEFAULT_TIME_ZONE = "America/Toronto"


def validate_time_zone(value: str) -> None:
    if value not in zoneinfo.available_timezones():
        raise ValidationError(
            _("%(value)s is not a valid time zone."),
            code="invalid_time_zone",
            params={"value": value},
        )


def _in_choices(field: str, choices: type[models.TextChoices]) -> models.Q:
    return models.Q(**{f"{field}__in": choices.values})


class PracticeRole(models.TextChoices):
    """System practice roles (A-03 adds custom roles and their permissions)."""

    PRACTICE_ADMIN = "practice_admin", _("Practice admin")
    ACCOUNTANT = "accountant", _("Accountant")
    REVIEWER = "reviewer", _("Reviewer")
    PAYROLL_SPECIALIST = "payroll_specialist", _("Payroll specialist")
    READ_ONLY = "read_only", _("Read-only staff")


class OrganisationRole(models.TextChoices):
    """System organisation roles (A-03 adds custom roles and their permissions)."""

    OWNER = "owner", _("Owner")
    ADMIN = "admin", _("Admin")
    ACCOUNTANT_DELEGATE = "accountant_delegate", _("Accountant delegate")
    SALES = "sales", _("Sales")
    PURCHASING = "purchasing", _("Purchasing")
    PAYROLL = "payroll", _("Payroll")
    HR = "hr", _("HR")
    EMPLOYEE = "employee", _("Employee")


class OrganisationStatus(models.TextChoices):
    """Commercial life-cycle; transitions are driven by billing (U-03…U-05) and demo (U-07)."""

    DEMO = "demo", _("Demo")
    TRIAL = "trial", _("Trial")
    ACTIVE = "active", _("Active")
    GRACE = "grace", _("Grace period")
    READ_ONLY = "read_only", _("Read-only")
    CANCELLED = "cancelled", _("Cancelled")


class AssignmentRole(models.TextChoices):
    """What the practice does for the organisation (e.g. bookkeeper + tax accountant)."""

    FULL_SERVICE = "full_service", _("Full service")
    BOOKKEEPING = "bookkeeping", _("Bookkeeping")
    TAX = "tax", _("Tax")
    PAYROLL = "payroll", _("Payroll")


class Practice(models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(_("name"), max_length=200)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("practice")
        verbose_name_plural = _("practices")

    def __str__(self) -> str:
        return self.name


class PracticeMember(models.Model):
    practice = models.ForeignKey(
        Practice, on_delete=models.PROTECT, related_name="members", verbose_name=_("practice")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="practice_memberships",
        verbose_name=_("user"),
    )
    role = models.CharField(_("role"), max_length=32, choices=PracticeRole.choices)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("practice member")
        verbose_name_plural = _("practice members")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["practice", "user"], name="tenancy_practicemember_unique_practice_user"
            ),
            models.CheckConstraint(
                condition=_in_choices("role", PracticeRole),
                name="tenancy_practicemember_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.practice} ({self.role})"


class Organisation(models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(_("name"), max_length=200)
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=OrganisationStatus.choices,
        default=OrganisationStatus.TRIAL,
    )
    time_zone = models.CharField(
        _("time zone"),
        max_length=64,
        default=DEFAULT_TIME_ZONE,
        validators=[validate_time_zone],
    )
    # Default language of the organisation's own output (emails, documents) when no user's
    # preference applies (A-10-T14; per-contact document language arrives in X-02).
    locale = models.CharField(
        _("language"),
        max_length=5,
        choices=Locale.choices,
        default=Locale.EN_CA,
        db_default=Locale.EN_CA,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("organisation")
        verbose_name_plural = _("organisations")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=_in_choices("status", OrganisationStatus),
                name="tenancy_organisation_status_valid",
            ),
            models.CheckConstraint(
                condition=_in_choices("locale", Locale),
                name="tenancy_organisation_locale_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class OrganisationMember(models.Model):
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="members",
        verbose_name=_("organisation"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organisation_memberships",
        verbose_name=_("user"),
    )
    role = models.CharField(_("role"), max_length=32, choices=OrganisationRole.choices)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("organisation member")
        verbose_name_plural = _("organisation members")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "user"],
                name="tenancy_organisationmember_unique_organisation_user",
            ),
            models.CheckConstraint(
                condition=_in_choices("role", OrganisationRole),
                name="tenancy_organisationmember_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organisation} ({self.role})"


class PracticeAssignment(models.Model):
    practice = models.ForeignKey(
        Practice, on_delete=models.PROTECT, related_name="assignments", verbose_name=_("practice")
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="practice_assignments",
        verbose_name=_("organisation"),
    )
    assigned_staff = models.ManyToManyField(
        PracticeMember,
        blank=True,
        related_name="assignments",
        verbose_name=_("assigned staff"),
    )
    role = models.CharField(
        _("role"),
        max_length=32,
        choices=AssignmentRole.choices,
        default=AssignmentRole.FULL_SERVICE,
    )
    active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("practice assignment")
        verbose_name_plural = _("practice assignments")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["practice", "organisation"],
                name="tenancy_practiceassignment_unique_practice_organisation",
            ),
            models.CheckConstraint(
                condition=_in_choices("role", AssignmentRole),
                name="tenancy_practiceassignment_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.practice} → {self.organisation} ({self.role})"


@receiver(m2m_changed, sender=PracticeAssignment.assigned_staff.through)
def _staff_must_belong_to_the_assigned_practice(
    sender: Any,
    instance: PracticeAssignment | PracticeMember,
    action: str,
    reverse: bool,
    pk_set: set[int] | None,
    **kwargs: Any,
) -> None:
    """Only members of the assignment's own practice can be assigned to its organisation."""
    if action != "pre_add" or not pk_set:
        return
    if reverse and isinstance(instance, PracticeMember):  # member.assignments.add(assignment)
        mismatch = (
            PracticeAssignment.objects.filter(pk__in=pk_set)
            .exclude(practice_id=instance.practice_id)
            .exists()
        )
    elif not reverse and isinstance(instance, PracticeAssignment):  # assigned_staff.add(member)
        mismatch = (
            PracticeMember.objects.filter(pk__in=pk_set)
            .exclude(practice_id=instance.practice_id)
            .exists()
        )
    else:
        return
    if mismatch:
        raise ValidationError(
            _("Assigned staff must be members of the assigned practice."),
            code="staff_not_in_practice",
        )


class OrgOwnedModel(models.Model):
    """Abstract base for every business record (A-01-T02).

    Every row belongs to exactly one organisation and carries:

    - ``organisation`` — the owning tenant (required, never cascade-deleted);
    - ``public_id`` — random UUID used in URLs and APIs instead of the sequential primary key;
    - ``created_by`` — the user who created the row (empty for system processes such as imports,
      seeders and scheduled jobs);
    - ``created_at`` / ``updated_at`` — set automatically;
    - ``deleted_at`` — soft delete: records are never removed (CRA six-year retention); use
      ``soft_delete()`` / ``restore()``.

    ``objects`` is an ``OrgScopedManager`` (A-01-T04): every query is limited to the active
    organisation and fails without one; ``objects.unscoped(reason=...)`` is the logged way out.
    The A-01-T08 check makes inheriting this class mandatory for business models.
    """

    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.PROTECT,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("organisation"),
    )
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True, editable=False)

    objects: ClassVar[OrgScopedManager[Any]] = OrgScopedManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the row deleted (idempotent: the first deletion time is kept)."""
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self) -> None:
        if self.deleted_at is not None:
            self.deleted_at = None
            self.save(update_fields=["deleted_at", "updated_at"])


# ---- Invitations (A-02-T08) ---------------------------------------------------------------------

INVITATION_TTL = timedelta(days=7)


class InvitationKind(models.TextChoices):
    """The four invitation flows (A-02 business rules)."""

    PRACTICE_STAFF = "practice_staff", _("Practice invites a staff member")
    ORGANISATION_OWNER = "organisation_owner", _("Practice invites the organisation's owner")
    ORGANISATION_USER = "organisation_user", _("Organisation invites a user")
    ORGANISATION_ACCOUNTANT = "organisation_accountant", _("Organisation invites its accountant")


class InvitationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    ACCEPTED = "accepted", _("Accepted")
    REVOKED = "revoked", _("Revoked")
    EXPIRED = "expired", _("Expired")


def hash_token(token: str) -> str:
    """Invitation links carry a random token; only its SHA-256 is stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> tuple[str, str]:
    """A fresh (token, token_hash) pair: 256 random bits, URL-safe."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def _pending() -> models.Q:
    return models.Q(accepted_at__isnull=True, revoked_at__isnull=True)


def _role_rule(kind: str, roles: type[models.TextChoices] | list[str]) -> models.Q:
    values = roles if isinstance(roles, list) else roles.values
    return models.Q(kind=kind, role__in=values)


class Invitation(models.Model):
    """An emailed, single-use invitation to join a practice or an organisation.

    - ``practice_staff``: target ``practice``; ``role`` is a practice role.
    - ``organisation_owner``: target ``organisation`` (a client the inviting practice created);
      ``role`` is ``owner``.
    - ``organisation_user``: target ``organisation``; ``role`` is an organisation role.
    - ``organisation_accountant``: target ``organisation``; ``role`` is what the accountant's
      practice will do for it (an assignment role).

    The link token is never stored — only ``token_hash``. At most one *pending* invitation exists
    per email address and target (database constraint); accepting or revoking it frees the slot.
    Expiry (7 days) is checked by the service (A-02-T09), not by the constraint.
    """

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    kind = models.CharField(_("type"), max_length=32, choices=InvitationKind.choices)
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="invitations_sent",
        verbose_name=_("invited by"),
    )
    practice = models.ForeignKey(
        "tenancy.Practice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invitations",
        verbose_name=_("practice"),
    )
    organisation = models.ForeignKey(
        "tenancy.Organisation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invitations",
        verbose_name=_("organisation"),
    )
    role = models.CharField(_("role"), max_length=32)
    email = models.EmailField(_("email address"), max_length=254)
    token_hash = models.CharField(_("token hash"), max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField(_("expires at"))
    accepted_at = models.DateTimeField(_("accepted at"), null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invitations_accepted",
        verbose_name=_("accepted by"),
    )
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    send_count = models.PositiveSmallIntegerField(_("times sent"), default=0)
    last_sent_at = models.DateTimeField(_("last sent at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["email", "practice"],
                condition=_pending() & models.Q(practice__isnull=False),
                name="tenancy_invitation_one_pending_per_email_practice",
            ),
            models.UniqueConstraint(
                fields=["email", "organisation"],
                condition=_pending() & models.Q(organisation__isnull=False),
                name="tenancy_invitation_one_pending_per_email_organisation",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind=InvitationKind.PRACTICE_STAFF,
                        practice__isnull=False,
                        organisation__isnull=True,
                    )
                    | (
                        ~models.Q(kind=InvitationKind.PRACTICE_STAFF)
                        & models.Q(
                            kind__in=InvitationKind.values,
                            organisation__isnull=False,
                            practice__isnull=True,
                        )
                    )
                ),
                name="tenancy_invitation_target_matches_kind",
            ),
            models.CheckConstraint(
                condition=(
                    _role_rule(InvitationKind.PRACTICE_STAFF, PracticeRole)
                    | _role_rule(InvitationKind.ORGANISATION_OWNER, [OrganisationRole.OWNER])
                    | _role_rule(InvitationKind.ORGANISATION_USER, OrganisationRole)
                    | _role_rule(InvitationKind.ORGANISATION_ACCOUNTANT, AssignmentRole)
                ),
                name="tenancy_invitation_role_matches_kind",
            ),
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")),
                name="tenancy_invitation_email_lowercase",
            ),
            models.CheckConstraint(
                condition=~(
                    models.Q(accepted_at__isnull=False) & models.Q(revoked_at__isnull=False)
                ),
                name="tenancy_invitation_not_accepted_and_revoked",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["email"], name="tenancy_invitation_email_idx"),
        ]

    def __str__(self) -> str:
        target = self.practice or self.organisation
        return f"{self.email} → {target} ({self.kind}, {self.role})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = normalise_email(self.email)
        super().save(*args, **kwargs)

    @property
    def status(self) -> str:
        if self.accepted_at is not None:
            return InvitationStatus.ACCEPTED
        if self.revoked_at is not None:
            return InvitationStatus.REVOKED
        if self.expires_at <= timezone.now():
            return InvitationStatus.EXPIRED
        return InvitationStatus.PENDING

    @property
    def is_pending(self) -> bool:
        return self.status == InvitationStatus.PENDING

    @property
    def target(self) -> Any:
        return self.practice if self.kind == InvitationKind.PRACTICE_STAFF else self.organisation

    @classmethod
    def find_by_token(cls, token: str) -> Invitation | None:
        return cls.objects.filter(token_hash=hash_token(token)).first()
