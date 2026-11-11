"""``manage.py permcat_export`` — the permission catalogue as JSON, CSV or Markdown (A-03-T01).

    python manage.py permcat_export                     # JSON on stdout
    python manage.py permcat_export --format csv --output permissions.csv
    python manage.py permcat_export --format markdown --locale fr-ca

Every permission declared in an app's ``permissions.py``: key, label (in ``--locale``), module,
risk, scope, owner-only. Ordered by module (navigation order), then key. The Markdown output is
the catalogue page of the documentation (A-03-T16).
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import translation

from numo9.rbac.catalogue import catalogue

FIELDS = ("key", "label", "module", "risk", "scope", "owner_only")


def rows() -> list[dict[str, Any]]:
    return [
        {
            "key": p.key,
            "label": str(p.label),
            "module": p.module,
            "risk": p.risk.value,
            "scope": p.scope.value,
            "owner_only": p.owner_only,
        }
        for p in catalogue
    ]


def as_json(data: list[dict[str, Any]]) -> str:
    return (
        json.dumps({"count": len(data), "permissions": data}, ensure_ascii=False, indent=2) + "\n"
    )


def as_csv(data: list[dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(data)
    return out.getvalue()


def as_markdown(data: list[dict[str, Any]]) -> str:
    lines = [f"{len(data)} permissions."]
    module = None
    for row in data:
        if row["module"] != module:
            module = row["module"]
            lines += [
                "",
                f"## {module}",
                "",
                "| Key | Permission | Risk | Scope |",
                "|---|---|---|---|",
            ]
        owner = " (owner only)" if row["owner_only"] else ""
        lines.append(f"| `{row['key']}` | {row['label']}{owner} | {row['risk']} | {row['scope']} |")
    return "\n".join(lines) + "\n"


FORMATS = {"json": as_json, "csv": as_csv, "markdown": as_markdown}


class Command(BaseCommand):
    help = "Export the permission catalogue (every declared permission)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--format", choices=sorted(FORMATS), default="json")
        parser.add_argument("--locale", default="en-ca", help="Language of the labels.")
        parser.add_argument("--output", type=Path, help="Write to this file instead of stdout.")

    def handle(self, *args: Any, **options: Any) -> None:
        with translation.override(options["locale"]):
            text = FORMATS[options["format"]](rows())
        if options["output"]:
            options["output"].write_text(text, encoding="utf-8")
            self.stderr.write(f"{len(catalogue)} permissions written to {options['output']}")
        else:
            self.stdout.write(text, ending="")
