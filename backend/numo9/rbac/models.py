"""Roles, role permissions, role assignments and approval limits (A-03-T02).

- ``Role`` — a named set of permissions at one scope: ``platform`` (Numo9 staff), ``practice``
  or ``organisation``. **System roles** (``is_system``) are defined by Numo9 and seeded by
  migration (A-03-T03); they belong to no tenant and are not editable. **Custom roles** belong to
  one organisation (organisation scope) or one practice (practice scope); platform roles are
  always system roles.
- ``RolePermission`` — one permission key of the catalogue (A-03-T01) granted by a role. Keys
  are stored as text: the catalogue lives in code.
- ``RoleAssignment`` — a role given to a user in an organisation, a practice, or (platform
  roles) everywhere. The role that comes with a membership (``OrganisationMember.role``,
  ``PracticeMember.role``) is the system role with that key — it is not duplicated here;
  assignments add further roles, typically custom ones (A-03-T04 takes the union).
- ``ApprovalLimit`` — the highest amount (CAD) a user, or everyone holding a role, may approve
  for a document type in one organisation (A-03-T07 enforces it).

``Role``, ``RolePermission`` and ``RoleAssignment`` are platform models (tenancy allow-list):
system roles have no organisation, and custom roles name an organisation without holding its
business data. ``ApprovalLimit`` is an organisation's record: an ``OrgOwnedModel``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import OrgOwnedModel

from .catalogue import Scope, UnknownPermission, catalogue


class RoleScope(models.TextChoices):
    PLATFORM = Scope.PLATFORM.value, _("Platform")
    PRACTICE = Scope.PRACTICE.value, _("Practice")
    ORGANISATION = Scope.ORGANISATION.value, _("Organisation")


#: Permission scopes a role of each scope may grant: practice roles grant organisation
#: permissions in the organisations their practice serves (A-03-T04).
GRANTABLE_SCOPES: dict[str, frozenset[str]] = {
    RoleScope.PLATFORM: frozenset({Scope.PLATFORM.value}),
    RoleScope.PRACTICE: frozenset({Scope.PRACTICE.value, Scope.ORGANISATION.value}),
    RoleScope.ORGANISATION: frozenset({Scope.ORGANISATION.value}),
}


class Role(models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    scope = models.CharField(_("scope"), max_length=16, choices=RoleScope.choices)
    key = models.SlugField(
        _("key"),
        max_length=50,
        blank=True,
        help_text=_("System roles: stable identifier, e.g. 'owner'. Empty for custom roles."),
    )
    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    is_system = models.BooleanField(_("system role"), default=False)
    organisation = models.ForeignKey(
        "tenancy.Organisation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custom_roles",
        verbose_name=_("organisation"),
    )
    practice = models.ForeignKey(
        "tenancy.Practice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custom_roles",
        verbose_name=_("practice"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ("scope", "-is_system", "name")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            # System roles belong to no tenant and have a key; custom roles have no key.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        is_system=True,
                        organisation__isnull=True,
                        practice__isnull=True,
                    )
                    & ~models.Q(key="")
                )
                | models.Q(is_system=False, key=""),
                name="rbac_role_system_shape",
            ),
            # Custom roles: an organisation role belongs to an organisation, a practice role to a
            # practice; there are no custom platform roles.
            models.CheckConstraint(
                condition=models.Q(is_system=True)
                | models.Q(scope="organisation", organisation__isnull=False, practice__isnull=True)
                | models.Q(scope="practice", practice__isnull=False, organisation__isnull=True),
                name="rbac_role_custom_owner",
            ),
            models.UniqueConstraint(
                fields=["scope", "key"],
                condition=models.Q(is_system=True),
                name="rbac_role_unique_system_key",
            ),
            models.UniqueConstraint(
                "organisation",
                Lower("name"),
                condition=models.Q(organisation__isnull=False),
                name="rbac_role_unique_name_per_organisation",
            ),
            models.UniqueConstraint(
                "practice",
                Lower("name"),
                condition=models.Q(practice__isnull=False),
                name="rbac_role_unique_name_per_practice",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def editable(self) -> bool:
        """Custom roles can be edited; system roles cannot (A-03-T09)."""
        return not self.is_system

    def permission_keys(self) -> frozenset[str]:
        return frozenset(self.grants.values_list("permission", flat=True))


class RolePermission(models.Model):
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="grants", verbose_name=_("role")
    )
    permission = models.CharField(_("permission"), max_length=100)

    class Meta:
        verbose_name = _("role permission")
        verbose_name_plural = _("role permissions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="rbac_rolepermission_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.role} → {self.permission}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """The key must be in the catalogue and grantable at the role's scope."""
        try:
            permission = catalogue.get(self.permission)
        except UnknownPermission:
            raise ValidationError(
                {"permission": _("There is no permission '%(key)s'.") % {"key": self.permission}},
                code="unknown_permission",
            ) from None
        if permission.scope.value not in GRANTABLE_SCOPES[self.role.scope]:
            raise ValidationError(
                {
                    "permission": _(
                        "'%(key)s' is a %(permission_scope)s permission; a %(role_scope)s role "
                        "can't grant it."
                    )
                    % {
                        "key": permission.key,
                        "permission_scope": permission.scope.value,
                        "role_scope": self.role.scope,
                    }
                },
                code="permission_scope",
            )


class RoleAssignment(models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, related_name="assignments", verbose_name=_("role")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_assignments",
        verbose_name=_("user"),
    )
    organisation = models.ForeignKey(
        "tenancy.Organisation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_assignments",
        verbose_name=_("organisation"),
    )
    practice = models.ForeignKey(
        "tenancy.Practice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="role_assignments",
        verbose_name=_("practice"),
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("assigned by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("role assignment")
        verbose_name_plural = _("role assignments")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=~models.Q(organisation__isnull=False, practice__isnull=False),
                name="rbac_assignment_one_tenant",
            ),
            models.UniqueConstraint(
                fields=["role", "user", "organisation"],
                condition=models.Q(organisation__isnull=False),
                name="rbac_assignment_unique_in_organisation",
            ),
            models.UniqueConstraint(
                fields=["role", "user", "practice"],
                condition=models.Q(practice__isnull=False),
                name="rbac_assignment_unique_in_practice",
            ),
            models.UniqueConstraint(
                fields=["role", "user"],
                condition=models.Q(organisation__isnull=True, practice__isnull=True),
                name="rbac_assignment_unique_platform",
            ),
        ]

    def __str__(self) -> str:
        where = self.organisation or self.practice or _("platform")
        return f"{self.user} · {self.role} · {where}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """The tenant must match the role's scope, and a custom role is used only where it lives."""
        role = self.role
        if role.scope == RoleScope.ORGANISATION and (
            self.organisation_id is None or self.practice_id is not None
        ):
            raise ValidationError(
                _("An organisation role is given in an organisation."), code="assignment_scope"
            )
        if role.scope == RoleScope.PRACTICE and (
            self.practice_id is None or self.organisation_id is not None
        ):
            raise ValidationError(
                _("A practice role is given in a practice."), code="assignment_scope"
            )
        if role.scope == RoleScope.PLATFORM and (
            self.organisation_id is not None or self.practice_id is not None
        ):
            raise ValidationError(
                _("A platform role is given without an organisation or practice."),
                code="assignment_scope",
            )
        if not role.is_system and (
            (role.organisation_id is not None and role.organisation_id != self.organisation_id)
            or (role.practice_id is not None and role.practice_id != self.practice_id)
        ):
            raise ValidationError(
                _("This custom role belongs to another organisation or practice."),
                code="assignment_foreign_role",
            )


class ApprovalDocumentType(models.TextChoices):
    """Documents whose approval is limited by amount (Phase 0 plan A-03, gap #25)."""

    JOURNAL = "journal", _("Manual journal")
    BILL = "bill", _("Bill")
    PURCHASE_ORDER = "purchase_order", _("Purchase order")
    PAY_RUN = "pay_run", _("Pay run")


class ApprovalLimit(OrgOwnedModel):
    """Highest amount (CAD, the organisation's base currency) one user — or everyone holding a
    role — may approve for a document type in the organisation. The effective limit is the lower
    of the user's own limit and the limits of their roles (A-03-T07); no limit set → no approval.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="approval_limits",
        verbose_name=_("user"),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="approval_limits",
        verbose_name=_("role"),
    )
    doc_type = models.CharField(
        _("document type"), max_length=32, choices=ApprovalDocumentType.choices
    )
    max_amount = models.DecimalField(
        _("maximum amount (CAD)"),
        max_digits=18,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        verbose_name = _("approval limit")
        verbose_name_plural = _("approval limits")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(user__isnull=False, role__isnull=True)
                | models.Q(user__isnull=True, role__isnull=False),
                name="rbac_limit_user_or_role",
            ),
            models.CheckConstraint(
                condition=models.Q(max_amount__gte=0), name="rbac_limit_not_negative"
            ),
            models.UniqueConstraint(
                fields=["organisation", "user", "doc_type"],
                condition=models.Q(user__isnull=False, deleted_at__isnull=True),
                name="rbac_limit_unique_user",
            ),
            models.UniqueConstraint(
                fields=["organisation", "role", "doc_type"],
                condition=models.Q(role__isnull=False, deleted_at__isnull=True),
                name="rbac_limit_unique_role",
            ),
        ]

    def __str__(self) -> str:
        who = self.user or self.role
        return f"{who} · {self.doc_type} ≤ {self.max_amount} CAD"

    def clean(self) -> None:
        super().clean()
        role = self.role
        if role is not None and (
            role.scope == RoleScope.PLATFORM
            or (role.organisation_id is not None and role.organisation_id != self.organisation_id)
            or role.practice_id is not None
        ):
            raise ValidationError(
                {"role": _("Choose a role used in this organisation.")}, code="limit_role"
            )


class AccessRequest(OrgOwnedModel):
    """Someone refused a permission asks for it ("Request access", A-03-T14).

    The people who could give it (``roles.assignment.manage`` + the permission themselves) are
    emailed, and see open requests on Users and roles until the notification centre (A-07)
    takes over delivery. One open request per person and permission; closing is a soft delete.
    """

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_requests",
        verbose_name=_("requester"),
    )
    permission = models.CharField(_("permission"), max_length=100)
    note = models.CharField(_("note"), max_length=500, blank=True)
    notified = models.PositiveSmallIntegerField(
        _("people notified"), default=0, help_text=_("How many people were emailed.")
    )

    class Meta:
        verbose_name = _("access request")
        verbose_name_plural = _("access requests")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "requester", "permission"],
                condition=models.Q(deleted_at__isnull=True),
                name="rbac_accessrequest_one_open",
            )
        ]

    def __str__(self) -> str:
        return f"{self.requester} → {self.permission}"
