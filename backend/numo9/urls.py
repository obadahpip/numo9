"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from .health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/v1/", include("numo9.tenancy.urls")),
    path("api/v1/", include("numo9.security.urls")),
    # Sign-up, email verification, login, logout, password reset (A-02): django-allauth headless,
    # browser client only (/_allauth/browser/v1/…). OpenAPI: /_allauth/openapi.html in dev.
    path("_allauth/", include("numo9.accounts.urls")),
]
