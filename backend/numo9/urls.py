"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from numo9.billing.webhooks import stripe_webhook

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
    path("api/v1/", include("numo9.entitlements.urls")),  # entitlements bootstrap (U-03-T09)
    path("api/v1/", include("numo9.files.urls")),  # documents inbox and attachments (A-06)
    path("api/v1/", include("numo9.workspace.urls")),  # organisation directory (V-01)
    path("api/v1/", include("numo9.notifications.urls")),  # notification centre (A-07)
    path("api/v1/", include("numo9.orgsettings.urls")),  # organisation settings, locks (A-05)
    path("api/v1/", include("numo9.imports.urls")),  # imports and exports (B-03-T11)
    path("api/v1/", include("numo9.contacts.urls")),  # contacts (B-01-T11)
    path("api/v1/", include("numo9.ledger.urls")),  # journals read API (C-02-T15)
    path("api/v1/", include("numo9.billing.urls")),  # subscription billing (U-04)
    path("api/v1/", include("numo9.platform.urls")),  # platform console (U-06)
    path("api/v1/", include("numo9.bulk.urls")),  # bulk actions over organisations (V-03)
    path("api/v1/", include("numo9.staff.urls")),  # practice staff management (V-05)
    path("api/v1/", include("numo9.demo.urls")),  # demo organisations (U-07)
    path("api/v1/", include("numo9.founding.urls")),  # founding offer (U-08)
    path("api/v1/", include("numo9.scale.urls")),  # perf-only endpoints, off by default (S-06)
    # Sign-up, email verification, login, logout, password reset (A-02): django-allauth headless,
    # browser client only (/_allauth/browser/v1/…). OpenAPI: /_allauth/openapi.html in dev.
    path("_allauth/", include("numo9.accounts.urls")),
    # Email provider delivery webhooks (A-07-T08): django-anymail's tracking views,
    # /webhooks/email/<provider>/tracking/, HTTP basic auth with ANYMAIL_WEBHOOK_SECRET.
    path("webhooks/email/", include("anymail.urls")),
    # Stripe billing webhooks (U-04-T06): signed by Stripe, stored once, processed by Celery.
    path("webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
]
