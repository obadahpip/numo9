"""Every feature-key problem at once (U-01-T07 tests)."""

from django.urls import path

from . import feature_api

urlpatterns = [
    path("api/v1/o/<uuid:org>/undeclared/", feature_api.CanaryUndeclared.as_view()),
    path("api/v1/o/<uuid:org>/unknown/", feature_api.CanaryUnknownKey.as_view()),
    path("api/v1/o/<uuid:org>/not-enforced/", feature_api.CanaryNotEnforced.as_view()),
    path("api/v1/elsewhere/", feature_api.DeclaredOutsideBusiness.as_view()),
]
