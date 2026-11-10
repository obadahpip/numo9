"""Breached-password validator (A-02-T02).

Checks a new password against Have I Been Pwned's Pwned Passwords range API with k-anonymity:
only the first five hex characters of the password's SHA-1 are sent; the API answers with every
suffix in that range and the comparison happens here. ``Add-Padding`` hides the real answer size.

The check **fails open**: if the API is slow or down, a warning is logged and the password is
accepted (length, common-password and similarity validators still apply), so sign-up never
depends on a third party being up. ``BREACHED_PASSWORD_CHECK = False`` turns it off (tests).
"""

from __future__ import annotations

import hashlib
import logging
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


def breach_count(password: str) -> int | None:
    """How often the password appears in known breaches; ``None`` when the API can't answer."""
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324 — HIBP protocol
    prefix, suffix = digest[:5], digest[5:]
    url = f"{settings.BREACHED_PASSWORD_API}{prefix}"
    if not url.startswith("https://"):
        raise ValueError("BREACHED_PASSWORD_API must be an https:// URL")
    request = urllib.request.Request(  # noqa: S310 — https checked above
        url, headers={"Add-Padding": "true", "User-Agent": "Numo9-password-check"}
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 — https checked above
            request, timeout=settings.BREACHED_PASSWORD_TIMEOUT
        ) as response:
            body = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("breached-password check unavailable: %s", type(exc).__name__)
        return None
    for line in body.splitlines():
        candidate, _sep, count = line.strip().partition(":")
        if candidate.upper() == suffix:
            try:
                return int(count)
            except ValueError:
                return 1
    return 0


class BreachedPasswordValidator:
    def validate(self, password: str, user: Any = None) -> None:
        if not getattr(settings, "BREACHED_PASSWORD_CHECK", True):
            return
        if breach_count(password):
            raise ValidationError(
                _(
                    "This password has appeared in a data breach, so attackers try it first. "
                    "Choose a different password."
                ),
                code="password_breached",
            )

    def get_help_text(self) -> str:
        return _("Your password can't be one that has appeared in a known data breach.")
