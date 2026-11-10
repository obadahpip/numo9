"""Error-message catalogue (A-10-T14): every API error is a stable key plus a gettext message.

Clients and tests rely on the key (``code``); people read the message, translated into the
request's language. Messages follow the microcopy rules (Phase 0 plan §3.5): say what happened
and what to do, name the record, no blame, Canadian English, sentence case, never "Oops".

Add an error here — not as an inline string — and run ``make i18n``; the French text goes in
``backend/locale/fr_CA/LC_MESSAGES/django.po``.

    raise serializers.ValidationError({"practice": [error_detail(UNKNOWN_PRACTICE)]})
    raise api_error(ORG_HEADER_MISMATCH)                # 400 with {"detail", "code"}
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail

CODE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


@dataclass(frozen=True)
class ErrorMessage:
    code: str
    message: Promise
    status: int = status.HTTP_400_BAD_REQUEST

    def text(self, **params: Any) -> str:
        """The message in the active language, with ``%(name)s`` parameters filled in."""
        message = str(self.message)
        return message % params if params else message


CATALOGUE: dict[str, ErrorMessage] = {}


def define(
    code: str, message: Promise, status_code: int = status.HTTP_400_BAD_REQUEST
) -> ErrorMessage:
    if not CODE.match(code):
        raise ValueError(f"Error code {code!r} must be a dotted lower-case key like 'area.reason'.")
    if code in CATALOGUE:
        raise ValueError(f"Error code {code!r} is defined twice.")
    error = ErrorMessage(code, message, status_code)
    CATALOGUE[code] = error
    return error


def error_detail(error: ErrorMessage, **params: Any) -> ErrorDetail:
    """A DRF ErrorDetail carrying the translated message and the key (for field errors)."""
    return ErrorDetail(error.text(**params), code=error.code)


class CatalogueError(APIException):
    def __init__(self, error: ErrorMessage, **params: Any) -> None:
        self.status_code = error.status
        super().__init__(detail=error.text(**params), code=error.code)


def api_error(error: ErrorMessage, **params: Any) -> CatalogueError:
    return CatalogueError(error, **params)


# ---- tenancy (A-01) ------------------------------------------------------------------------
UNKNOWN_PRACTICE = define(
    "tenancy.unknown_practice",
    _("This practice doesn't exist or you're not a member. Choose one of your practices."),
)
ORG_HEADER_MISMATCH = define(
    "tenancy.org_header_mismatch",
    _(
        "The organisation in the address and the one in the X-Numo9-Org header differ. "
        "Send one organisation, or the same one in both."
    ),
)
