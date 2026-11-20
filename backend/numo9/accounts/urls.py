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
    path(
        f"{BROWSER}auth/login",
        views.LoginView.as_api_view(client=Client.BROWSER),
        name="numo9-auth-login",
    ),
    path(
        f"{BROWSER}account/authenticators/totp",
        views.ManageTOTPView.as_api_view(client=Client.BROWSER),
        name="numo9-mfa-totp",
    ),
    path(
        f"{BROWSER}auth/sessions",
        views.SessionsView.as_api_view(client=Client.BROWSER),
        name="numo9-auth-sessions",
    ),
    # Social sign-in provider callbacks (A-02-T16): with HEADLESS_ONLY, allauth.urls serves only
    # /_allauth/providers/<provider>/login/callback/ (registered with Google and Microsoft).
    path("providers/", include("allauth.urls")),
    path("", include("allauth.headless.urls")),
]
