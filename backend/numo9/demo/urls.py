"""Demo routes, under /api/v1/ (U-07)."""

from django.urls import path

from . import api

ORG = "o/<uuid:org>/"

urlpatterns = [
    path(f"{ORG}demo/convert", api.DemoConvertView.as_view(), name="demo-convert"),
]
