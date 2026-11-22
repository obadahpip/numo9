"""Phase 0 search providers (A-09-T03), registered in ``apps.ready``.

======================  ===========================================================  ==========
record                  indexed                                                      opens
======================  ===========================================================  ==========
contact (B-01)          display name; number; legal name, BN; its people's names,    contact
                        emails and phones (a person's change re-indexes the contact)
account (C-01)          code (exact / prefix: "54" → 5400); name in every language;  chart
                        description, type
journal (C-02)          number; narration **and every line's description** (Xero     journal
                        can't search journals — gap 52); date; total
organisation (A-01)     its name (the organisation's own home)                       home
user (A-02)             a member's name, email and role (one per membership)         users
document (A-06)         file name, sender, folder; period / tax year                 documents
======================  ===========================================================  ==========

Each document carries the permission that lets a user see the record and the feature key of its
product (gated results show a lock and the reason, never the record).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Sum

from .registry import Doc, index, register_dependent, register_provider


def _org(instance: Any) -> str:
    return str(instance.organisation.public_id)


def contact_document(contact: Any) -> Doc | None:
    if getattr(contact, "merged_into_id", None):
        return None  # merged away: the surviving contact is the result
    people = list(contact.people.filter(deleted_at__isnull=True)) if contact.pk else []
    body = " ".join(
        part
        for person in people
        for part in (person.first_name, person.last_name, person.email, person.phone)
        if part
    )
    first_email = next((p.email for p in people if p.email), "")
    return Doc(
        title=contact.display_name,
        subtitle=" · ".join(x for x in (contact.legal_name, first_email) if x),
        code=contact.number or "",
        body=" ".join(x for x in (body, contact.bn or "", contact.external_id or "") if x),
        url=f"/o/{_org(contact)}/contacts/{contact.public_id}",
        permission_key="contacts.contacts.view",
        feature_key="accounting.contacts.read",
    )


def account_document(account: Any) -> Doc | None:
    names = [str(v) for v in (account.name_i18n or {}).values() if v]
    return Doc(
        title=account.name_in("en-ca") or (names[0] if names else account.code),
        subtitle=account.get_type_display(),
        code=account.code,
        body=" ".join([*names, account.description or ""]),
        url=f"/o/{_org(account)}/accounting/chart-of-accounts?account={account.public_id}",
        permission_key="accounting.accounts.view",
        feature_key="accounting.chart_of_accounts.read",
    )


def journal_document(entry: Any) -> Doc | None:
    from numo9.ledger.models import JournalLine, JournalStatus
    from numo9.ledger.sequence import format_journal_number

    lines = JournalLine._base_manager.filter(
        organisation_id=entry.organisation_id, entry_id=entry.pk
    )
    descriptions = " ".join(d for d in lines.values_list("description", flat=True) if d)
    total = lines.aggregate(total=Sum("debit"))["total"] or Decimal("0")
    number = format_journal_number(entry.organisation, entry.number) if entry.number else ""
    # Drafts and journals waiting for approval say so (C-04-T14: approvers find them by narration).
    state = (
        str(JournalStatus(entry.status).label)
        if entry.status in (JournalStatus.DRAFT, JournalStatus.AWAITING_APPROVAL)
        else ""
    )
    return Doc(
        title=number or str(entry),
        subtitle=" — ".join(x for x in (state, (entry.narration or "")[:300]) if x),
        code=number,
        body=" ".join(x for x in (entry.narration or "", descriptions) if x),
        amount=total,
        date=entry.date,
        url=f"/o/{_org(entry)}/accounting/journals/{entry.public_id}",
        permission_key="accounting.journals.view",
        feature_key="accounting.journals.read",
    )


def organisation_document(organisation: Any) -> Doc | None:
    return Doc(
        title=organisation.name,
        url=f"/o/{organisation.public_id}",
        organisation_id=organisation.pk,
        object_id=str(organisation.public_id),
    )


def member_document(member: Any) -> Doc | None:
    user = member.user
    return Doc(
        title=user.name or user.email,
        subtitle=user.email,
        body=member.role,
        url=f"/o/{member.organisation.public_id}/settings/users-roles",
        permission_key="organisation.members.view",
        organisation_id=member.organisation_id,
        object_type="accounts.user",
        object_id=str(user.public_id),
    )


def document_document(document: Any) -> Doc | None:
    if getattr(document, "status", "") == "quarantined":
        return None  # a file with a virus can't be opened: never offered
    return Doc(
        title=document.name,
        subtitle=" · ".join(x for x in (document.sender, document.folder) if x),
        body=" ".join(str(x) for x in (document.period, document.tax_year) if x),
        url=f"/o/{_org(document)}/documents?document={document.public_id}",
        permission_key="documents.file.view",
        feature_key="accounting.documents.read",
    )


def _user_renamed(sender: Any, instance: Any, created: bool = False, **kwargs: Any) -> None:
    from numo9.tenancy.models import OrganisationMember

    if created:
        return
    for member in OrganisationMember.objects.filter(user=instance).select_related("user"):
        index(member)


def register_phase0_providers() -> None:
    from django.conf import settings
    from django.db.models.signals import post_save

    from numo9.contacts.models import Contact, ContactPerson
    from numo9.files.models import Document
    from numo9.ledger.models import Account, JournalEntry
    from numo9.ledger.services import ENTRY_WRITTEN
    from numo9.tenancy.models import Organisation, OrganisationMember

    register_provider(Contact, contact_document)
    register_dependent(ContactPerson, lambda person: person.contact)
    register_provider(Account, account_document)
    register_provider(JournalEntry, journal_document)
    if index not in ENTRY_WRITTEN:
        ENTRY_WRITTEN.append(index)  # bulk inserts and updates of the posting service
    register_provider(Organisation, organisation_document)
    register_provider(OrganisationMember, member_document)
    register_provider(Document, document_document)
    post_save.connect(
        _user_renamed,
        sender=settings.AUTH_USER_MODEL,
        dispatch_uid="numo9.search.user_renamed",
        weak=False,
    )
