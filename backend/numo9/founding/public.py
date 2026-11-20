"""Public founding counter (U-08-T08): ``GET /api/v1/public/founding`` — anyone.

What the website's counter widget ("427 of 1,000 founding places left") and the in-app pricing
read: ``total`` (the cap), ``allocated``, ``remaining = total − allocated`` and ``complete`` (no
place left: the widget shows "Offer complete"). The answer is the same for everyone and cached for
30 seconds (server cache and ``Cache-Control: public, max-age=30``); an allocation or a change of
cap clears the server copy (``clear_cache``), so only browsers and CDNs may lag 30 s.
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.rbac.drf import PUBLIC, requires_permission

from .models import FoundingCounter

CACHE_SECONDS = 30
CACHE_KEY = "founding:public-counter:v1"


def counter_body() -> dict[str, Any]:
    counter = FoundingCounter.current()
    return {
        "total": counter.cap,
        "allocated": counter.allocated,
        "remaining": counter.remaining,
        "complete": counter.remaining == 0,
    }


def public_counter() -> dict[str, Any]:
    body: dict[str, Any] | None = cache.get(CACHE_KEY)
    if body is None:
        body = counter_body()
        cache.set(CACHE_KEY, body, CACHE_SECONDS)
    return body


def clear_cache() -> None:
    cache.delete(CACHE_KEY)
    transaction.on_commit(lambda: cache.delete(CACHE_KEY))


class FoundingCounterSerializer(serializers.Serializer[Any]):
    total = serializers.IntegerField(help_text="Founding places offered (the cap)")
    allocated = serializers.IntegerField()
    remaining = serializers.IntegerField(help_text="total − allocated")
    complete = serializers.BooleanField(help_text="No place left: show 'Offer complete'")


class PublicFoundingCounterView(APIView):
    authentication_classes: list[type] = []  # the same answer for everyone; no session needed

    @requires_permission(PUBLIC)
    @extend_schema(
        operation_id="public_founding_counter",
        summary="Founding offer: places left (cached 30 s)",
        responses=FoundingCounterSerializer,
        auth=[],
    )
    def get(self, request: Request) -> Response:
        response = Response(FoundingCounterSerializer(public_counter()).data)
        response["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
        return response
