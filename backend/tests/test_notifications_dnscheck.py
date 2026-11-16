"""A-07-T06 — DNS verification job (dnspython) for SPF, DKIM, DMARC, return path; status per
record.

Acceptance: the status updates — a domain whose records are added step by step goes pending →
partial → verified, with each record's status, what was found and when; a wrong record (two SPF
records, SPF without Numo9's include, another DKIM key, DMARC without a policy, CNAME to another
host) is ``wrong`` and the domain ``failed``; a lookup timeout leaves the record as it was. The
beat job checks new unverified domains and verified domains once a day; the API's "check now".
Also: the real dnspython lookup path (NXDOMAIN → missing, TXT strings joined).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest import mock

import dns.resolver
import pytest
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.notifications import dnscheck, domains, providers
from numo9.notifications.models import SendingDomain
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.notification_helpers import FakeProvider

pytestmark = pytest.mark.django_db

DKIM = "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC1"


class Zone:
    """A fake DNS zone: (name, type) → values; ``timeout`` names fail like a dead server."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str], list[str]] = {}
        self.timeout: set[str] = set()

    def __call__(self, name: str, rdtype: str) -> list[str]:
        if name in self.timeout:
            raise dnscheck.LookupFailed("timeout")
        return self.records.get((name, rdtype), [])

    def add(self, name: str, rdtype: str, *values: str) -> None:
        self.records[(name, rdtype)] = list(values)


@pytest.fixture
def zone() -> Iterator[Zone]:
    fake = Zone()
    with mock.patch.object(dnscheck, "resolve", fake):
        yield fake


@pytest.fixture
def org(settings: Any) -> Iterator[Organisation]:
    provider = FakeProvider(dkim_value=DKIM)
    providers.register_provider(provider)
    settings.NUMO9_EMAIL_DOMAIN_PROVIDER = provider.name
    yield Organisation.objects.create(name="Refined Interiors Inc.")
    providers._providers.pop(provider.name, None)


def _domain(org: Organisation, name: str = "refined.ca") -> SendingDomain:
    with org_context(org):
        return domains.add_domain(name)


def _statuses(domain: SendingDomain) -> dict[str, str]:
    with org_context(domain.organisation):
        return {r.kind: r.status for r in domain.records.all()}


def test_status_updates_as_records_are_added(org: Organisation, zone: Zone) -> None:
    domain = _domain(org)
    dnscheck.check_domain(domain)
    assert domain.status == "pending" and domain.last_checked_at is not None
    assert set(_statuses(domain).values()) == {"missing"}

    zone.add(
        "refined.ca", "TXT", "google-site-verification=abc", "v=spf1 include:spf.numo9.ca ~all"
    )
    zone.add("pm202611._domainkey.refined.ca", "TXT", DKIM.replace("p=", "p= "))
    dnscheck.check_domain(domain)
    assert domain.status == "partial" and domain.verified_at is None
    assert _statuses(domain) == {
        "spf": "ok", "dkim": "ok", "dmarc": "missing", "return_path": "missing"
    }  # fmt: skip

    zone.add("_dmarc.refined.ca", "TXT", "v=DMARC1; p=none; rua=mailto:d@refined.ca")
    zone.add("pm-bounces.refined.ca", "CNAME", "PM.MTASV.NET.")
    dnscheck.check_domain(domain)
    assert domain.status == "verified" and domain.verified_at is not None
    first_verified = domain.verified_at
    with org_context(org):
        spf = domain.records.get(kind="spf")
    assert spf.found == "v=spf1 include:spf.numo9.ca ~all" and spf.checked_at is not None
    dnscheck.check_domain(domain)
    assert domain.verified_at == first_verified  # kept from the first time


@pytest.mark.parametrize(
    ("name", "rdtype", "values", "kind"),
    [
        ("refined.ca", "TXT", ["v=spf1 include:spf.numo9.ca ~all", "v=spf1 -all"], "spf"),
        ("refined.ca", "TXT", ["v=spf1 include:_spf.google.com ~all"], "spf"),
        ("pm202611._domainkey.refined.ca", "TXT", ["v=DKIM1; k=rsa; p=OTHERKEY"], "dkim"),
        ("_dmarc.refined.ca", "TXT", ["v=DMARC1; rua=mailto:x@refined.ca"], "dmarc"),
        ("pm-bounces.refined.ca", "CNAME", ["elsewhere.example.com."], "return_path"),
    ],
)
def test_wrong_records(
    org: Organisation, zone: Zone, name: str, rdtype: str, values: list[str], kind: str
) -> None:
    domain = _domain(org)
    zone.add(name, rdtype, *values)
    dnscheck.check_domain(domain)
    assert _statuses(domain)[kind] == "wrong"
    assert domain.status == "failed"
    with org_context(org):
        assert domain.records.get(kind=kind).found  # what was found is shown


def test_lookup_timeout_keeps_the_previous_result(org: Organisation, zone: Zone) -> None:
    domain = _domain(org)
    zone.add("refined.ca", "TXT", "v=spf1 include:spf.numo9.ca ~all")
    dnscheck.check_domain(domain)
    assert _statuses(domain)["spf"] == "ok"
    zone.timeout.add("refined.ca")
    dnscheck.check_domain(domain)
    assert _statuses(domain)["spf"] == "ok"


def test_beat_job_checks_what_is_due(org: Organisation, zone: Zone) -> None:
    new = _domain(org, "refined.ca")
    old = _domain(org, "old-unverified.ca")
    verified = _domain(org, "verified.ca")
    with org_context(org):
        SendingDomain.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=30)
        )
        SendingDomain.objects.filter(pk=verified.pk).update(
            status="verified", last_checked_at=timezone.now() - timedelta(hours=2)
        )
    assert {d.pk for d in dnscheck.due_for_check()} == {new.pk}
    later = timezone.now() + timedelta(days=1)
    assert {d.pk for d in dnscheck.due_for_check(later)} == {new.pk, verified.pk}

    with mock.patch.object(dnscheck, "check_domain") as check:
        result = dnscheck.check_sending_domains.run()
    assert check.call_count == 1 and result["checked"] == 1


def test_check_now_api(org: Organisation, zone: Zone) -> None:
    domain = _domain(org)
    user = User.objects.create_user(email="dana@refined.ca", password="x" * 12, name="Dana")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    browser = Client()
    browser.force_login(user)
    zone.add("_dmarc.refined.ca", "TXT", "v=DMARC1; p=reject")
    response = browser.post(f"/api/v1/o/{org.public_id}/email-domains/{domain.public_id}/check")
    assert response.status_code == 200
    records = {r["kind"]: r for r in response.json()["records"]}
    assert records["dmarc"]["status"] == "ok" and records["dmarc"]["found"] == "v=DMARC1; p=reject"
    assert response.json()["status"] == "partial"


def test_dnspython_lookup_path() -> None:
    class Answer(list[Any]):
        pass

    txt = mock.Mock(strings=[b"v=spf1 include:", b"spf.numo9.ca ~all"])
    with mock.patch.object(dns.resolver.Resolver, "resolve", return_value=Answer([txt])):
        assert dnscheck._resolve("refined.ca", "TXT") == ["v=spf1 include:spf.numo9.ca ~all"]
    with mock.patch.object(dns.resolver.Resolver, "resolve", side_effect=dns.resolver.NXDOMAIN):
        assert dnscheck._resolve("nowhere.refined.ca", "TXT") == []
    with (
        mock.patch.object(dns.resolver.Resolver, "resolve", side_effect=dns.exception.Timeout),
        pytest.raises(dnscheck.LookupFailed),
    ):
        dnscheck._resolve("slow.refined.ca", "TXT")
