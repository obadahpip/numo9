"""Custom sending domains (A-07-T05): add a domain at the provider, store the DNS records.

``add_domain(domain, from_local_part="billing")`` in the active organisation:

1. normalises and validates the name (lower case, a real host name, not Numo9's own domain and
   not a public mailbox domain such as gmail.com — nobody can publish DNS records there);
2. creates it at the email provider (``providers.get_provider()``), which returns the DKIM key
   and the return-path host;
3. stores the ``SendingDomain`` (``pending``) and the four records the organisation must add:

   | Record | Host | Type | Value |
   |---|---|---|---|
   | SPF | the domain | TXT | ``v=spf1 include:<NUMO9_EMAIL_SPF_INCLUDE> ~all`` |
   | DKIM | ``<selector>._domainkey.<domain>`` | TXT (or CNAME, provider's choice) | the key |
   | DMARC | ``_dmarc.<domain>`` | TXT | ``v=DMARC1; p=quarantine; adkim=r; aspf=r`` |
   | Return path | ``bounces.<domain>`` | CNAME | the provider's bounce host |

``refresh_from_provider(sending_domain)`` fetches the DKIM record again (a provider that rotated
its key) and resets that record's check; ``remove_domain`` deletes it at the provider and soft
deletes it here. The DNS check is A-07-T06.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import transaction

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.context import current_org

from .models import (
    DOMAIN,
    DomainStatus,
    RecordKind,
    RecordStatus,
    SendingDomain,
    SendingDomainRecord,
)
from .providers import ProviderDomain, ProviderError, get_provider

PUBLIC_MAILBOX_DOMAINS = frozenset(
    {
        "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
        "yahoo.com", "yahoo.ca", "icloud.com", "me.com", "aol.com", "proton.me",
        "protonmail.com", "videotron.ca", "sympatico.ca", "shaw.ca", "rogers.com", "bell.net",
    }
)  # fmt: skip
DMARC_VALUE = "v=DMARC1; p=quarantine; adkim=r; aspf=r"


def spf_value() -> str:
    include = str(getattr(settings, "NUMO9_EMAIL_SPF_INCLUDE", "spf.numo9.ca"))
    return f"v=spf1 include:{include} ~all"


def normalise(domain: str) -> str:
    return (domain or "").strip().lower().rstrip(".").removeprefix("www.")


def _check_name(domain: str) -> None:
    own = normalise(str(getattr(settings, "NUMO9_EMAIL_OWN_DOMAIN", "numo9.ca")))
    if not DOMAIN.match(domain):
        raise api_error(errors.EMAIL_DOMAIN_INVALID, domain=domain)
    if domain in PUBLIC_MAILBOX_DOMAINS or domain == own or domain.endswith(f".{own}"):
        raise api_error(errors.EMAIL_DOMAIN_NOT_YOURS, domain=domain)


def _records(sending_domain: SendingDomain, answer: ProviderDomain) -> list[SendingDomainRecord]:
    rows = [
        (RecordKind.SPF, "TXT", sending_domain.domain, spf_value()),
        (RecordKind.DKIM, answer.dkim_record_type, answer.dkim_host, answer.dkim_value),
        (RecordKind.DMARC, "TXT", f"_dmarc.{sending_domain.domain}", DMARC_VALUE),
    ]
    if answer.return_path_host:
        rows.append(
            (RecordKind.RETURN_PATH, "CNAME", answer.return_path_host, answer.return_path_target)
        )
    return [
        SendingDomainRecord(
            organisation=sending_domain.organisation,
            sending_domain=sending_domain,
            kind=kind,
            record_type=record_type,
            host=host,
            value=value,
        )
        for kind, record_type, host, value in rows
    ]


def add_domain(domain: str, from_local_part: str = "billing", user: Any = None) -> SendingDomain:
    organisation = current_org()
    if organisation is None:
        raise ValueError("add_domain() runs in an organisation context")
    name = normalise(domain)
    _check_name(name)
    if SendingDomain.objects.filter(domain=name, deleted_at__isnull=True).exists():
        raise api_error(errors.EMAIL_DOMAIN_EXISTS, domain=name)
    provider = get_provider()
    try:
        answer = provider.create_domain(name)
    except ProviderError as exc:
        raise api_error(errors.EMAIL_DOMAIN_PROVIDER) from exc
    with transaction.atomic():
        sending_domain = SendingDomain(
            organisation=organisation,
            domain=name,
            from_local_part=from_local_part or "billing",
            provider=provider.name,
            provider_domain_id=answer.provider_id,
            dkim_selector=answer.dkim_selector,
            dkim_private_key=answer.private_key,
            created_by=user if getattr(user, "pk", None) else None,
        )
        sending_domain.save()
        SendingDomainRecord.objects.bulk_create(_records(sending_domain, answer))
    return sending_domain


def refresh_from_provider(sending_domain: SendingDomain) -> SendingDomain:
    """Fetch the DKIM record again (key rotation); a changed value must be checked again."""
    provider = get_provider(sending_domain.provider)
    try:
        answer = provider.fetch_domain(sending_domain.provider_domain_id, sending_domain.domain)
    except ProviderError as exc:
        raise api_error(errors.EMAIL_DOMAIN_PROVIDER) from exc
    record = sending_domain.records.get(kind=RecordKind.DKIM)
    if (record.host, record.value, record.record_type) != (
        answer.dkim_host,
        answer.dkim_value,
        answer.dkim_record_type,
    ):
        record.host, record.value = answer.dkim_host, answer.dkim_value
        record.record_type = answer.dkim_record_type
        record.status, record.found, record.checked_at = RecordStatus.UNCHECKED, "", None
        record.save()
        sending_domain.dkim_selector = answer.dkim_selector
        if sending_domain.status == DomainStatus.VERIFIED:
            sending_domain.status = DomainStatus.PARTIAL
        sending_domain.save()
    return sending_domain


def remove_domain(sending_domain: SendingDomain) -> None:
    provider = get_provider(sending_domain.provider)
    try:
        provider.delete_domain(sending_domain.provider_domain_id, sending_domain.domain)
    except ProviderError as exc:
        raise api_error(errors.EMAIL_DOMAIN_PROVIDER) from exc
    sending_domain.soft_delete()


def sender_for(organisation: Any) -> tuple[str, str]:
    """(From, Reply-To) for an organisation's emails (A-07 business rule).

    A **verified** sending domain sends as ``<brand name> <billing@its-domain>``; otherwise the
    email goes from Numo9's address with Reply-To the organisation's email address (its settings),
    so answers still reach the organisation and no receiver sees a From that fails DMARC.
    """
    from email.utils import formataddr, parseaddr

    from numo9.orgsettings.models import OrganisationSettings
    from numo9.tenancy.context import org_context

    from .templating import brand_for

    with org_context(organisation):
        verified = (
            SendingDomain.objects.filter(status=DomainStatus.VERIFIED, deleted_at__isnull=True)
            .order_by("verified_at", "pk")
            .first()
        )
        profile = OrganisationSettings.objects.filter(deleted_at__isnull=True).first()
    name = brand_for(organisation).name
    if verified is not None:
        return formataddr((name, verified.from_address)), ""
    default_name, default_address = parseaddr(str(settings.DEFAULT_FROM_EMAIL))
    reply_to = profile.email if profile is not None and profile.email else ""
    return formataddr((f"{name} via {default_name or 'Numo9'}", default_address)), reply_to
