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
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
# gettext catalogues: backend/locale/<en_CA|fr_CA>/LC_MESSAGES/django.po (S-01-T10).
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = env_str("DJANGO_TIME_ZONE", "America/Toronto")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
