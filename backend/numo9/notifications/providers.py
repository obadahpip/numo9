"""Email provider adapters for custom sending domains (A-07-T05).

A provider creates the domain on its side and tells us the DKIM key and the return-path (bounce)
host the organisation must publish. The transactional email provider is chosen in SP-03; its
adapter implements ``DomainProvider`` and registers under its name, selected by
``NUMO9_EMAIL_DOMAIN_PROVIDER``. Until then ``local`` is used: Numo9 generates the domain's DKIM
key itself (RSA 2048, private key stored encrypted) — what an own MTA signing outgoing mail needs,
and a working stand-in in dev and staging.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class ProviderDomain:
    """What a provider answers for a domain."""

    provider_id: str
    dkim_selector: str
    dkim_host: str
    dkim_value: str
    dkim_record_type: str = "TXT"
    return_path_host: str = ""
    return_path_target: str = ""
    private_key: str = ""


class ProviderError(RuntimeError):
    """The provider refused or could not be reached."""


class DomainProvider(Protocol):
    name: str

    def create_domain(self, domain: str) -> ProviderDomain: ...

    def fetch_domain(self, provider_id: str, domain: str) -> ProviderDomain: ...

    def delete_domain(self, provider_id: str, domain: str) -> None: ...


_providers: dict[str, DomainProvider] = {}


def register_provider(provider: DomainProvider) -> DomainProvider:
    _providers[provider.name] = provider
    return provider


def get_provider(name: str | None = None) -> DomainProvider:
    wanted = name or str(getattr(settings, "NUMO9_EMAIL_DOMAIN_PROVIDER", "local"))
    try:
        return _providers[wanted]
    except KeyError:
        raise ProviderError(f"No email domain provider called {wanted!r}") from None


def return_path_target() -> str:
    return str(getattr(settings, "NUMO9_EMAIL_RETURN_PATH_TARGET", "bounces.numo9.ca"))


class LocalDkimProvider:
    """Numo9 holds the DKIM key itself (see the module docstring)."""

    name = "local"

    def create_domain(self, domain: str) -> ProviderDomain:
        selector = f"numo9-{timezone.now():%Y%m}"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        private = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        return ProviderDomain(
            provider_id=f"local:{domain}",
            dkim_selector=selector,
            dkim_host=f"{selector}._domainkey.{domain}",
            dkim_value=f"v=DKIM1; k=rsa; p={base64.b64encode(public).decode()}",
            return_path_host=f"bounces.{domain}",
            return_path_target=return_path_target(),
            private_key=private,
        )

    def fetch_domain(self, provider_id: str, domain: str) -> ProviderDomain:
        raise ProviderError("The local provider keeps no records of its own: they are stored here.")

    def delete_domain(self, provider_id: str, domain: str) -> None:
        return None


register_provider(LocalDkimProvider())
