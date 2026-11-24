"""``manage.py seed_invoice_fixtures <org> [--user EMAIL] [--pdf-dir DIR]`` (D-03a-T18).

Builds the 50 fixture invoices (``numo9.sales.fixtures``) in the organisation (public id),
approving as the user (default: its first owner), and writes one PDF per province to
``--pdf-dir`` when given.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.accounts.models import User
from numo9.tenancy.models import Organisation, OrganisationMember

from ...fixtures import build_invoice_fixtures, render_pdf_fixtures


class Command(BaseCommand):
    help = "Create the 50 fixture invoices across the provinces (and their PDFs)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("organisation", help="Public id of the organisation")
        parser.add_argument("--user", help="Email of the person approving (default: an owner)")
        parser.add_argument("--pdf-dir", help="Write one PDF per province here")

    def handle(self, *args: Any, **options: Any) -> None:
        organisation = Organisation.objects.filter(public_id=options["organisation"]).first()
        if organisation is None:
            raise CommandError("There's no organisation with this public id.")
        if options.get("user"):
            user = User.objects.filter(email=options["user"]).first()
        else:
            owner = (
                OrganisationMember.objects.filter(organisation=organisation, role="owner")
                .order_by("pk")
                .first()
            )
            user = owner.user if owner else None
        if user is None:
            raise CommandError("No user to approve the invoices: pass --user.")
        invoices = build_invoice_fixtures(organisation, user)
        self.stdout.write(f"{len(invoices)} invoices created.")
        if options.get("pdf_dir"):
            for path in render_pdf_fixtures(invoices, Path(options["pdf_dir"])):
                self.stdout.write(f"PDF: {path}")
