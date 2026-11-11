"""DRF exception handler (A-10-T14): error bodies carry a stable ``code`` next to the message.

- ``{"detail": "<message in the request's language>", "code": "not_found"}`` for request-level
  errors (401, 403, 404, 405, 429, catalogue errors);
- field errors keep DRF's shape ``{"field": ["<message>"]}`` — their keys are the
  ``ErrorDetail.code`` of each message (see ``errors.error_detail``);
- an exception with an ``extra`` dict adds those fields to the body next to ``detail`` and
  ``code`` (e.g. ``approvers`` of ``approval.limit_exceeded``, A-03-T07).
"""

from __future__ import annotations

from typing import Any

from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None or not isinstance(exc, APIException):
        return response
    data = response.data
    if isinstance(data, dict) and set(data) == {"detail"}:
        codes = exc.get_codes()
        if isinstance(codes, str):
            data["code"] = codes
        extra = getattr(exc, "extra", None)
        if isinstance(extra, dict):
            data.update({k: v for k, v in extra.items() if k not in ("detail", "code")})
    return response
