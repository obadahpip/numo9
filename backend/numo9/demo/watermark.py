"""The demo watermark (U-07-T08): every document a demo organisation prints or downloads says
"DEMO — NOT A REAL DOCUMENT" across each page, in the document's language.

Registered with the document renderer (``numo9.documents.pdf.register_watermark``) when the app
loads. The organisation is the active tenant (documents render inside the organisation's
context) or ``context["organisation"]`` when a caller renders outside one.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _

from numo9.tenancy.context import current_org

from .exclusions import is_demo


def demo_watermark(context: dict[str, Any]) -> str:
    organisation = context.get("organisation") or current_org()
    if organisation is None or not hasattr(organisation, "is_demo"):
        return ""
    return _("DEMO — NOT A REAL DOCUMENT") if is_demo(organisation) else ""
