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
    path("api/v1/", include("numo9.rbac.urls")),  # roles, assignments, limits (A-03-T09)
    path("api/v1/", include("numo9.jobs.urls")),  # job tray: progress, events, retry (A-08-T06)
    path("api/v1/", include("numo9.audit.urls")),  # audit log and record history (A-04-T07)
    path("api/v1/", include("numo9.catalogue.urls")),  # products and feature keys (U-01-T09)
    path("api/v1/", include("numo9.packages.urls")),  # packages, prices, promo codes (U-02-T07)
    path("api/v1/", include("numo9.files.urls")),  # documents inbox and attachments (A-06)
    # Sign-up, email verification, login, logout, password reset (A-02): django-allauth headless,
    # browser client only (/_allauth/browser/v1/…). OpenAPI: /_allauth/openapi.html in dev.
    path("_allauth/", include("numo9.accounts.urls")),
]
