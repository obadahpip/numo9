"""Helpers for notification and email tests (A-07)."""

from __future__ import annotations

from dataclasses import dataclass, field

from numo9.notifications.providers import ProviderDomain, ProviderError


@dataclass
class FakeProvider:
    """A mocked email provider: answers like an ESP's domain API; records the calls."""

    name: str = "fake-esp"
    dkim_value: str = "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC1"
    fail: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)

    def _answer(self, domain: str) -> ProviderDomain:
        return ProviderDomain(
            provider_id=f"esp-{domain}",
            dkim_selector="pm202611",
            dkim_host=f"pm202611._domainkey.{domain}",
            dkim_value=self.dkim_value,
            return_path_host=f"pm-bounces.{domain}",
            return_path_target="pm.mtasv.net",
        )

    def create_domain(self, domain: str) -> ProviderDomain:
        self.calls.append(("create", domain))
        if self.fail:
            raise ProviderError("down")
        return self._answer(domain)

    def fetch_domain(self, provider_id: str, domain: str) -> ProviderDomain:
        self.calls.append(("fetch", provider_id))
        if self.fail:
            raise ProviderError("down")
        return self._answer(domain)

    def delete_domain(self, provider_id: str, domain: str) -> None:
        self.calls.append(("delete", provider_id))
