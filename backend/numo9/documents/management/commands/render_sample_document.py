"""``manage.py render_sample_document --out sample.pdf [--locale fr-ca]`` (A-10-T16).

Renders the document template baseline with Canadian sample data, to preview the Letter layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from numo9.documents.pdf import render_pdf
from numo9.documents.sample_data import sample_context


class Command(BaseCommand):
    help = "Render the sample document (Letter, 1 in margins, Canadian sample data) to a PDF."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--out", required=True, help="Output PDF path")
        parser.add_argument("--locale", default="en-ca", help="en-ca (default) or fr-ca")

    def handle(self, *args: Any, **options: Any) -> None:
        pdf = render_pdf("documents/sample.html", sample_context(), locale=options["locale"])
        out = Path(options["out"])
        out.write_bytes(pdf)
        self.stdout.write(f"Wrote {out} ({len(pdf):,} bytes)")
