"""django-allauth adapter (A-02): Numo9's account rules on top of allauth's defaults."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


@dataclass(frozen=True)
class Brand:
    """What emails call the site: the product, at the web app's address (not the API host)."""

    name: str
    domain: str


def brand() -> Brand:
    return Brand(name="Numo9", domain=urlsplit(settings.FRONTEND_URL).netloc or "numo9.ca")


class AccountAdapter(DefaultAccountAdapter):  # type: ignore[misc]  # allauth is untyped
    def send_mail(self, template_prefix: str, email: str, context: dict[str, Any]) -> None:
        super().send_mail(template_prefix, email, {"current_site": brand(), **context})
