"""Security routes, mounted under /api/v1/ (S-03)."""

from django.urls import path

from . import api

urlpatterns = [
    path("auth/csrf", api.CsrfTokenView.as_view(), name="auth-csrf"),
]
