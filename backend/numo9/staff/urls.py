"""Practice staff API routes (V-05), under /api/v1/."""

from django.urls import path

from . import api

urlpatterns = [
    path("practice/staff", api.StaffListView.as_view(), name="practice-staff"),
    path(
        "practice/staff/<uuid:user_id>", api.StaffMemberView.as_view(), name="practice-staff-member"
    ),
    path(
        "practice/staff/<uuid:user_id>/suspend",
        api.StaffSuspendView.as_view(),
        name="practice-staff-suspend",
    ),
    path(
        "practice/staff/<uuid:user_id>/reinstate",
        api.StaffReinstateView.as_view(),
        name="practice-staff-reinstate",
    ),
    path(
        "practice/staff/<uuid:user_id>/assignments",
        api.StaffAssignmentsView.as_view(),
        name="practice-staff-assignments",
    ),
    path(
        "practice/staff/<uuid:user_id>/organisations/<uuid:org_id>",
        api.StaffOrganisationView.as_view(),
        name="practice-staff-organisation",
    ),
    path(
        "practice/staff/<uuid:user_id>/groups/<uuid:group_id>",
        api.StaffGroupView.as_view(),
        name="practice-staff-group",
    ),
]
