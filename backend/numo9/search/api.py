"""``GET /api/v1/o/<org>/search?q=…`` (A-09-T05): the command palette's results.

One answer for the active organisation, grouped: ``records`` (the index — contacts, accounts,
journals, documents, users, the organisation), ``settings``, ``reports``, ``navigation`` (the
static entries, in the request's language).

**Filtering** — a record or entry needing a permission the user lacks in this organisation is
left out entirely; one whose product isn't in the organisation's package stays, ``locked``, with
the product named (``reason``) — never hidden, never a redirect (U-03 rule).

**Parsing and ranking** — the query is matched as a code or number (``54`` → account 5400),
as words (full text, every word a prefix: ``cedar roo``, accents ignored), as an amount
(``1,130`` / ``1130.00`` / ``$1,130`` find a 1,130.00 journal) and, for typos, by trigram
similarity of the title. Rank: exact code > code prefix > amount > full text (by its rank) >
trigram (by similarity).
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import F, Q
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org
from numo9.workspace.search import query_words

from .models import SearchDocument
from .static import NAVIGATION, REPORTS, SETTINGS, match_static

EVERYONE_HERE = "organisation.profile.view"  # every organisation and practice role has it
MAX_RESULTS = 20
TRIGRAM_MIN = 0.3
_AMOUNT = re.compile(r"^\$?\s*-?\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?$|^\$?\s*-?\d+(?:\.\d{1,2})?$")
_CODE = re.compile(r"^[A-Za-z]{0,6}-?\d[\w-]*$")

TIER_EXACT_CODE, TIER_CODE_PREFIX, TIER_AMOUNT, TIER_TEXT, TIER_TRIGRAM = 5, 4, 3, 2, 1


def parse_amount(query: str) -> Decimal | None:
    """``1,130`` / ``1 130.00`` / ``$1130`` → 1130.00 (None when the query isn't an amount)."""
    text = query.strip()
    if not _AMOUNT.match(text):
        return None
    try:
        return Decimal(re.sub(r"[$,\s]", "", text)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def looks_like_code(query: str) -> bool:
    return bool(_CODE.match(query.strip()))


def ranked_documents(query: str, limit: int = MAX_RESULTS) -> list[tuple[int, float, Any]]:
    """``(tier, score, document)`` of the active organisation's index, best first."""
    rows = SearchDocument.objects.all()
    found: dict[int, tuple[int, float, Any]] = {}

    def keep(tier: int, score: float, document: Any) -> None:
        best = found.get(document.pk)
        if best is None or (tier, score) > best[:2]:
            found[document.pk] = (tier, score, document)

    text = query.strip()
    if looks_like_code(text):
        for document in rows.filter(code__iexact=text)[:limit]:
            keep(TIER_EXACT_CODE, 1.0, document)
        for document in rows.filter(code__istartswith=text).order_by("code")[:limit]:
            keep(TIER_CODE_PREFIX, 1.0 / (1 + len(document.code)), document)
    amount = parse_amount(text)
    if amount is not None:
        for document in rows.filter(Q(amount=amount) | Q(amount=-amount))[:limit]:
            keep(TIER_AMOUNT, 1.0, document)
    words = query_words(text)
    if words:
        search = SearchQuery(
            " & ".join(f"{w}:*" for w in words), search_type="raw", config="simple"
        )
        matched = (
            rows.filter(search_vector=search)
            .annotate(rank=SearchRank(F("search_vector"), search))
            .order_by("-rank")[:limit]
        )
        for document in matched:
            keep(TIER_TEXT, float(document.rank), document)
        if len(text) >= 3:
            similar = (
                rows.annotate(similarity=TrigramSimilarity("title", text))
                .filter(similarity__gte=TRIGRAM_MIN)
                .order_by("-similarity")[:limit]
            )
            for document in similar:
                keep(TIER_TRIGRAM, float(document.similarity), document)
    ordered = sorted(found.values(), key=lambda item: (-item[0], -item[1], item[2].title))
    return ordered[:limit]


class _Gate:
    """Permission and package checks of one request (each key decided once)."""

    def __init__(self, user: Any, organisation: Any) -> None:
        from numo9.entitlements.cache import entitlements_for
        from numo9.rbac.resolver import organisation_permissions

        self.permissions = organisation_permissions(user, organisation)
        self.entitlements = entitlements_for(organisation)
        self._products: dict[str, str] = {}

    def allowed(self, permission_key: str) -> bool:
        return not permission_key or permission_key in self.permissions

    def lock(self, feature_key: str) -> str:
        """ "" when the package includes the feature, else the reason (naming the product)."""
        if not feature_key or self.entitlements.allows(feature_key):
            return ""
        if feature_key not in self._products:
            from numo9.catalogue.models import FeatureKey
            from numo9.catalogue.texts import product_name

            code = (
                FeatureKey.objects.filter(key=feature_key)
                .values_list("product__code", flat=True)
                .first()
            )
            self._products[feature_key] = product_name(code) if code else ""
        product = self._products[feature_key]
        if product:
            return _("Part of %(product)s, which isn't in this organisation's package.") % {
                "product": product
            }
        return _("Not in this organisation's package.")


def search(user: Any, organisation: Any, query: str) -> dict[str, list[dict[str, Any]]]:
    gate = _Gate(user, organisation)
    records: list[dict[str, Any]] = []
    for tier, _score, document in ranked_documents(query):
        if not gate.allowed(document.permission_key):
            continue
        reason = gate.lock(document.feature_key)
        records.append(
            {
                "type": document.object_type,
                "id": document.object_id,
                "title": document.title,
                "subtitle": document.subtitle,
                "code": document.code,
                "amount": document.amount,
                "date": document.date,
                "url": document.url,
                "match": {
                    TIER_EXACT_CODE: "code",
                    TIER_CODE_PREFIX: "code_prefix",
                    TIER_AMOUNT: "amount",
                    TIER_TEXT: "text",
                    TIER_TRIGRAM: "similar",
                }[tier],
                "locked": bool(reason),
                "reason": reason,
            }
        )
    groups: dict[str, list[dict[str, Any]]] = {
        "records": records,
        SETTINGS: [],
        REPORTS: [],
        NAVIGATION: [],
    }
    for entry in match_static(query):
        if not gate.allowed(entry.permission_key):
            continue
        reason = gate.lock(entry.feature_key)
        groups[entry.group].append(
            {
                "key": entry.key,
                "title": str(entry.title),
                "url": f"/o/{organisation.public_id}/{entry.path}".rstrip("/"),
                "locked": bool(reason),
                "reason": reason,
            }
        )
    return groups


class RecordResultSerializer(serializers.Serializer[Any]):
    type = serializers.CharField(help_text="contacts.contact, ledger.account, …")
    id = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, allow_null=True)
    date = serializers.DateField(allow_null=True)
    url = serializers.CharField()
    match = serializers.ChoiceField(
        choices=[(m, m) for m in ("code", "code_prefix", "amount", "text", "similar")]
    )
    locked = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)


class StaticResultSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    title = serializers.CharField()
    url = serializers.CharField()
    locked = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)


class SearchResultSerializer(serializers.Serializer[Any]):
    query = serializers.CharField(allow_blank=True)
    records = RecordResultSerializer(many=True)
    settings = StaticResultSerializer(many=True)
    reports = StaticResultSerializer(many=True)
    navigation = StaticResultSerializer(many=True)


class SearchView(APIView):
    # Every result is checked against the user's permissions and the package (above); anyone
    # who can open the organisation may search it (every organisation and practice role).
    required_feature = CORE

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="search",
        summary="Search the organisation: records, settings, reports, navigation",
        parameters=[OpenApiParameter("q", OpenApiTypes.STR, description="What to find")],
        responses=SearchResultSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = current_org()
        query = (request.query_params.get("q") or "").strip()[:200]
        if organisation is None or not query:
            body: dict[str, Any] = {
                "query": query,
                "records": [],
                "settings": [],
                "reports": [],
                "navigation": [],
            }
            return Response(SearchResultSerializer(body).data)
        body = {"query": query, **search(request.user, organisation, query)}
        return Response(SearchResultSerializer(body).data)
