"""The audit log: one append-only row per change, with who, what, where and the field diff (A-04).

``AuditEvent`` (table ``audit_event``) is written by the audit service (``service.record``,
A-04-T03) and never changed afterwards: the database refuses ``UPDATE`` and ``DELETE`` on it
(trigger and revoked privileges, A-04-T02) and every organisation's events form a SHA-256 hash
chain (``prev_hash`` → ``hash``, A-04-T05) that ``manage.py audit_verify`` checks.

What a row says:

- **where** — ``organisation`` (empty for platform events: sign-ins, platform console) and/or
  ``practice`` (practice events: practice staff invitations, practice roles);
- **who** — ``actor_kind`` (``user`` | ``system`` | ``impersonation``), ``actor_user``,
  ``impersonator`` (the platform staff member signed in *as* ``actor_user``) and
  ``actor_label`` — the name shown in the log, kept as it was then: the person's name and email,
  or ``System: <job name>`` for background jobs (gap-44);
- **what** — ``action`` (``<app>.<model>.created|updated|deleted|restored``, ``auth.login.failed``
  …), the record (``object_type`` model label, ``object_id`` public id, ``object_label`` as
  it was shown then) and ``changes`` — ``{field: [old, new]}`` for every field that changed, with
  masked fields (SIN, bank details, secrets) never stored in clear;
- **context** — ``ip``, ``user_agent``, ``request_id`` (A-04-T04), ``batch_id`` of a bulk
  operation (A-04-T06) and ``meta`` (extra facts, e.g. a failed sign-in's reason);
- **when** — ``created_at``, set by the service (it is part of the hashed payload).

**Partition-ready** (S-06-T03 turns ``audit_event`` into a parent partitioned by month on
``created_at``): the primary key is ``(created_at, id)`` — PostgreSQL requires the partition key
in every unique constraint — ``id`` comes from the sequence ``audit_event_id_seq``, nothing
references the table, and no other unique constraint exists (``public_id`` is indexed, not
unique: a random UUID). All indexes are plain b-trees that partition with the table.

**Tenancy.** ``objects`` is the organisation-scoped manager of every business record: the
viewer and the API read one organisation's events only. Platform and practice events (no
organisation) are read through ``platform_events``, kept for the platform audit endpoint and
the chain verifier only.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, NoReturn

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation, OrgOwnedModel, Practice

#: Sequence feeding ``AuditEvent.id`` (created by migration 0001; owned by the column).
ID_SEQUENCE = "audit_event_id_seq"


class ActorKind(models.TextChoices):
    USER = "user", _("User")
    SYSTEM = "system", _("System")
    IMPERSONATION = "impersonation", _("Platform staff signed in as the user")


class AuditImmutable(RuntimeError):
    """An audit event cannot be changed or removed (append-only, A-04-T02)."""


class AuditEvent(OrgOwnedModel):
    """One change: who did what to which record, when, from where, with the field diff."""

    pk = models.CompositePrimaryKey("created_at", "id")
    id = models.BigIntegerField(
        _("sequence number"),
        editable=False,
        db_default=models.Func(models.Value(ID_SEQUENCE), function="nextval"),
    )
    created_at = models.DateTimeField(_("date and time"), default=timezone.now, editable=False)

    # Platform and practice events have no organisation (overrides OrgOwnedModel's required FK).
    organisation = models.ForeignKey(  # type: ignore[assignment]  # nullable here
        Organisation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=False,  # every audit index starts with the organisation
        related_name="audit_events",
        verbose_name=_("organisation"),
    )
    # Random id used in URLs; indexed, not unique (a unique index would have to include the
    # partition key on a partitioned table).
    public_id = models.UUIDField(  # not unique here
        _("public ID"), default=uuid.uuid4, editable=False, db_index=True
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_events",
        verbose_name=_("practice"),
    )

    # The actor (who).
    actor_kind = models.CharField(
        _("actor kind"), max_length=16, choices=ActorKind.choices, default=ActorKind.SYSTEM
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("user"),
    )
    impersonator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("impersonator"),
    )
    actor_label = models.CharField(_("by"), max_length=300, blank=True)

    # What happened, to which record.
    action = models.CharField(_("action"), max_length=100)
    object_type = models.CharField(_("record type"), max_length=100, blank=True)
    object_id = models.CharField(_("record ID"), max_length=64, blank=True)
    object_label = models.CharField(_("record"), max_length=300, blank=True)
    changes = models.JSONField(_("changes"), default=dict, blank=True)
    meta = models.JSONField(_("details"), default=dict, blank=True)

    # Where from (A-04-T04) and which bulk operation (A-04-T06).
    ip = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.CharField(_("device"), max_length=512, blank=True)
    request_id = models.CharField(_("request ID"), max_length=64, blank=True)
    batch_id = models.UUIDField(_("batch ID"), null=True, blank=True)

    # Hash chain per organisation (A-04-T05).
    prev_hash = models.CharField(_("previous hash"), max_length=64, blank=True)
    hash = models.CharField(_("hash"), max_length=64, blank=True)

    # Removed from OrgOwnedModel: an audit event is never edited, soft-deleted or "created by"
    # anyone but its actor.
    created_by = None
    updated_at = None  # type: ignore[assignment]
    deleted_at = None

    #: Every organisation's events, platform and practice events included — the platform audit
    #: endpoint and the chain verifier only (see the module docstring).
    platform_events = models.Manager["AuditEvent"]()

    class Meta:
        db_table = "audit_event"
        verbose_name = _("audit event")
        verbose_name_plural = _("audit events")
        default_manager_name = "objects"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(actor_kind__in=ActorKind.values),
                name="audit_event_actor_kind_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(actor_kind=ActorKind.IMPERSONATION)
                | models.Q(impersonator__isnull=False, actor_user__isnull=False),
                name="audit_event_impersonation_names_both",
            ),
            models.CheckConstraint(condition=~models.Q(action=""), name="audit_event_action_set"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            # Global viewer: one organisation's events, newest first (default 90-day range).
            models.Index(fields=["organisation", "-created_at", "-id"], name="audit_org_time_idx"),
            # Record history drawer: one record's timeline.
            models.Index(
                fields=["organisation", "object_type", "object_id", "-created_at"],
                name="audit_org_object_idx",
            ),
            # "User" filter.
            models.Index(
                fields=["organisation", "actor_user", "-created_at"], name="audit_org_actor_idx"
            ),
            # Hash chain: the tail of an organisation's chain and verification in order.
            models.Index(fields=["organisation", "id"], name="audit_org_chain_idx"),
            # Bulk operations: every event of one batch.
            models.Index(
                fields=["batch_id"],
                name="audit_batch_idx",
                condition=models.Q(batch_id__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}:{self.object_id} by {self.actor_label}"

    # ---- append-only (A-04-T02): the model refuses before the database does ----

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise AuditImmutable("Audit events cannot be changed.")
        # Always an INSERT: the primary key is set before saving (created_at, id from the
        # sequence), so Django would otherwise try an UPDATE first.
        kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise AuditImmutable("Audit events cannot be deleted.")

    @property
    def is_deleted(self) -> bool:
        return False

    def soft_delete(self) -> NoReturn:
        raise AuditImmutable("Audit events cannot be deleted.")

    def restore(self) -> NoReturn:
        raise AuditImmutable("Audit events cannot be changed.")
