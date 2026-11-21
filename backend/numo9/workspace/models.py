"""Accountant workspace models (V-01).

``OrgDirectorySummary`` (V-01-T02) — one denormalised row per **practice × organisation** the
practice actively serves: everything the organisation directory searches, filters, sorts and
counts, in one table, so 2,000 organisations answer in well under 300 ms (p95) without joining
settings, registrations, subscriptions and memberships on every keystroke.

- The row is *derived*: ``numo9.workspace.summary`` rebuilds it from the source records (signals on
  every change, a nightly full rebuild); nothing edits it by hand. Rows of an assignment that is
  switched off are deleted (the practice no longer serves the organisation).
- Per practice, not per organisation: tags are the practice's own (V-02), and a practice must never
  see another practice's tags for the same client.
- ``search_vector`` — PostgreSQL ``tsvector`` (configuration ``simple``, ``unaccent``: "Erable"
  finds "Érable") over name, legal name, BN, owner, tags, industry and province; GIN index.
  ``bn`` (the nine digits) also has a trigram index, so a partial BN typed with or without spaces
  matches.
- ``gst_cycle``, ``overdue_count`` and ``unfiled_count`` are filled by providers that later phases
  register (GST/HST returns, sales invoices, filings); empty / 0 until then.

It is a cross-organisation *read model* of directory facts (the same facts ``/api/v1/me/
organisations`` shows), not an organisation's business records: it is allow-listed in
``numo9.tenancy.checks`` and every read goes through ``numo9.workspace.search``, which limits it to
the organisations the user may access in that practice (isolation tests:
``tests/test_workspace_isolation.py``).
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, TypeVar

from django.conf import settings
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from numo9.tenancy.models import Organisation, Practice


class DirectoryStatus(models.TextChoices):
    """Commercial state as the directory shows it (status chips: Trial 12 d, Paid, Demo…)."""

    TRIAL = "trial", _("Trial")
    PAID = "paid", _("Paid")
    DEMO = "demo", _("Demo")
    READ_ONLY = "read_only", _("Read-only")
    ARCHIVED = "archived", _("Archived")


class Density(models.TextChoices):
    """Row height of the directory grid (A-10-T10 density toggle)."""

    COMFORTABLE = "comfortable", _("Comfortable")
    COMPACT = "compact", _("Compact")


class GstCycle(models.TextChoices):
    """GST/HST filing frequency (fed by the GST/HST returns provider of a later phase)."""

    MONTHLY = "monthly", _("Monthly")
    QUARTERLY = "quarterly", _("Quarterly")
    ANNUAL = "annual", _("Annual")


def _in(field: str, choices: type[models.TextChoices], *, blank: bool = False) -> models.Q:
    condition = models.Q(**{f"{field}__in": choices.values})
    return condition | models.Q(**{field: ""}) if blank else condition


class OrgDirectorySummary(models.Model):
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,  # derived data: goes with the practice
        related_name="directory_rows",
        verbose_name=_("practice"),
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,  # derived data: goes with the organisation
        related_name="directory_rows",
        verbose_name=_("organisation"),
    )
    name = models.CharField(_("name"), max_length=200)
    legal_name = models.CharField(_("legal name"), max_length=200, blank=True)
    bn = models.CharField(_("Business Number"), max_length=9, blank=True)
    owner_name = models.CharField(_("owner"), max_length=200, blank=True)
    owner_email = models.CharField(_("owner email"), max_length=254, blank=True)
    industry = models.CharField(_("industry"), max_length=100, blank=True)
    province = models.CharField(_("province or territory"), max_length=2, blank=True)
    package = models.CharField(_("package"), max_length=64, blank=True)
    status = models.CharField(_("status"), max_length=16, choices=DirectoryStatus.choices)
    trial_ends_at = models.DateTimeField(_("trial ends"), null=True, blank=True)
    fye_month = models.PositiveSmallIntegerField(_("fiscal year end month"), default=12)
    fye_day = models.PositiveSmallIntegerField(_("fiscal year end day"), default=31)
    gst_cycle = models.CharField(
        _("GST/HST cycle"), max_length=16, choices=GstCycle.choices, blank=True
    )
    payroll_enabled = models.BooleanField(_("payroll"), default=False)
    overdue_count = models.PositiveIntegerField(_("overdue items"), default=0)
    unfiled_count = models.PositiveIntegerField(_("unfiled returns"), default=0)
    lock_date = models.DateField(
        _("latest lock date"),
        null=True,
        blank=True,
        help_text=_("The latest lock date set on any module (A-05); empty = no lock date (V-04)."),
    )
    tags = models.JSONField(_("tags"), default=list, blank=True)
    search_vector = SearchVectorField(_("search vector"), null=True, editable=False)
    refreshed_at = models.DateTimeField(_("refreshed at"))

    class Meta:
        verbose_name = _("organisation directory row")
        verbose_name_plural = _("organisation directory rows")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("practice", "organisation"), name="workspace_summary_one_per_assignment"
            ),
            models.CheckConstraint(
                condition=_in("status", DirectoryStatus), name="workspace_summary_status_valid"
            ),
            models.CheckConstraint(
                condition=_in("gst_cycle", GstCycle, blank=True),
                name="workspace_summary_gst_cycle_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(fye_month__gte=1, fye_month__lte=12),
                name="workspace_summary_fye_month_valid",
            ),
        ]
        # GIN (search_vector) and trigram (bn) indexes are created by the migration on PostgreSQL
        # only (numo9.audit.pg.PostgresOnly): a throw-away SQLite database can still migrate.
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("practice", "name"), name="workspace_summary_name_idx"),
            models.Index(fields=("practice", "status"), name="workspace_summary_status_idx"),
            models.Index(fields=("organisation",), name="workspace_summary_org_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.practice} → {self.name}"


class SavedView(models.Model):
    """A user's own named directory state in one practice (V-01-T08): search and filters, the
    columns shown and their order, the sort, the row density; one view can open by default.

    Personal: nobody else — not even a practice admin — lists, opens, changes or deletes it (the
    API answers 404). Stored on the server, so a view follows the user to another browser or
    device and survives logout/login. Not organisation data (it names filter values, not records):
    allow-listed platform model, like the practice memberships it belongs to.
    """

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # personal preferences go with the user
        related_name="directory_views",
        verbose_name=_("user"),
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name="directory_views",
        verbose_name=_("practice"),
    )
    name = models.CharField(_("name"), max_length=80)
    filters = models.JSONField(
        _("search and filters"),
        default=dict,
        blank=True,
        help_text=_('{"q": "maple", "province": ["ON"], "status": ["paid"]}'),
    )
    columns = models.JSONField(
        _("columns"), default=list, blank=True, help_text=_("Shown columns, in order.")
    )
    sort = models.JSONField(
        _("sort"), default=list, blank=True, help_text=_('["-overdue", "name"]')
    )
    density = models.CharField(
        _("density"), max_length=16, choices=Density.choices, default=Density.COMFORTABLE
    )
    is_default = models.BooleanField(_("opens by default"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("saved directory view")
        verbose_name_plural = _("saved directory views")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "user", "practice", Lower("name"), name="workspace_view_name_unique_per_user"
            ),
            models.UniqueConstraint(
                fields=("user", "practice"),
                condition=models.Q(is_default=True),
                name="workspace_view_one_default_per_user",
            ),
            models.CheckConstraint(
                condition=_in("density", Density), name="workspace_view_density_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.practice} · {self.name}"


# ---- groups (V-02) ---------------------------------------------------------------------------


_M = TypeVar("_M", bound=models.Model)


class AccessQuerySet(models.QuerySet[_M, _M]):
    """Bulk writes that bypass ``save()``/``delete()`` signals still invalidate the cached group
    access (V-02-T06): ``update``, ``bulk_create`` and ``bulk_update`` bump the access generation
    (``numo9.workspace.access.bump``), now and when the transaction commits."""

    def _bump(self) -> None:
        from .access import bump

        bump()

    def update(self, **kwargs: Any) -> int:
        rows = super().update(**kwargs)
        if rows:
            self._bump()
        return rows

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[_M]:
        created = super().bulk_create(objs, *args, **kwargs)
        if created:
            self._bump()
        return created

    def bulk_update(self, objs: Any, fields: Any, *args: Any, **kwargs: Any) -> int:
        rows = super().bulk_update(objs, fields, *args, **kwargs)
        if rows:
            self._bump()
        return rows


AccessManager = models.Manager.from_queryset(AccessQuerySet)

#: Deepest level of the group tree: a top-level group is depth 1 (V-02 business rule).
GROUP_MAX_DEPTH = 5


class OrgGroup(MP_Node):  # type: ignore[misc]
    """A practice's group of client organisations (V-02-T02): "Toronto office → Retail clients".

    A tree per practice, stored as a **materialised path** (``django-treebeard`` ``MP_Node``:
    ``path``, ``depth``, ``numchild``) — reading a subtree or the ancestors is one indexed query and
    a cycle can't be represented. Depth 1 to ``GROUP_MAX_DEPTH`` (5), also a database check.
    Siblings are kept in name order; a name is unique among its siblings (case ignored). An
    organisation can be in several groups (``OrgGroupMembership``). Practice data, not an
    organisation's records: allow-listed like the practice memberships.
    """

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    practice = models.ForeignKey(
        Practice, on_delete=models.CASCADE, related_name="+", verbose_name=_("practice")
    )
    name = models.CharField(_("name"), max_length=80)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    node_order_by: ClassVar[list[str]] = ["name"]

    class Meta:
        verbose_name = _("organisation group")
        verbose_name_plural = _("organisation groups")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(depth__gte=1, depth__lte=GROUP_MAX_DEPTH),
                name="workspace_group_max_depth",
            ),
            models.CheckConstraint(condition=~models.Q(name=""), name="workspace_group_name"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("practice", "depth"), name="workspace_group_practice_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class OrgGroupMembership(models.Model):
    """An organisation in a practice group (V-02-T02); in several groups at once if needed.

    The organisation must be one the group's practice serves (``clean``); removing the practice's
    assignment removes its memberships (V-02 edge case "org removed from practice").
    """

    group = models.ForeignKey(
        OrgGroup, on_delete=models.CASCADE, related_name="memberships", verbose_name=_("group")
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name="group_memberships",
        verbose_name=_("organisation"),
    )
    added_at = models.DateTimeField(_("added at"), auto_now_add=True)

    objects = AccessManager()

    class Meta:
        verbose_name = _("organisation in a group")
        verbose_name_plural = _("organisations in groups")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("group", "organisation"), name="workspace_group_membership_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organisation} ∈ {self.group}"


# ---- tags (V-02-T03) ---------------------------------------------------------------------------


class TagColour(models.TextChoices):
    """The 12-colour tag palette (V-02): each colour has a name; a tag always shows its name."""

    RED = "red", _("Red")
    ORANGE = "orange", _("Orange")
    AMBER = "amber", _("Amber")
    OLIVE = "olive", _("Olive")
    GREEN = "green", _("Green")
    TEAL = "teal", _("Teal")
    CYAN = "cyan", _("Cyan")
    BLUE = "blue", _("Blue")
    INDIGO = "indigo", _("Indigo")
    VIOLET = "violet", _("Violet")
    MAGENTA = "magenta", _("Magenta")
    SLATE = "slate", _("Slate")


class Tag(models.Model):
    """A practice's colour tag for its client organisations (V-02-T03): "Year-end soon".

    Practice-scoped: another practice never sees it, even on the same client. ``name_key`` is the
    name without case, accents and repeated spaces — unique per practice (database constraint), so
    "Québec" and "quebec" are one tag.
    """

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    practice = models.ForeignKey(
        Practice, on_delete=models.CASCADE, related_name="+", verbose_name=_("practice")
    )
    name = models.CharField(_("name"), max_length=40)
    name_key = models.CharField(_("name key"), max_length=40, editable=False)
    colour = models.CharField(
        _("colour"), max_length=10, choices=TagColour.choices, default=TagColour.SLATE
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        ordering = ("name_key",)
        verbose_name = _("tag")
        verbose_name_plural = _("tags")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("practice", "name_key"), name="workspace_tag_name_unique_per_practice"
            ),
            models.CheckConstraint(condition=~models.Q(name_key=""), name="workspace_tag_name"),
            models.CheckConstraint(
                condition=_in("colour", TagColour), name="workspace_tag_colour_valid"
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        from .tags import tag_key

        self.name = " ".join((self.name or "").split())
        self.name_key = tag_key(self.name)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "name" in update_fields:
            kwargs["update_fields"] = [*update_fields, "name_key"]
        super().save(*args, **kwargs)


class OrgTag(models.Model):
    """A tag on an organisation, in the tag's practice (V-02-T03)."""

    tag = models.ForeignKey(
        Tag, on_delete=models.CASCADE, related_name="assignments", verbose_name=_("tag")
    )
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="+", verbose_name=_("organisation")
    )
    added_at = models.DateTimeField(_("added at"), auto_now_add=True)

    class Meta:
        verbose_name = _("organisation tag")
        verbose_name_plural = _("organisation tags")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tag", "organisation"), name="workspace_org_tag_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organisation} #{self.tag}"


# ---- group staff (V-02-T04) --------------------------------------------------------------------


class GroupStaffRole(models.TextChoices):
    """The role a staff member works with in a group (practice admins see every client anyway)."""

    ACCOUNTANT = "accountant", _("Accountant")
    REVIEWER = "reviewer", _("Reviewer")
    PAYROLL_SPECIALIST = "payroll_specialist", _("Payroll specialist")
    READ_ONLY = "read_only", _("Read-only staff")


class GroupStaffAssignment(models.Model):
    """A practice member assigned to a group (V-02-T04): they work on every organisation in the
    group and its sub-groups, including organisations added later (the access resolver, V-02-T05).

    One row per group and member (unique); the member belongs to the group's practice. Removing the
    row revokes what it granted (on the member's next request, V-02-T06); access through another
    group or a direct assignment stays.
    """

    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    group = models.ForeignKey(
        OrgGroup, on_delete=models.CASCADE, related_name="staff", verbose_name=_("group")
    )
    practice_member = models.ForeignKey(
        "tenancy.PracticeMember",
        on_delete=models.PROTECT,
        related_name="group_assignments",
        verbose_name=_("staff member"),
    )
    role = models.CharField(
        _("role"), max_length=32, choices=GroupStaffRole.choices, default=GroupStaffRole.ACCOUNTANT
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = AccessManager()

    class Meta:
        verbose_name = _("group staff assignment")
        verbose_name_plural = _("group staff assignments")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("group", "practice_member"), name="workspace_group_staff_unique"
            ),
            models.CheckConstraint(
                condition=_in("role", GroupStaffRole), name="workspace_group_staff_role_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.practice_member} → {self.group} ({self.role})"


class DashboardLayout(models.Model):
    """A user's own practice home layout (V-04-T09): the widgets' order and the hidden ones.

    Personal, per practice, stored on the server (follows the user to another device). Widget keys
    the dashboard doesn't know any more are ignored; new widgets show after the ordered ones.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_layouts",
        verbose_name=_("user"),
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name="dashboard_layouts",
        verbose_name=_("practice"),
    )
    order = models.JSONField(_("widget order"), default=list, blank=True)
    hidden = models.JSONField(_("hidden widgets"), default=list, blank=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("dashboard layout")
        verbose_name_plural = _("dashboard layouts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("user", "practice"), name="workspace_dashboard_layout_once"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.practice} · dashboard"
