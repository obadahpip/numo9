"""Journal entries and lines (C-02-T02, ADR-0003).

``ledger_journalline`` is partition-ready (C-02-T03 hash-partitions it by organisation): primary
key ``(organisation_id, id)``, ``id`` from the sequence ``ledger_journalline_id_seq`` (created
first, then owned by the column). Both tables get row-level security (A-01-T12): the journal line
table is one of the plan's sensitive tables. The SQL steps run on PostgreSQL only.
"""

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from numo9.audit.pg import PostgresOnly
from numo9.tenancy.rls import EnableOrgRLS


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0006_exemption_certificate"),
        ("ledger", "0002_seed_gifi"),
        ("tenancy", "0004_practice_setup_pending"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        PostgresOnly(
            sql="CREATE SEQUENCE ledger_journalline_id_seq AS bigint",
            reverse_sql="DROP SEQUENCE IF EXISTS ledger_journalline_id_seq",
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name="public ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, editable=False, null=True, verbose_name="deleted at"
                    ),
                ),
                (
                    "number",
                    models.PositiveBigIntegerField(
                        blank=True, null=True, verbose_name="journal number"
                    ),
                ),
                ("date", models.DateField(verbose_name="date")),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("manual", "Manual journal"),
                            ("sales", "Sales"),
                            ("purchase", "Purchases"),
                            ("payment", "Payment"),
                            ("payroll", "Payroll"),
                            ("opening", "Opening balance"),
                            ("adjustment", "Adjustment"),
                            ("reversal", "Reversal"),
                        ],
                        default="manual",
                        max_length=32,
                        verbose_name="journal type",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("awaiting_approval", "Awaiting approval"),
                            ("posted", "Posted"),
                            ("reversed", "Reversed"),
                        ],
                        default="draft",
                        max_length=20,
                        verbose_name="status",
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        blank=True, max_length=60, verbose_name="source document type"
                    ),
                ),
                (
                    "source_id",
                    models.CharField(blank=True, max_length=64, verbose_name="source document"),
                ),
                ("narration", models.TextField(blank=True, verbose_name="narration")),
                (
                    "book_scope",
                    models.CharField(
                        choices=[
                            ("both", "Both books"),
                            ("accounting", "Accounting book"),
                            ("tax", "Tax book"),
                        ],
                        default="both",
                        max_length=16,
                        verbose_name="books",
                    ),
                ),
                (
                    "posted_at",
                    models.DateTimeField(blank=True, null=True, verbose_name="posted at"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="created by",
                    ),
                ),
                (
                    "organisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="tenancy.organisation",
                        verbose_name="organisation",
                    ),
                ),
                (
                    "posted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="posted by",
                    ),
                ),
                (
                    "reversal_of",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reversed_by",
                        to="ledger.journalentry",
                        verbose_name="reverses",
                    ),
                ),
            ],
            options={
                "verbose_name": "journal entry",
                "verbose_name_plural": "journal entries",
                "ordering": ("-date", "-number", "-pk"),
            },
        ),
        migrations.CreateModel(
            name="JournalLine",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "organisation",
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
                            models.Value("ledger_journalline_id_seq"),
                            function="nextval",
                        ),
                        editable=False,
                        verbose_name="line ID",
                    ),
                ),
                ("line_no", models.PositiveSmallIntegerField(verbose_name="line")),
                (
                    "debit",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=18,
                        verbose_name="debit",
                    ),
                ),
                (
                    "credit",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=18,
                        verbose_name="credit",
                    ),
                ),
                (
                    "book",
                    models.CharField(
                        choices=[
                            ("both", "Both books"),
                            ("accounting", "Accounting book"),
                            ("tax", "Tax book"),
                        ],
                        default="both",
                        max_length=16,
                        verbose_name="book",
                    ),
                ),
                (
                    "tracking",
                    models.JSONField(blank=True, default=dict, verbose_name="tracking"),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=500, verbose_name="description"),
                ),
                (
                    "tax_code",
                    models.CharField(blank=True, max_length=60, verbose_name="tax code"),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="journal_lines",
                        to="ledger.account",
                        verbose_name="account",
                    ),
                ),
                (
                    "contact",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="journal_lines",
                        to="contacts.contact",
                        verbose_name="contact",
                    ),
                ),
                (
                    "entry",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lines",
                        to="ledger.journalentry",
                        verbose_name="journal entry",
                    ),
                ),
                (
                    "organisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="%(app_label)s_%(class)s_set",
                        to="tenancy.organisation",
                        verbose_name="organisation",
                    ),
                ),
            ],
            options={
                "verbose_name": "journal line",
                "verbose_name_plural": "journal lines",
                "ordering": ("entry_id", "line_no"),
            },
        ),
        migrations.AddIndex(
            model_name="journalentry",
            index=models.Index(fields=["organisation", "date"], name="ledger_journal_date_idx"),
        ),
        migrations.AddIndex(
            model_name="journalentry",
            index=models.Index(
                fields=["organisation", "source_type", "source_id"],
                name="ledger_journal_source_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.UniqueConstraint(
                condition=models.Q(("number__isnull", False)),
                fields=("organisation", "number"),
                name="ledger_journal_number_unique_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("status__in", ["draft", "awaiting_approval", "posted", "reversed"])
                ),
                name="ledger_journal_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("book_scope__in", ["both", "accounting", "tax"])),
                name="ledger_journal_book_scope_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("type", ""), _negated=True),
                name="ledger_journal_type_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("number__isnull", False),
                        ("posted_at__isnull", False),
                        ("status__in", ["posted", "reversed"]),
                    ),
                    models.Q(
                        ("number__isnull", True),
                        ("status__in", ["draft", "awaiting_approval"]),
                    ),
                    _connector="OR",
                ),
                name="ledger_journal_number_when_posted",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("reversal_of", models.F("pk")), _negated=True),
                name="ledger_journal_not_own_reversal",
            ),
        ),
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(
                fields=["organisation", "account", "book"],
                name="ledger_line_account_book_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(fields=["organisation", "entry"], name="ledger_line_entry_idx"),
        ),
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.CheckConstraint(
                condition=models.Q(("debit__gte", 0)),
                name="ledger_line_debit_not_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.CheckConstraint(
                condition=models.Q(("credit__gte", 0)),
                name="ledger_line_credit_not_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("credit", 0), ("debit__gt", 0)),
                    models.Q(("credit__gt", 0), ("debit", 0)),
                    _connector="OR",
                ),
                name="ledger_line_one_side",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.CheckConstraint(
                condition=models.Q(("book__in", ["both", "accounting", "tax"])),
                name="ledger_line_book_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.UniqueConstraint(
                fields=("organisation", "entry", "line_no"),
                name="ledger_line_no_unique",
            ),
        ),
        PostgresOnly(
            sql="ALTER SEQUENCE ledger_journalline_id_seq OWNED BY ledger_journalline.id",
            reverse_sql=migrations.RunSQL.noop,
        ),
        EnableOrgRLS("ledger_journalentry"),
        EnableOrgRLS("ledger_journalline"),
    ]
