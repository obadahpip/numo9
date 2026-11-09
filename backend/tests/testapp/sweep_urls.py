"""URLconfs for the tenant sweep tests (A-01-T09).

``urlpatterns`` is a correctly isolated API; the ``leaky``, ``unclassified`` and ``unbuildable``
modules below re-use it plus one faulty route each.
"""

from django.http import HttpRequest, JsonResponse
from django.urls import path

from . import api


def ping(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True})


urlpatterns = [
    path("ping/", ping),
    path("api/v1/o/<uuid:org>/widgets/", api.WidgetList.as_view()),
    path("api/v1/o/<uuid:org>/widgets/<uuid:public_id>/", api.WidgetDetail.as_view()),
    path(
        "api/v1/o/<uuid:org>/unscoped-widgets/<uuid:public_id>/",
        api.UnscopedWidgetDetail.as_view(),
    ),
]
