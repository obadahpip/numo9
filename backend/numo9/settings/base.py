"""Settings shared by every environment. Environment modules import * from here."""

from pathlib import Path
from typing import Any

from django.utils.translation import gettext_lazy as _

from numo9.security.logging import configure_structlog, logging_config

from .env import env_bool, env_int, env_str

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
    # Security baseline: CSRF token endpoint, encrypted fields, log scrubbing (S-03).
    "numo9.security",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    # Sign-up, email verification, login, password reset — JSON API only (A-02).
    "allauth",
    "allauth.account",
    "allauth.headless",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Permissions-Policy and a Content-Security-Policy on every response (S-03-T10).
    "numo9.security.headers.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # django-allauth login flow state (A-02-T02).
    "allauth.account.middleware.AccountMiddleware",
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
    r"^api/v1/auth/csrf$",  # CSRF token for the web app (S-03-T01)
    r"^_allauth/",  # sign-up, login, reset, 2FA for the signed-in user only (A-02)
]

# Overridden per environment.
DATABASES: dict[str, Any] = {}

# ---- Security headers and cookies (S-03-T01) -------------------------------------------------
# Same in every environment; the HTTPS-only flags (Secure cookies, HSTS, SSL redirect) are in
# settings/deployed.py for staging and prod.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# The web app reads the token from GET /api/v1/auth/csrf, not from the cookie.
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
LANGUAGE_COOKIE_HTTPONLY = False  # the web app reads the locale cookie (A-10-T13)
LANGUAGE_COOKIE_SAMESITE = "Lax"
# Session lifetime: two weeks of inactivity at most; A-02 adds the per-practice idle timeout.
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60

# ---- Logging (S-03-T06) ------------------------------------------------------------------------
# Every log line — Django, libraries, structlog — is scrubbed of SIN, bank and card numbers,
# tokens and passwords (numo9.security.scrubbing). JSON lines in staging/prod, plain text locally.
LOGGING = logging_config(
    json=env_bool("NUMO9_LOG_JSON", False), level=env_str("NUMO9_LOG_LEVEL", "INFO")
)
configure_structlog()

# ---- Field encryption (S-03-T04) ---------------------------------------------------------------
# Key-encryption keys for EncryptedField: JSON {"<key id>": "<base64 32 bytes>"} and the id that
# encrypts new values. Staging/prod read them from the SOPS-encrypted environment (S-03-T03);
# dev/test fall back to a fixed development key (settings/dev.py, settings/test.py).
FIELD_ENCRYPTION_KEYS = env_str("NUMO9_FIELD_ENCRYPTION_KEYS", "")
FIELD_ENCRYPTION_ACTIVE_KEY = env_str("NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY", "")

# ---- Passwords (A-02-T02) ---------------------------------------------------------------------
# Argon2id for every new or changed password; older hashes are upgraded at the next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    # Pwned Passwords range API (k-anonymity: only 5 hex characters of the SHA-1 leave the server).
    {"NAME": "numo9.accounts.validators.BreachedPasswordValidator"},
]
BREACHED_PASSWORD_CHECK = env_bool("NUMO9_BREACHED_PASSWORD_CHECK", True)
BREACHED_PASSWORD_API = "https://api.pwnedpasswords.com/range/"  # noqa: S105 — a URL
BREACHED_PASSWORD_TIMEOUT = 3.0  # seconds; the check fails open (logged) when the API is down

# ---- Authentication: django-allauth headless (A-02) ---------------------------------------------
# allauth for the web app's JSON API (/_allauth/browser/v1/…); Django's ModelBackend still serves
# the admin login.
AUTHENTICATION_BACKENDS = [
    "allauth.account.auth_backends.AuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
]
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)  # "app" (token) clients arrive with the mobile apps (Phase 7)
# Links in emails open the web app, which calls the API with the key.
FRONTEND_URL = env_str("NUMO9_FRONTEND_URL", "http://localhost:3000").rstrip("/")
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{FRONTEND_URL}/verify/{{key}}",
    "account_reset_password": f"{FRONTEND_URL}/reset",
    "account_reset_password_from_key": f"{FRONTEND_URL}/reset/{{key}}",
    "account_signup": f"{FRONTEND_URL}/signup",
}
ACCOUNT_ADAPTER = "numo9.accounts.adapter.AccountAdapter"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
# 4-field sign-up: path, name, email, password (+ practice or organisation name for the path).
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_SIGNUP_FORM_CLASS = "numo9.accounts.forms.SignupForm"
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # unverified users cannot log in
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_UNIQUE_EMAIL = True
# Same answer whether or not an email is registered (sign-up sends the owner a notice instead).
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = "Numo9 · "
ACCOUNT_EMAIL_NOTIFICATIONS = True

# ---- Email (A-07 adds the provider and custom sending domains) ---------------------------------
EMAIL_BACKEND = env_str("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", 1025)  # Mailpit in the dev stack
EMAIL_HOST_USER = env_str("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env_str("DJANGO_DEFAULT_FROM_EMAIL", "Numo9 <no-reply@numo9.ca>")

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
