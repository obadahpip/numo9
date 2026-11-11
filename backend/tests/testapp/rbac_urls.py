from django.urls import path, re_path

from . import rbac_api

urlpatterns = [
    re_path(r"^api/v1/o/[^/]+/settings/$", rbac_api.OrgSettings.as_view()),
    path("api/v1/by-class/", rbac_api.ByClass.as_view()),
    path("api/v1/console/", rbac_api.Console.as_view()),
    path("api/v1/practice-staff/", rbac_api.PracticeStaff.as_view()),
    path("api/v1/undeclared/", rbac_api.Undeclared.as_view()),
]
