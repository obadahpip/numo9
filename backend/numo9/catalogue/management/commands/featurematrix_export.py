"""``manage.py featurematrix_export`` — the feature matrix as CSV or XLSX (U-01-T10).

python manage.py featurematrix_export --format xlsx --output feature-matrix.xlsx
python manage.py featurematrix_export --format csv --locale fr-ca   # to stdout
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.catalogue.exports import FORMATS, write


class Command(BaseCommand):
    help = "Export the feature matrix (key → product → packages) as CSV or XLSX."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--format", choices=FORMATS, default="csv")
        parser.add_argument("--locale", default="en-ca", help="Language of the texts")
        parser.add_argument("--output", help="File to write (default: stdout; required for xlsx)")

    def handle(self, *args: Any, **options: Any) -> None:
        body = write(options["format"], options["locale"])
        if options["output"]:
            Path(options["output"]).write_bytes(body)
            self.stdout.write(f"featurematrix_export: wrote {options['output']}")
        elif options["format"] == "xlsx":
            raise CommandError("XLSX needs --output FILE.")
        else:
            sys.stdout.buffer.write(body)
