"""Founding offer routes (U-08), under /api/v1/."""

from django.urls import path

from . import public

urlpatterns = [
    # Public counter (U-08-T08): anyone, cached 30 s.
    path("public/founding", public.PublicFoundingCounterView.as_view(), name="public-founding"),
]
