"""System checks for field encryption (S-03-T04), run by ``manage.py check --deploy``."""

from __future__ import annotations

from typing import Any

from django.core import checks
from django.core.exceptions import ImproperlyConfigured

from . import crypto


@checks.register(checks.Tags.security, deploy=True)
def check_field_encryption_keys(
    app_configs: Any = None, **kwargs: Any
) -> list[checks.CheckMessage]:
    try:
        ring = crypto.key_ring()
    except ImproperlyConfigured as error:
        return [
            checks.Error(
                str(error),
                hint="Set NUMO9_FIELD_ENCRYPTION_KEYS and NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY in the "
                "SOPS-encrypted environment (docs/security/secrets-runbook.md).",
                id="security.E100",
            )
        ]
    if any(key_id.endswith("-local") for key_id in ring.keys):
        return [
            checks.Error(
                "The development field-encryption key is in the key ring.",
                hint="Deployed environments use their own keys (manage.py generate_field_key).",
                id="security.E102",
            )
        ]
    return []
