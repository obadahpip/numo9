"""Settings shared by every environment. Environment modules import * from here."""

from pathlib import Path
from typing import Any

from django.utils.translation import gettext_lazy as _

from .env import env_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Overridden per environment.
SECRET_KEY = ""
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    # Project apps first so their templates/static override contrib defaults.
    "numo9.accounts",
    "numo9.tenancy",
    # Printed documents: WeasyPrint Letter template baseline (A-10-T16).
    "numo9.documents",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Request language: user's locale → numo9_locale cookie → Accept-Language (A-10-T14).
    "numo9.i18n.middleware.LocaleMiddleware",
    # Active organisation + acting practice into contextvars (A-01-T03); needs request.user.
    "numo9.tenancy.middleware.TenantContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "numo9.urls"
WSGI_APPLICATION = "numo9.wsgi.application"
ASGI_APPLICATION = "numo9.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Custom user model (A-02-T01); set before the first migration, never change afterwards.
AUTH_USER_MODEL = "accounts.User"

# Django REST framework (A-01-T06). Secure default: an endpoint must opt out of authentication
# explicitly. Organisation-scoped endpoints add IsOrgMemberOrAssigned (404 on foreign data).
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Error bodies carry a stable `code` next to the localised message (A-10-T14).
    "EXCEPTION_HANDLER": "numo9.i18n.exceptions.exception_handler",
}

# OpenAPI 3 schema (A-01-T13), served at /api/schema/ to signed-in users; the typed frontend
# client is generated from `manage.py spectacular`.
SPECTACULAR_SETTINGS = {
    "TITLE": "Numo9 API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "PracticeRoleEnum": "numo9.tenancy.models.PracticeRole",
        "OrganisationRoleEnum": "numo9.tenancy.models.OrganisationRole",
        "OrganisationStatusEnum": "numo9.tenancy.models.OrganisationStatus",
        "AssignmentRoleEnum": "numo9.tenancy.models.AssignmentRole",
    },
}

# Routes that are not organisation-scoped and are therefore skipped by `manage.py tenant_sweep`
# (A-01-T09). Every entry is reviewed: none of these may return one organisation's data.
TENANT_SWEEP_EXEMPT = [
    r"^api/schema/",  # OpenAPI schema (no tenant data)
    r"^api/v1/me/",  # the signed-in user's own memberships (A-01-T13)
    r"^api/v1/practices$",  # create a practice (A-01-T13)
    r"^api/v1/organisations$",  # create an organisation (A-01-T13)
]

# Overridden per environment.
DATABASES: dict[str, Any] = {}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-ca"
LANGUAGES = [("en-ca", _("English (Canada)")), ("fr-ca", _("French (Canada)"))]
# gettext catalogues: backend/locale/<en_CA|fr_CA>/LC_MESSAGES/django.po (S-01-T10); the .mo
# files are compiled at build time (tools/compile_messages.py, A-10-T14), never committed.
LOCALE_PATHS = [BASE_DIR / "locale"]
# Same cookie as the web app's language (A-10-T13); read by numo9.i18n.middleware.
LANGUAGE_COOKIE_NAME = "numo9_locale"
TIME_ZONE = env_str("DJANGO_TIME_ZONE", "America/Toronto")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
