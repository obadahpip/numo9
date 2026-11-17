"""Practice staff API routes (V-05), under /api/v1/."""

from django.urls import path

from . import api

urlpatterns = [
    path("practice/staff", api.StaffListView.as_view(), name="practice-staff"),
]
