"""Security routes, mounted under /api/v1/ (S-03)."""

from django.urls import path

from . import api, reveal_api

urlpatterns = [
    path("auth/csrf", api.CsrfTokenView.as_view(), name="auth-csrf"),
    # Reveal a masked value (S-03-T05).
    path("o/<uuid:org>/reveal", reveal_api.RevealView.as_view(), name="security-reveal"),
]
