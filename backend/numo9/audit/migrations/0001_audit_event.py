"""Audit log table ``audit_event`` (A-04-T01).

Partition-ready (S-06-T03): primary key ``(created_at, id)``, ``id`` from the sequence
``audit_event_id_seq`` (created first, then owned by the column), no unique constraint without
the partition key, nothing references the table.
"""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenancy", "0004_practice_setup_pending"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE SEQUENCE audit_event_id_seq AS bigint",
            reverse_sql="DROP SEQUENCE IF EXISTS audit_event_id_seq",
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "created_at",
                        "id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "id",
                    models.BigIntegerField(
                        db_default=models.Func(
                            models.Value("audit_event_id_seq"), function="nextval"
                        ),
                        editable=False,
                        verbose_name="sequence number",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="date and time",
                    ),
                ),
                (
                    "public_id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        verbose_name="public ID",
                    ),
                ),
                (
                    "actor_kind",
                    models.CharField(
                        choices=[
                            ("user", "User"),
                            ("system", "System"),
                            ("impersonation", "Platform staff signed in as the user"),
                        ],
                        default="system",
                        max_length=16,
                        verbose_name="actor kind",
                    ),
                ),
                (
                    "actor_label",
                    models.CharField(blank=True, max_length=300, verbose_name="by"),
                ),
                ("action", models.CharField(max_length=100, verbose_name="action")),
                (
                    "object_type",
                    models.CharField(blank=True, max_length=100, verbose_name="record type"),
                ),
                (
                    "object_id",
                    models.CharField(blank=True, max_length=64, verbose_name="record ID"),
                ),
                (
                    "object_label",
                    models.CharField(blank=True, max_length=300, verbose_name="record"),
                ),
                (
                    "changes",
                    models.JSONField(blank=True, default=dict, verbose_name="changes"),
                ),
                (
                    "meta",
                    models.JSONField(blank=True, default=dict, verbose_name="details"),
                ),
                (
                    "ip",
                    models.GenericIPAddressField(blank=True, null=True, verbose_name="IP address"),
                ),
                (
                    "user_agent",
                    models.CharField(blank=True, max_length=512, verbose_name="device"),
                ),
                (
                    "request_id",
                    models.CharField(blank=True, max_length=64, verbose_name="request ID"),
                ),
                (
                    "batch_id",
                    models.UUIDField(blank=True, null=True, verbose_name="batch ID"),
                ),
                (
                    "prev_hash",
                    models.CharField(blank=True, max_length=64, verbose_name="previous hash"),
                ),
                (
                    "hash",
                    models.CharField(blank=True, max_length=64, verbose_name="hash"),
                ),
                (
                    "actor_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="user",
                    ),
                ),
                (
                    "impersonator",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="impersonator",
                    ),
                ),
                (
                    "organisation",
                    models.ForeignKey(
                        blank=True,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="tenancy.organisation",
                        verbose_name="organisation",
                    ),
                ),
                (
                    "practice",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="tenancy.practice",
                        verbose_name="practice",
                    ),
                ),
            ],
            options={
                "verbose_name": "audit event",
                "verbose_name_plural": "audit events",
                "db_table": "audit_event",
                "default_manager_name": "objects",
                "indexes": [
                    models.Index(
                        fields=["organisation", "-created_at", "-id"],
                        name="audit_org_time_idx",
                    ),
                    models.Index(
                        fields=[
                            "organisation",
                            "object_type",
                            "object_id",
                            "-created_at",
                        ],
                        name="audit_org_object_idx",
                    ),
                    models.Index(
                        fields=["organisation", "actor_user", "-created_at"],
                        name="audit_org_actor_idx",
                    ),
                    models.Index(fields=["organisation", "id"], name="audit_org_chain_idx"),
                    models.Index(
                        condition=models.Q(("batch_id__isnull", False)),
                        fields=["batch_id"],
                        name="audit_batch_idx",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("actor_kind__in", ["user", "system", "impersonation"])),
                        name="audit_event_actor_kind_valid",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("actor_kind", "impersonation"), _negated=True),
                            models.Q(
                                ("actor_user__isnull", False),
                                ("impersonator__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="audit_event_impersonation_names_both",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("action", ""), _negated=True),
                        name="audit_event_action_set",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql="ALTER SEQUENCE audit_event_id_seq OWNED BY audit_event.id",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
