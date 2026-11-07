"""Liveness endpoint used by load balancers, Compose healthchecks and deploy health gates."""

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})
