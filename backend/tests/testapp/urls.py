"""Test-only URLs exposing the tenant context (used with override_settings(ROOT_URLCONF=...))."""

from django.http import HttpRequest, JsonResponse
from django.urls import path, re_path

from numo9.tenancy.context import acting_practice, current_org

from . import api
from .models import Widget


def context_view(request: HttpRequest) -> JsonResponse:
    org, practice = current_org(), acting_practice()
    return JsonResponse(
        {
            "org": str(org.public_id) if org else None,
            "practice": str(practice.public_id) if practice else None,
            "request_org": str(request.organisation.public_id)  # type: ignore[attr-defined]
            if request.organisation  # type: ignore[attr-defined]
            else None,
        }
    )


def widgets_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"labels": sorted(Widget.objects.values_list("label", flat=True))})


def boom_view(request: HttpRequest) -> JsonResponse:
    raise RuntimeError("view failed")


urlpatterns = [
    path("boom/", boom_view),
    path("ctx/", context_view),
    path("widgets/", widgets_view),
    re_path(r"^o/[^/]+/ctx/$", context_view),
    re_path(r"^o/[^/]+/widgets/$", widgets_view),
    re_path(r"^api/v1/o/[^/]+/ctx/$", context_view),
    re_path(r"^api/v1/o/[^/]+/widgets/$", api.WidgetList.as_view()),
    re_path(r"^api/v1/o/[^/]+/widgets/(?P<public_id>[0-9a-f-]+)/$", api.WidgetDetail.as_view()),
    re_path(
        r"^api/v1/o/[^/]+/unscoped-widgets/(?P<public_id>[0-9a-f-]+)/$",
        api.UnscopedWidgetDetail.as_view(),
    ),
    re_path(r"^api/v1/o/(?P<org_id>[^/]+)/organisation/$", api.OrganisationDetail.as_view()),
    path("api/v1/no-org/widgets/", api.WidgetList.as_view()),
]
