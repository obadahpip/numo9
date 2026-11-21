"""Static search entries (A-09-T04): settings pages, the reports catalogue, navigation.

Not records — the same for every organisation — so they live here, not in ``SearchDocument``,
and are matched in Python in the request's language: each entry has a title and **synonyms**
("lock date", "BN", "fiscal year", "année financière" …) and matches when every word of the
query starts a word of the title or a synonym, accents and case ignored. ``register_static()``
lets later modules add theirs (their reports, their settings sections).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from numo9.workspace.search import fold, query_words

SETTINGS, REPORTS, NAVIGATION = "settings", "reports", "navigation"


@dataclass(frozen=True)
class StaticEntry:
    key: str
    group: str
    title: Promise | str
    path: str  # under /o/<org>/
    synonyms: tuple[Promise | str, ...] = field(default_factory=tuple)
    permission_key: str = ""
    feature_key: str = ""

    def words(self) -> set[str]:
        text = " ".join([str(self.title), *(str(s) for s in self.synonyms)])
        return set(query_words(text))

    def matches(self, words: list[str]) -> bool:
        mine = self.words()
        return bool(words) and all(any(w.startswith(q) for w in mine) for q in words)

    def exact(self, query: str) -> bool:
        folded = fold(query.strip())
        return folded == fold(str(self.title)) or any(folded == fold(str(s)) for s in self.synonyms)


_entries: dict[str, StaticEntry] = {}


def register_static(*entries: StaticEntry) -> None:
    for entry in entries:
        _entries[entry.key] = entry


def static_entries() -> list[StaticEntry]:
    return list(_entries.values())


def match_static(query: str, entries: Iterable[StaticEntry] | None = None) -> list[StaticEntry]:
    words = query_words(query)
    found = [e for e in (entries if entries is not None else _entries.values()) if e.matches(words)]
    return sorted(found, key=lambda e: (not e.exact(query), str(e.title)))


register_static(
    # ---- settings pages (A-05) ---------------------------------------------------------------
    StaticEntry(
        "settings.general",
        SETTINGS,
        _("General settings"),
        "settings/general",
        (
            _("organisation profile"),
            _("address"),
            _("fiscal year"),
            _("fiscal year end"),
            _("year end"),
            _("time zone"),
            _("legal name"),
            "année financière",
            "fin d'exercice",
        ),
    ),
    StaticEntry(
        "settings.registrations",
        SETTINGS,
        _("Tax registrations"),
        "settings/registrations",
        (
            _("BN"),
            _("Business Number"),
            _("GST/HST number"),
            _("QST number"),
            "numéro d'entreprise",
            "TPS",
            "TVQ",
        ),
    ),
    StaticEntry(
        "settings.lock_dates",
        SETTINGS,
        _("Lock dates"),
        "settings/lock-dates",
        (_("lock date"), _("close the period"), _("period lock"), "date de verrouillage"),
    ),
    StaticEntry(
        "settings.users_roles",
        SETTINGS,
        _("Users and roles"),
        "settings/users-roles",
        (_("invite"), _("permissions"), _("approval limits"), "utilisateurs"),
        permission_key="organisation.members.view",
    ),
    StaticEntry(
        "settings.notifications",
        SETTINGS,
        _("Notification settings"),
        "settings/notifications",
        (_("email alerts"), _("notifications")),
    ),
    StaticEntry(
        "settings.subscription",
        SETTINGS,
        _("Subscription and billing"),
        "settings/subscription",
        (_("package"), _("invoice"), _("payment method"), _("trial"), "abonnement"),
    ),
    StaticEntry(
        "settings.audit_log",
        SETTINGS,
        _("Audit log"),
        "settings/audit-log",
        (_("history"), _("who changed"), "journal d'audit"),
    ),
    StaticEntry(
        "settings.email_domain",
        SETTINGS,
        _("Email sending domain"),
        "settings/email-domain",
        (_("SPF"), _("DKIM"), _("DMARC")),
    ),
    StaticEntry(
        "settings.package_features",
        SETTINGS,
        _("Package features"),
        "settings/package-features",
        (_("what's included"), _("feature matrix")),
    ),
    # ---- reports catalogue (Phase 1 reports, K-01…, register theirs) ----------------------
    StaticEntry(
        "reports.contact_statement",
        REPORTS,
        _("Customer statements"),
        "contacts",
        (_("statement"), _("aging"), "relevé"),
        permission_key="contacts.contacts.view",
        feature_key="accounting.contacts.read",
    ),
    # ---- navigation ------------------------------------------------------------------------
    StaticEntry("nav.home", NAVIGATION, _("Home"), "", (_("dashboard"), "accueil")),
    StaticEntry(
        "nav.contacts",
        NAVIGATION,
        _("Contacts"),
        "contacts",
        (_("customers"), _("suppliers"), "clients", "fournisseurs"),
        permission_key="contacts.contacts.view",
        feature_key="accounting.contacts.read",
    ),
    StaticEntry(
        "nav.chart_of_accounts",
        NAVIGATION,
        _("Chart of accounts"),
        "accounting/chart-of-accounts",
        (_("accounts"), _("GIFI"), "plan comptable"),
        permission_key="accounting.accounts.view",
        feature_key="accounting.chart_of_accounts.read",
    ),
    StaticEntry(
        "nav.journals",
        NAVIGATION,
        _("Journals"),
        "accounting/journals",
        (_("manual journal"), _("general ledger"), "écritures"),
        permission_key="accounting.journals.view",
        feature_key="accounting.journals.read",
    ),
    StaticEntry(
        "nav.documents",
        NAVIGATION,
        _("Documents"),
        "documents",
        (_("files"), _("receipts"), _("inbox"), "pièces justificatives"),
        permission_key="documents.file.view",
        feature_key="accounting.documents.read",
    ),
)
