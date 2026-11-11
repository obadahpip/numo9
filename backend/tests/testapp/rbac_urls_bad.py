from django.urls import path
from drf_spectacular.views import SpectacularJSONAPIView

from . import rbac_api
from .rbac_urls import urlpatterns as good

urlpatterns = [
    *good,
    path("api/v1/unknown-key/", rbac_api.UnknownKey.as_view()),
    path("api/v1/not-enforced/", rbac_api.NotEnforced.as_view()),
    path("api/v1/schema.json", SpectacularJSONAPIView.as_view()),  # third-party, not exempt
]
