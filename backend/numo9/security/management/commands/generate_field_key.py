"""``manage.py generate_field_key <key id>`` — a new AES-256 key for the field-encryption key ring
(S-03-T04). Prints it once; put it in the SOPS-encrypted environment, never in a file or ticket."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.security import crypto


class Command(BaseCommand):
    help = "Print a new base64 AES-256 key for NUMO9_FIELD_ENCRYPTION_KEYS."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("key_id", help="Key id, e.g. 2026-11 (letters, digits, . _ -)")

    def handle(self, *args: Any, **options: Any) -> None:
        key_id = options["key_id"]
        if not crypto.KEY_ID.match(key_id) or key_id.endswith("-local"):
            raise CommandError(
                "Key id: 1–32 letters, digits, '.', '_' or '-', not ending '-local'."
            )
        self.stdout.write(f'"{key_id}": "{crypto.generate_key()}"')
