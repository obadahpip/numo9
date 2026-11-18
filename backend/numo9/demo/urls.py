"""Demo routes, under /api/v1/ (U-07)."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path("demo", api.DemoOpenView.as_view(), name="demo-open"),
    path(f"{ORG}demo/convert", api.DemoConvertView.as_view(), name="demo-convert"),
    path(f"{ORG}demo/reset", api.DemoResetView.as_view(), name="demo-reset"),
    path(f"{ORG}demo/outbox", api.DemoOutboxView.as_view(), name="demo-outbox"),
]
