"""``manage.py seed_practice --orgs 2000`` — a practice with many client organisations (V-01-T06).

Performance fixture for the organisation directory (k6 benchmark V-01-T07, the 2,000-row
directory UI V-01-T09) and a realistic demo: Canadian names (accents included), provinces, fiscal
year ends, Business Numbers with valid check digits, owners, packages and statuses (trial with an
end date, paid, demo, read-only, a few archived). Acceptance: 2,000 organisations in < 2 minutes.

    manage.py seed_practice --orgs 2000
    manage.py seed_practice --orgs 500 --practice "Toronto CPA" --admin lead@toronto.test --staff 8

- Rows are bulk-inserted (no per-row signals or audit entries: this is test data, not someone's
  books), then the directory rows are rebuilt in one pass.
- The practice admin and the staff get unusable passwords unless ``--password`` is given (then
  their email addresses are verified so they can sign in). Dev and staging only — the command
  refuses to run with ``DEBUG`` off unless ``--force``.
- Each staff member is assigned a share of the organisations, so their directory is smaller.
- ``--sample-counts`` (default on) gives the provider-fed columns (GST/HST cycle, overdue items,
  unfiled returns) sample values on the directory rows, so their filters have something to show
  until the later phases' providers exist; the nightly rebuild resets them.
- ``--seed`` makes the data reproducible (default 2026).
"""

from __future__ import annotations

import random
import time
from datetime import timedelta
from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction
from django.utils import timezone

from numo9.accounts.models import User
from numo9.catalogue.models import Product
from numo9.entitlements.models import Subscription, SubscriptionStatus
from numo9.orgsettings.models import (
    OrganisationSettings,
    RegistrationStatus,
    RegistrationType,
    TaxRegistration,
)
from numo9.orgsettings.validators import luhn_valid
from numo9.packages.models import Package, PackageProduct, PackageStatus
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    Practice,
    PracticeAssignment,
    PracticeMember,
    PracticeRole,
)
from numo9.workspace.models import GstCycle, OrgDirectorySummary
from numo9.workspace.summary import refresh_organisation

FIRST = [
    "Maple",
    "Érable",
    "Birch",
    "Cedar",
    "Northern",
    "Laurentian",
    "Prairie",
    "Harbour",
    "Granite",
    "Québec",
    "Fraser",
    "Bluewater",
    "Aurora",
    "Chinook",
    "Saint-Laurent",
    "Rideau",
    "Muskoka",
    "Okanagan",
    "Fundy",
    "Algonquin",
    "Beaumont",
    "Lévis",
    "Trois-Rivières",
    "Kootenay",
    "Niagara",
]
SECOND = [
    "Leaf",
    "Ridge",
    "Valley",
    "Shore",
    "Pines",
    "Bay",
    "River",
    "Hill",
    "Lakes",
    "Point",
    "Grove",
    "Coast",
    "Falls",
    "Creek",
    "Plains",
    "Heights",
    "Brook",
    "Meadow",
]
TRADE = [
    ("Supply", "Wholesale"),
    ("Bakery", "Food services"),
    ("Dental", "Health care"),
    ("Movers", "Transportation"),
    ("Tile Co.", "Construction"),
    ("Consulting", "Professional"),
    ("Café", "Food services"),
    ("Auto Repair", "Automotive"),
    ("Design", "Professional"),
    ("Landscaping", "Construction"),
    ("Pharmacy", "Retail"),
    ("Boutique", "Retail"),
    ("Plumbing", "Construction"),
    ("Farms", "Agriculture"),
    ("Software", "Technology"),
]
SUFFIX = ["Ltd.", "Inc.", "Corp.", "Ltée", "Inc.", "Ltd."]
#: Province, a postal code in it, weight.
PROVINCES = [
    ("ON", "M5V 2T6", 38),
    ("QC", "H2X 1Y4", 23),
    ("BC", "V6B 1A1", 13),
    ("AB", "T2P 1J9", 11),
    ("MB", "R3C 0A1", 4),
    ("SK", "S4P 3Y2", 3),
    ("NS", "B3H 1A1", 3),
    ("NB", "E1C 4M3", 2),
    ("NL", "A1C 5M2", 1),
    ("PE", "C1A 4P3", 1),
    ("YT", "Y1A 1B1", 1),
]
GIVEN = [
    "Dana",
    "Sam",
    "Amélie",
    "Noah",
    "Priya",
    "Liam",
    "Chloé",
    "Omar",
    "Mei",
    "Lucas",
    "Fatima",
]
FAMILY = ["Tremblay", "Patel", "Gagnon", "Smith", "Nguyen", "Roy", "Côté", "Singh", "Wong", "Brown"]
#: Status, weight.
STATUSES = [
    (OrganisationStatus.ACTIVE, 70),
    (OrganisationStatus.TRIAL, 18),
    (OrganisationStatus.DEMO, 3),
    (OrganisationStatus.READ_ONLY, 4),
    (OrganisationStatus.CANCELLED, 5),
]
SUBSCRIPTION_STATUS = {
    OrganisationStatus.ACTIVE: SubscriptionStatus.ACTIVE,
    OrganisationStatus.TRIAL: SubscriptionStatus.TRIALING,
    OrganisationStatus.DEMO: SubscriptionStatus.DEMO,
    OrganisationStatus.READ_ONLY: SubscriptionStatus.READ_ONLY,
    OrganisationStatus.CANCELLED: SubscriptionStatus.CANCELLED,
}
#: Sample packages for an empty database (code, name, products).
SAMPLE_PACKAGES = [
    ("seed_books", "Books (sample)", ["accounting"]),
    ("seed_growth", "Growth (sample)", ["accounting", "tax"]),
    ("seed_complete", "Complete (sample)", ["accounting", "tax", "payroll", "inventory"]),
]
FYE = [(12, 31, 60), (3, 31, 12), (6, 30, 10), (9, 30, 8), (1, 31, 4), (4, 30, 3), (10, 31, 3)]


def _bn(rng: random.Random, used: set[str]) -> str:
    while True:
        body = f"{rng.randrange(10_000_000, 99_999_999):08d}"
        bn = next(body + d for d in "0123456789" if luhn_valid(body + d))
        if bn not in used:
            used.add(bn)
            return bn


def _weighted(rng: random.Random, items: list[Any]) -> Any:
    return rng.choices(items, weights=[item[-1] for item in items])[0]


class Command(BaseCommand):
    help = "Create a practice with N client organisations (directory performance fixture, V-01)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--orgs", type=int, default=2000, help="Organisations (default 2000).")
        parser.add_argument("--practice", default="Seed Practice", help="Practice name.")
        parser.add_argument("--admin", default="seed-admin@numo9.test", help="Admin email.")
        parser.add_argument("--staff", type=int, default=5, help="Accountants (default 5).")
        parser.add_argument("--password", default="", help="Password for the admin and staff.")
        parser.add_argument("--seed", type=int, default=2026, help="Random seed.")
        parser.add_argument(
            "--no-sample-counts",
            dest="sample_counts",
            action="store_false",
            help="Leave GST/HST cycle, overdue items and unfiled returns empty.",
        )
        parser.add_argument("--force", action="store_true", help="Run even with DEBUG off.")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not options["force"]:
            raise CommandError("seed_practice creates test data: dev/staging only (or --force).")
        count: int = options["orgs"]
        if not 1 <= count <= 20_000:
            raise CommandError("--orgs must be between 1 and 20,000.")
        started = time.monotonic()
        rng = random.Random(options["seed"])  # noqa: S311 (test data, not security)
        with transaction.atomic():
            practice, staff = self._practice(options)
            organisation_ids = self._organisations(rng, practice, staff, count, options["seed"])
        inserted = time.monotonic() - started
        for organisation_id in organisation_ids:
            refresh_organisation(organisation_id)
        if options["sample_counts"]:
            self._sample_counts(rng, practice)
        self._analyze()
        elapsed = time.monotonic() - started
        self.stdout.write(
            f"{practice.name}: {count} organisations, {len(staff)} staff, admin "
            f"{options['admin']} — inserted in {inserted:.1f} s, "
            f"directory ready in {elapsed:.1f} s."
        )
        self.stdout.write(f"Practice id: {practice.public_id}")

    # ---- people ----------------------------------------------------------------------------

    def _person(self, email: str, name: str, password: str) -> User:
        """The user (created when missing). With a password the address is marked verified, so
        the admin and staff can sign in at once (k6 benchmark, demos)."""
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=password or None, name=name)
        elif password:
            user.set_password(password)
            user.save(update_fields=["password"])
        if password:
            EmailAddress.objects.update_or_create(
                user=user, email=user.email, defaults={"verified": True, "primary": True}
            )
        return user

    def _practice(self, options: dict[str, Any]) -> tuple[Practice, list[PracticeMember]]:
        password = options["password"]
        practice = Practice.objects.filter(name=options["practice"]).first()
        if practice is None:
            practice = Practice.objects.create(name=options["practice"])
        admin = self._person(options["admin"], "Seed Admin", password)
        PracticeMember.objects.get_or_create(
            practice=practice, user=admin, defaults={"role": PracticeRole.PRACTICE_ADMIN}
        )
        staff = []
        local, _, domain = options["admin"].partition("@")
        for index in range(options["staff"]):
            person = self._person(
                f"{local}+staff{index + 1}@{domain}", f"Staff {index + 1}", password
            )
            member, _ = PracticeMember.objects.get_or_create(
                practice=practice, user=person, defaults={"role": PracticeRole.ACCOUNTANT}
            )
            staff.append(member)
        return practice, staff

    # ---- organisations (bulk) --------------------------------------------------------------

    def _packages(self) -> list[Package]:
        """The active packages; on an empty database, three sample ones (``seed_*`` codes —
        packages are the client's data, so real ones are never invented here)."""
        packages = list(Package.objects.filter(status=PackageStatus.ACTIVE).order_by("sort"))
        if packages:
            return packages
        for sort, (code, name, products) in enumerate(SAMPLE_PACKAGES):
            package = Package.objects.create(
                code=code, name_i18n={"en-CA": name, "fr-CA": name}, sort=sort
            )
            for product in products:
                PackageProduct.objects.create(
                    package=package, product=Product.objects.get(code=product)
                )
            package.status = PackageStatus.ACTIVE
            package.save()
            packages.append(package)
        return packages

    def _organisations(
        self,
        rng: random.Random,
        practice: Practice,
        staff: list[PracticeMember],
        count: int,
        seed: int,
    ) -> list[int]:
        now = timezone.now()
        packages = self._packages()
        used_bns = set(
            TaxRegistration._base_manager.filter(type=RegistrationType.BN).values_list(
                "number", flat=True
            )
        )
        names = set(practice.assignments.values_list("organisation__name", flat=True))
        plans: list[dict[str, Any]] = []
        for index in range(count):
            first, second = rng.choice(FIRST), rng.choice(SECOND)
            trade, industry = rng.choice(TRADE)
            name = f"{first} {second} {trade} {rng.choice(SUFFIX)}"
            while name in names:  # unique per practice, still readable
                name = f"{first} {second} {trade} {index + 1}"
            names.add(name)
            province, postal, _w = _weighted(rng, PROVINCES)
            month, day, _w = _weighted(rng, FYE)
            status = _weighted(rng, STATUSES)[0]
            plans.append(
                {
                    "name": name,
                    "industry": industry,
                    "province": province,
                    "postal": postal,
                    "fye": (month, day),
                    "status": status,
                    "bn": _bn(rng, used_bns) if rng.random() < 0.9 else "",
                    "owner": f"{rng.choice(GIVEN)} {rng.choice(FAMILY)}",
                    "package": rng.choice(packages),
                    "trial_days": rng.randint(1, 30),
                }
            )
        organisations = Organisation.objects.bulk_create(
            [Organisation(name=p["name"], status=p["status"]) for p in plans], batch_size=1000
        )
        OrganisationSettings._base_manager.bulk_create(
            [
                OrganisationSettings(
                    organisation=org,
                    display_name=p["name"],
                    legal_name=p["name"],
                    industry=p["industry"],
                    mailing_province=p["province"],
                    mailing_postal_code=p["postal"],
                    mailing_city="",
                    fye_month=p["fye"][0],
                    fye_day=p["fye"][1],
                )
                for org, p in zip(organisations, plans, strict=True)
            ],
            batch_size=1000,
        )
        TaxRegistration._base_manager.bulk_create(
            [
                TaxRegistration(
                    organisation=org,
                    type=RegistrationType.BN,
                    number=p["bn"],
                    status=RegistrationStatus.ACTIVE,
                )
                for org, p in zip(organisations, plans, strict=True)
                if p["bn"]
            ],
            batch_size=1000,
        )
        unusable = make_password(None)
        owners = User.objects.bulk_create(
            [
                User(
                    email=f"owner-{seed}-{org.public_id.hex[:12]}@seed.numo9.test",
                    name=p["owner"],
                    password=unusable,
                )
                for org, p in zip(organisations, plans, strict=True)
            ],
            batch_size=1000,
        )
        OrganisationMember.objects.bulk_create(
            [
                OrganisationMember(organisation=org, user=owner, role=OrganisationRole.OWNER)
                for org, owner in zip(organisations, owners, strict=True)
            ],
            batch_size=1000,
        )
        Subscription._base_manager.bulk_create(
            [
                Subscription(
                    organisation=org,
                    package=p["package"],
                    status=SUBSCRIPTION_STATUS[p["status"]],
                    current_period_end=(
                        now + timedelta(days=p["trial_days"])
                        if p["status"] == OrganisationStatus.TRIAL
                        else now + timedelta(days=30)
                    ),
                    status_changed_at=now,
                )
                for org, p in zip(organisations, plans, strict=True)
            ],
            batch_size=1000,
        )
        assignments = PracticeAssignment.objects.bulk_create(
            [PracticeAssignment(practice=practice, organisation=org) for org in organisations],
            batch_size=1000,
        )
        through = PracticeAssignment.assigned_staff.through
        links = []
        for index, assignment in enumerate(assignments):
            if staff:
                member = staff[index % len(staff)]
                links.append(
                    through(practiceassignment_id=assignment.pk, practicemember_id=member.pk)
                )
        through.objects.bulk_create(links, batch_size=1000)
        return [org.pk for org in organisations]

    def _analyze(self) -> None:
        """Fresh planner statistics after a bulk insert (PostgreSQL), as autovacuum would give
        later: without them the directory queries are planned for empty tables."""
        if connection.vendor != "postgresql":
            return
        tables = [
            OrgDirectorySummary._meta.db_table,
            Organisation._meta.db_table,
            OrganisationMember._meta.db_table,
            PracticeAssignment._meta.db_table,
            PracticeAssignment.assigned_staff.through._meta.db_table,
            PracticeMember._meta.db_table,
        ]
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f'ANALYZE "{table}"')  # noqa: S608 (model table names)

    def _sample_counts(self, rng: random.Random, practice: Practice) -> None:
        rows = list(OrgDirectorySummary.objects.filter(practice=practice).only("pk"))
        cycles = [GstCycle.MONTHLY, GstCycle.QUARTERLY, GstCycle.QUARTERLY, GstCycle.ANNUAL]
        for row in rows:
            row.gst_cycle = rng.choice(cycles)
            row.overdue_count = rng.choice([0, 0, 0, 0, 1, 2, 3, 5])
            row.unfiled_count = rng.choice([0, 0, 0, 0, 0, 1, 2])
        OrgDirectorySummary.objects.bulk_update(
            rows, ["gst_cycle", "overdue_count", "unfiled_count"], batch_size=1000
        )
