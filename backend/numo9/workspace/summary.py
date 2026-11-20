"""Directory summary refresh (V-01-T03).

``OrgDirectorySummary`` rows are rebuilt from the source records — never edited by hand:

- ``refresh_organisation(org)`` — recompute the organisation's facts once and write one row per
  practice actively assigned to it (rows of practices that no longer serve it are deleted);
- ``schedule_refresh(org_id)`` — what the signals call (``signals.py``): after the current
  transaction commits (once per organisation per transaction, however many records changed), or at
  once outside a transaction. A change is in the directory as soon as its transaction commits
  (acceptance: < 5 s); a failing refresh is logged and never fails the user's save — the nightly
  rebuild repairs any drift;
- ``rebuild_all()`` — the nightly job (``tasks.py``) and ``manage.py rebuild_directory``: every
  active assignment, and orphan rows removed.

Where each fact comes from:

=====================  ======================================================================
name, legal_name,      ``OrganisationSettings`` (A-05): display name (else ``Organisation.name``),
industry, province,    legal name, industry, physical province (else mailing), fiscal year end
fye_month, fye_day
bn                     ``TaxRegistration`` (A-05) of type BN, status registered (latest start)
lock_date              the latest ``LockDate`` (A-05) date of any module and level (V-04)
owner_name/email       the organisation's ``owner`` membership (earliest)
package, status,       the entitlement engine (U-03): package code; Organisation.status mapped to
trial_ends_at,         the directory status (active/grace → paid, cancelled → archived); a
payroll_enabled        trialing subscription's period end; Payroll entitled
gst_cycle,             **providers** registered by later phases (``register_summary_provider``):
overdue_count,         empty / 0 until a provider answers
unfiled_count
tags                   the tags provider (V-02 ``register_tags_provider``), per practice
=====================  ======================================================================

``search_vector`` is computed by PostgreSQL (configuration ``simple`` over ``unaccent``): name,
legal name and BN weigh most, then owner and tags, then industry and the province (code and its
English and French names, so "quebec" finds QC organisations).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from django.db import connection, transaction
from django.utils import timezone, translation

from numo9.orgsettings.models import (
    OrganisationSettings,
    RegistrationStatus,
    RegistrationType,
    TaxRegistration,
)
from numo9.orgsettings.validators import Province
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    Practice,
    PracticeAssignment,
)

from .models import DirectoryStatus, OrgDirectorySummary

logger = logging.getLogger("numo9.workspace")

#: Organisation status (tenancy) → directory status.
DIRECTORY_STATUS: dict[str, str] = {
    OrganisationStatus.DEMO: DirectoryStatus.DEMO,
    OrganisationStatus.TRIAL: DirectoryStatus.TRIAL,
    OrganisationStatus.ACTIVE: DirectoryStatus.PAID,
    OrganisationStatus.GRACE: DirectoryStatus.PAID,
    OrganisationStatus.READ_ONLY: DirectoryStatus.READ_ONLY,
    OrganisationStatus.CANCELLED: DirectoryStatus.ARCHIVED,
}

#: Fields a summary provider may fill (later phases: GST/HST returns, invoices, filings).
PROVIDER_FIELDS: frozenset[str] = frozenset({"gst_cycle", "overdue_count", "unfiled_count"})

SummaryProvider = Callable[[Organisation], Mapping[str, Any]]
TagsProvider = Callable[[Practice, Organisation], Iterable[str]]

_providers: dict[str, SummaryProvider] = {}
_tags_provider: TagsProvider | None = None


def register_summary_provider(name: str, provider: SummaryProvider) -> None:
    """Add (or replace) a provider of ``PROVIDER_FIELDS`` for every organisation's row."""
    _providers[name] = provider


def unregister_summary_provider(name: str) -> None:
    _providers.pop(name, None)


def register_tags_provider(provider: TagsProvider | None) -> None:
    """The practice's tags of an organisation (V-02); ``None`` removes it."""
    global _tags_provider
    _tags_provider = provider


# ---- facts ------------------------------------------------------------------------------------


@dataclass
class _Facts:
    values: dict[str, Any]
    search_extra: str  # province names for the search vector


def _province_names(code: str) -> str:
    if code not in Province.values:
        return ""
    label = Province(code).label
    names = set()
    for language in ("en-ca", "fr-ca"):
        with translation.override(language):
            names.add(str(label))
    return " ".join(sorted(names))


def _settings_facts(organisation: Organisation) -> dict[str, Any]:
    row = OrganisationSettings._base_manager.filter(
        organisation_id=organisation.pk, deleted_at__isnull=True
    ).first()
    if row is None:
        return {"name": organisation.name}
    province = row.physical_province if not row.physical_same_as_mailing else ""
    return {
        "name": row.display_name or organisation.name,
        "legal_name": row.legal_name,
        "industry": row.industry,
        "province": (province or row.mailing_province or "").upper(),
        "fye_month": row.fye_month,
        "fye_day": row.fye_day,
    }


def _business_number(organisation: Organisation) -> str:
    registration = (
        TaxRegistration._base_manager.filter(
            organisation_id=organisation.pk,
            deleted_at__isnull=True,
            type=RegistrationType.BN,
            status=RegistrationStatus.ACTIVE,
        )
        .order_by("-effective_from", "-id")
        .first()
    )
    return registration.number[:9] if registration else ""


def _lock_date(organisation: Organisation) -> Any:
    from django.db.models import Max

    from numo9.orgsettings.models import LockDate

    latest = LockDate._base_manager.filter(
        organisation_id=organisation.pk, deleted_at__isnull=True, date__isnull=False
    ).aggregate(latest=Max("date"))
    return latest["latest"]


def _owner(organisation: Organisation) -> dict[str, str]:
    owner = (
        OrganisationMember.objects.filter(organisation=organisation, role=OrganisationRole.OWNER)
        .select_related("user")
        .order_by("created_at", "pk")
        .first()
    )
    if owner is None:
        return {"owner_name": "", "owner_email": ""}
    return {"owner_name": owner.user.name, "owner_email": owner.user.email}


def _commercial(organisation: Organisation) -> dict[str, Any]:
    from numo9.entitlements.engine import resolve_entitlements
    from numo9.entitlements.models import SubscriptionStatus, current_subscription

    subscription = current_subscription(organisation)
    entitlements = resolve_entitlements(organisation, record=False)
    trialing = subscription is not None and subscription.status == SubscriptionStatus.TRIALING
    return {
        "package": entitlements.package or "",
        "status": DIRECTORY_STATUS.get(organisation.status, DirectoryStatus.TRIAL),
        "trial_ends_at": subscription.current_period_end if trialing and subscription else None,
        "payroll_enabled": "payroll" in entitlements.products,
    }


def _provided(organisation: Organisation) -> dict[str, Any]:
    values: dict[str, Any] = {"gst_cycle": "", "overdue_count": 0, "unfiled_count": 0}
    for name, provider in _providers.items():
        try:
            answer = dict(provider(organisation))
        except Exception:  # a provider's bug must not empty the directory
            logger.exception("Directory summary provider %s failed", name)
            continue
        unknown = set(answer) - PROVIDER_FIELDS
        if unknown:
            logger.error("Directory summary provider %s returned %s", name, sorted(unknown))
        values.update({k: v for k, v in answer.items() if k in PROVIDER_FIELDS})
    return values


def organisation_facts(organisation: Organisation) -> _Facts:
    """Every practice-independent fact of the organisation's directory rows."""
    values: dict[str, Any] = {
        "legal_name": "",
        "industry": "",
        "province": "",
        "fye_month": 12,
        "fye_day": 31,
    }
    values.update(_settings_facts(organisation))
    values["bn"] = _business_number(organisation)
    values["lock_date"] = _lock_date(organisation)
    values.update(_owner(organisation))
    values.update(_commercial(organisation))
    values.update(_provided(organisation))
    return _Facts(values=values, search_extra=_province_names(values["province"]))


def _tags(practice: Practice, organisation: Organisation) -> list[str]:
    if _tags_provider is None:
        return []
    try:
        return sorted({str(tag) for tag in _tags_provider(practice, organisation)})
    except Exception:
        logger.exception("Directory tags provider failed")
        return []


# ---- writing rows -----------------------------------------------------------------------------

_VECTOR_SQL = """
UPDATE workspace_orgdirectorysummary SET search_vector =
    setweight(to_tsvector('simple', unaccent(name || ' ' || legal_name || ' ' || bn)), 'A')
    || setweight(to_tsvector('simple', unaccent(
        owner_name || ' ' || owner_email || ' ' || regexp_replace(owner_email, '[@.]', ' ', 'g')
        || ' '
        || coalesce((SELECT string_agg(value, ' ') FROM jsonb_array_elements_text(tags)), '')
    )), 'B')
    || setweight(to_tsvector('simple', unaccent(industry || ' ' || province || ' ' || %s)), 'C')
WHERE id = %s
"""


def _write_vector(row_id: int, search_extra: str) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(_VECTOR_SQL, [search_extra, row_id])


def refresh_organisation(organisation: Organisation | int) -> int:
    """Rebuild the organisation's directory rows; returns how many rows it now has."""
    if not isinstance(organisation, Organisation):
        found = Organisation.objects.filter(pk=organisation).first()
        if found is None:
            return 0  # deleted meanwhile: its rows went with it
        organisation = found
    practices = list(
        Practice.objects.filter(
            assignments__organisation=organisation, assignments__active=True
        ).distinct()
    )
    with transaction.atomic():
        OrgDirectorySummary.objects.filter(organisation=organisation).exclude(
            practice__in=practices
        ).delete()
        if not practices:
            return 0
        facts = organisation_facts(organisation)
        now = timezone.now()
        for practice in practices:
            row, _ = OrgDirectorySummary.objects.update_or_create(
                practice=practice,
                organisation=organisation,
                defaults={
                    **facts.values,
                    "tags": _tags(practice, organisation),
                    "refreshed_at": now,
                },
            )
            _write_vector(row.pk, facts.search_extra)
    return len(practices)


def rebuild_all(progress: Callable[[int, int], None] | None = None) -> dict[str, int]:
    """Rebuild every row (nightly): each organisation with an active assignment, orphans removed."""
    organisation_ids = list(
        PracticeAssignment.objects.filter(active=True)
        .values_list("organisation_id", flat=True)
        .distinct()
        .order_by("organisation_id")
    )
    removed, _ = OrgDirectorySummary.objects.exclude(organisation_id__in=organisation_ids).delete()
    rows = 0
    for index, organisation_id in enumerate(organisation_ids, start=1):
        rows += refresh_organisation(organisation_id)
        if progress is not None and (index % 100 == 0 or index == len(organisation_ids)):
            progress(index, len(organisation_ids))
    return {"organisations": len(organisation_ids), "rows": rows, "removed": removed}


# ---- scheduling (signals) ---------------------------------------------------------------------


class _Refresh:
    """An on-commit refresh of one organisation; equal callbacks are queued only once."""

    def __init__(self, organisation_id: int) -> None:
        self.organisation_id = organisation_id
        self.ran = False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Refresh) and other.organisation_id == self.organisation_id

    def __hash__(self) -> int:
        return hash(("workspace-refresh", self.organisation_id))

    def __call__(self) -> None:
        self.ran = True
        try:
            refresh_organisation(self.organisation_id)
        except Exception:  # never fail the user's (already committed) change
            logger.exception("Directory refresh of organisation %s failed", self.organisation_id)


def schedule_refresh(organisation_id: int | None) -> None:
    """Refresh the organisation's directory rows when the current transaction commits."""
    if organisation_id is None:
        return
    callback = _Refresh(organisation_id)
    if connection.in_atomic_block and any(
        isinstance(queued, _Refresh) and queued == callback and not queued.ran
        for _, queued, *_ in connection.run_on_commit
    ):
        return
    transaction.on_commit(callback)


def tags_changed(practice: Practice, organisations: Iterable[Organisation | int]) -> None:
    """V-02 calls this after the practice's tags of these organisations changed."""
    del practice  # every practice's row of the organisation is rebuilt (cheap, one org at a time)
    for organisation in organisations:
        schedule_refresh(
            organisation.pk if isinstance(organisation, Organisation) else organisation
        )
