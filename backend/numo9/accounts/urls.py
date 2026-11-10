"""Authentication routes (A-02): Numo9's overrides first, then django-allauth headless."""

from allauth.headless.constants import Client
from django.urls import include, path

from . import views

BROWSER = "browser/v1/"

urlpatterns = [
    path(
        f"{BROWSER}auth/signup",
        views.SignupView.as_api_view(client=Client.BROWSER),
        name="numo9-auth-signup",
    ),
    path("", include("allauth.headless.urls")),
]
