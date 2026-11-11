"""A plain Django view mounted under /api/ (rbac.E005, A-03-T06)."""

from django.urls import path

from . import rbac_api

urlpatterns = [
    path("api/v1/plain/", rbac_api.plain_django_view),
    path("not-api/plain/", rbac_api.plain_django_view),  # outside /api/: not reported
]
