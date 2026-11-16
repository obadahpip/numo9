"""DNS verification of sending domains (A-07-T06): SPF, DKIM, DMARC, return path.

``check_domain(sending_domain)`` looks up each record of the domain with dnspython and sets its
status, what was found and when:

| Record | Correct when |
|---|---|
| SPF | exactly one ``v=spf1`` TXT record at the domain, and it includes Numo9's SPF host |
| DKIM | the TXT record at ``<selector>._domainkey`` carries the same ``p=`` key (spaces and quote
  splits ignored) — or, for a CNAME DKIM record, points at the provider's host |
| DMARC | a ``v=DMARC1`` TXT record at ``_dmarc`` with a ``p=`` policy (any policy passes) |
| Return path | the CNAME points at the provider's bounce host |

``missing`` = no such record (NXDOMAIN, no answer); ``wrong`` = a record exists but is not right
(``found`` shows what is there, so the settings page can say what to fix). A lookup that times
out or a DNS server that fails leaves the record as it was (unknown is not wrong).

The domain's status follows its records: all correct → ``verified`` (``verified_at`` kept from the
first time); any wrong → ``failed``; some correct → ``partial``; none → ``pending``.

``check_sending_domains`` (platform job, beat every 15 minutes) checks every domain that is not
verified yet and was added in the last 14 days, and every verified domain once a day (records
removed later are noticed); the settings page's "Check now" runs ``check_domain`` directly.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta

import dns.exception
import dns.resolver
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from numo9.jobs.queues import IO
from numo9.jobs.runtime import platform_job
from numo9.tenancy.context import org_context

from .models import DomainStatus, RecordKind, RecordStatus, SendingDomain, SendingDomainRecord

CHECK_JOB = "numo9.notifications.check_sending_domains"
NEW_DOMAIN_WINDOW = timedelta(days=14)
VERIFIED_RECHECK = timedelta(days=1)
LOOKUP_TIMEOUT = 5.0


class LookupFailed(Exception):
    """The DNS server did not answer (timeout, SERVFAIL): the result is unknown."""


def _resolve(name: str, rdtype: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = float(getattr(settings, "NUMO9_DNS_TIMEOUT", LOOKUP_TIMEOUT))
    try:
        answer = resolver.resolve(name, rdtype)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return []
    except (dns.exception.Timeout, dns.resolver.NoNameservers) as exc:
        raise LookupFailed(str(exc)) from exc
    if rdtype == "TXT":
        return [b"".join(r.strings).decode("utf-8", "replace") for r in answer]
    return [r.to_text() for r in answer]


#: (name, "TXT" | "CNAME") → values; tests replace it with a fake zone.
Resolve = Callable[[str, str], list[str]]
resolve: Resolve = _resolve


def _host(value: str) -> str:
    return value.strip().rstrip(".").lower()


def _dkim_key(value: str) -> str:
    match = re.search(r"(?:^|;)\s*p\s*=\s*([^;]*)", value.replace('"', ""))
    return re.sub(r"\s+", "", match.group(1)) if match else ""


def _judge(record: SendingDomainRecord, spf_include: str) -> tuple[str, str]:
    """(status, found) for one record."""
    if record.record_type == "CNAME":
        targets = [_host(v) for v in resolve(record.host, "CNAME")]
        if not targets:
            return RecordStatus.MISSING, ""
        ok = _host(record.value) in targets
        return (RecordStatus.OK if ok else RecordStatus.WRONG), targets[0]
    texts = resolve(record.host, "TXT")
    if record.kind == RecordKind.SPF:
        spf = [t for t in texts if t.lower().startswith("v=spf1")]
        if not spf:
            return RecordStatus.MISSING, ""
        if len(spf) > 1:  # two SPF records = SPF permerror for every receiver
            return RecordStatus.WRONG, " | ".join(spf)
        ok = f"include:{spf_include.lower()}" in spf[0].lower().split()
        return (RecordStatus.OK if ok else RecordStatus.WRONG), spf[0]
    if record.kind == RecordKind.DMARC:
        dmarc = [t for t in texts if t.replace(" ", "").upper().startswith("V=DMARC1")]
        if not dmarc:
            return RecordStatus.MISSING, ""
        has_policy = re.search(r"(?:^|;)\s*p\s*=\s*(none|quarantine|reject)\b", dmarc[0], re.I)
        return (RecordStatus.OK if has_policy else RecordStatus.WRONG), dmarc[0]
    if record.kind == RecordKind.DKIM:
        dkim = [t for t in texts if "p=" in t.replace(" ", "")]
        if not dkim:
            return RecordStatus.MISSING, ""
        expected = _dkim_key(record.value)
        ok = any(_dkim_key(t) == expected and expected for t in dkim)
        return (RecordStatus.OK if ok else RecordStatus.WRONG), dkim[0]
    first = texts[0] if texts else ""
    return (RecordStatus.OK if record.value in texts else RecordStatus.MISSING), first


def domain_status(statuses: list[str]) -> str:
    if statuses and all(s == RecordStatus.OK for s in statuses):
        return DomainStatus.VERIFIED
    if any(s == RecordStatus.WRONG for s in statuses):
        return DomainStatus.FAILED
    if any(s == RecordStatus.OK for s in statuses):
        return DomainStatus.PARTIAL
    return DomainStatus.PENDING


def check_domain(sending_domain: SendingDomain) -> SendingDomain:
    """Look up every record now and update the statuses (see the module docstring)."""
    include = str(getattr(settings, "NUMO9_EMAIL_SPF_INCLUDE", "spf.numo9.ca"))
    now = timezone.now()
    with org_context(sending_domain.organisation):
        records = list(sending_domain.records.all())
        for record in records:
            try:
                record.status, record.found = _judge(record, include)
            except LookupFailed:
                continue  # unknown: keep the previous result
            record.found = record.found[:2000]
            record.checked_at = now
            record.save(update_fields=["status", "found", "checked_at", "updated_at"])
        status = domain_status([r.status for r in records])
        sending_domain.status = status
        sending_domain.last_checked_at = now
        if status == DomainStatus.VERIFIED and sending_domain.verified_at is None:
            sending_domain.verified_at = now
        sending_domain.save(
            update_fields=["status", "last_checked_at", "verified_at", "updated_at"]
        )
    return sending_domain


def due_for_check(now: datetime | None = None) -> list[SendingDomain]:
    moment = timezone.now() if now is None else now
    recent = Q(created_at__gte=moment - NEW_DOMAIN_WINDOW) & ~Q(status=DomainStatus.VERIFIED)
    stale_verified = Q(status=DomainStatus.VERIFIED) & (
        Q(last_checked_at__isnull=True) | Q(last_checked_at__lt=moment - VERIFIED_RECHECK)
    )
    return list(
        SendingDomain.objects.unscoped(reason="sending-domain DNS check (A-07-T06)")
        .filter(deleted_at__isnull=True)
        .filter(recent | stale_verified)
        .select_related("organisation")
        .order_by("pk")
    )


@platform_job(name=CHECK_JOB, queue=IO)
def check_sending_domains() -> dict[str, int]:
    """Beat, every 15 minutes: check the domains that are due (see the module docstring)."""
    counts = {"checked": 0, "verified": 0}
    for sending_domain in due_for_check():
        check_domain(sending_domain)
        counts["checked"] += 1
        counts["verified"] += sending_domain.status == DomainStatus.VERIFIED
    return counts
