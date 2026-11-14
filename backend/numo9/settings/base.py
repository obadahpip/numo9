"""Settings shared by every environment. Environment modules import * from here."""

from datetime import timedelta
from pathlib import Path
from typing import Any

from celery.schedules import crontab
from django.utils.translation import gettext_lazy as _

from numo9.jobs.queues import QUEUES
from numo9.security.logging import configure_structlog, logging_config

from .env import env_bool, env_int, env_str, redis_database

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Overridden per environment.
SECRET_KEY = ""
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    # Project apps first so their templates/static override contrib defaults.
    "numo9.accounts",
    "numo9.tenancy",
    # Roles, permission catalogue, approval limits (A-03).
    "numo9.rbac",
    # Printed documents: WeasyPrint Letter template baseline (A-10-T16).
    "numo9.documents",
    # Security baseline: CSRF token endpoint, encrypted fields, log scrubbing (S-03).
    "numo9.security",
    # Background jobs: Celery queues and the worker check task (A-08).
    "numo9.jobs",
    "numo9.audit",
    # Products and feature keys sold in packages (U-01).
    "numo9.catalogue",
    # Packages of products, effective-dated prices and promo codes (U-02).
    "numo9.packages",
    # General ledger: chart of accounts, GIFI list (C-01); posting engine (C-02).
    "numo9.ledger",
    # Organisation settings, tax registrations, lock dates, numbering (A-05).
    "numo9.orgsettings",
    # Contacts: contact model, people, addresses, duplicate detection (B-01).
    "numo9.contacts",
    # File storage, documents inbox, attachments, inbound email (A-06).
    "numo9.files",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    # Schedules in the database, run by numo9.jobs.beat.LockedDatabaseScheduler (A-08-T05).
    "django_celery_beat",
    # Sign-up, email verification, login, password reset — JSON API only (A-02).
    "allauth",
    "allauth.account",
    "allauth.headless",
    # TOTP 2FA, recovery codes, trusted browsers (A-02-T05).
    "allauth.mfa",
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
    # Audit context (A-04-T04): request id, client IP, device and the request's user for every
    # audit event; X-Request-ID on every response.
    "numo9.audit.context.AuditContextMiddleware",
    # Active organisation + acting practice into contextvars (A-01-T03); needs request.user.
    "numo9.tenancy.middleware.TenantContextMiddleware",
    # Permission sets cached for one request only — never across requests (A-03-T04).
    "numo9.rbac.resolver.PermissionCacheMiddleware",
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

# Django REST framework (A-01-T06). Secure default: every API method declares the permission
# it needs — a catalogue key, or PUBLIC / AUTHENTICATED — and RequiresPermission enforces it
# (A-03-T05; system check rbac.E001-E004). Organisation-scoped endpoints add
# IsOrgMemberOrAssigned first (404 on foreign data).
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "numo9.rbac.drf.RequiresPermission",
        # Feature key of the organisation's package: 402 naming the product (U-01-T05, U-03).
        "numo9.catalogue.drf.RequiresFeature",
    ],
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
        "RoleScopeEnum": "numo9.rbac.models.RoleScope",
        "MemberKindEnum": "numo9.rbac.serializers.MEMBER_KINDS",
        "InvitationKindEnum": "numo9.tenancy.models.InvitationKind",
        "JobStatusEnum": "numo9.jobs.models.JobStatus",  # A-08-T06
        "JobPurgeStatusEnum": [("dead", "dead"), ("failed", "failed")],  # A-08-T08
        "ProductKindEnum": "numo9.catalogue.models.ProductKind",  # U-01-T09
        "ProductStatusEnum": "numo9.catalogue.models.ProductStatus",  # U-01-T09
        "PackageStatusEnum": "numo9.packages.models.PackageStatus",  # U-02-T07
        "BillingIntervalEnum": "numo9.packages.models.BillingInterval",  # U-02-T07
        "PromoKindEnum": "numo9.packages.models.PromoKind",  # U-02-T07
        "PromoDurationEnum": "numo9.packages.models.PromoDuration",  # U-02-T07
        "PromoStatusEnum": "numo9.packages.models.PromoStatus",  # U-02-T07
        "PriceStateEnum": "numo9.packages.serializers.PRICE_STATES",  # U-02-T07
        "BulkActionEnum": "numo9.files.listing.BULK_ACTION_CHOICES",  # A-06-T10
        # Feature keys' action (U-01): named once a second "action" choice set exists (A-06-T10).
        "FeatureActionEnum": [("read", "read"), ("write", "write"), ("approve", "approve")],
    },
}

# Entitlement resolver behind RequiresFeature (U-01-T05): a stub allowing every feature key
# until the U-03 engine replaces it.
NUMO9_ENTITLEMENT_RESOLVER = "numo9.catalogue.entitlements.AllowAllResolver"
# Packages in the feature matrix (U-01-T09): the packages offered (U-02-T05).
NUMO9_PACKAGE_SOURCE = "numo9.packages.source.OfferedPackages"
# Stripe (U-02-T12 price sync; U-04 billing): the platform account's secret key from the
# secrets file (never in the repo); empty = Stripe sync off (the stub until U-04). STRIPE_API_BASE
# points the client elsewhere (stripe-mock in tests); empty = Stripe's own API.
STRIPE_SECRET_KEY = env_str("STRIPE_SECRET_KEY", "")
STRIPE_API_BASE = env_str("STRIPE_API_BASE", "")
# Gateway used by the sync job: a dotted path to a class (tests), or empty = the Stripe API when a
# key is set, otherwise off.
NUMO9_STRIPE_GATEWAY = ""
# Subscriptions as packages see them (U-02-T05, T10): nobody subscribes until U-03/U-04.
NUMO9_SUBSCRIPTION_SOURCE = "numo9.packages.subscriptions.NoSubscriptions"

# Third-party DRF views without a permission declaration (rbac.E004): dotted path -> why safe.
RBAC_EXEMPT_VIEWS = {
    "drf_spectacular.views.SpectacularAPIView": (
        "OpenAPI schema: no tenant data; SPECTACULAR_SETTINGS limits it to signed-in users"
    ),
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
    # Invitations to a practice or an organisation (A-02-T09): not organisation-scoped (practice
    # invitations have none); every object is checked by numo9.tenancy.invitations (404/403).
    r"^api/v1/invitations",
    r"^api/v1/permissions/catalogue$",  # the permission catalogue: same for everyone (A-03-T09)
    r"^api/v1/catalogue/",  # products and feature keys: same for everyone (U-01-T09)
    r"^api/v1/public/",  # public pricing: same for everyone, no sign-in (U-02-T08)
    # Inbound email webhook (A-06-T07): HMAC-signed by the provider; routed by the docs+<token>@
    # address to one organisation, whose context the processing then runs in.
    r"^api/v1/inbound/email$",
    # Platform console (A-08-T08 job dashboard): no organisation; platform.* permissions only.
    r"^api/v1/platform/",
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
# Password reset (A-02-T04): the emailed link is valid for one hour and works once (the token is
# bound to the password hash); setting a new password ends every session of the user (Django's
# session auth hash) and the user signs in again with the new password.
PASSWORD_RESET_TIMEOUT = 60 * 60
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
# Login rate limits (A-02-T03): every login attempt and every failed attempt per IP. A limited
# request gets 429. Counters live in the cache (Redis in staging/prod, settings/deployed.py).
ACCOUNT_RATE_LIMITS = {
    "login": "20/m/ip",
    "login_failed": "20/m/ip",  # per account: the lockout below
}
# Brute-force protection (S-03-T07, numo9/security/bruteforce.py): 10 failed logins for one
# address lock it for 15 minutes; after 5 failures a CAPTCHA token is required when a verifier
# is configured (dotted path to verify(token, remote_ip) -> bool; the provider arrives in Q-02).
NUMO9_LOGIN_LOCKOUT_THRESHOLD = 10
NUMO9_LOGIN_LOCKOUT_SECONDS = 15 * 60
NUMO9_LOGIN_CAPTCHA_AFTER = 5
NUMO9_CAPTCHA_VERIFIER = env_str("NUMO9_CAPTCHA_VERIFIER", "")
ACCOUNT_EMAIL_NOTIFICATIONS = True

# ---- Two-factor authentication: allauth.mfa (A-02-T05, numo9/accounts/mfa.py) -----------------
MFA_ADAPTER = "numo9.accounts.mfa.MFAAdapter"  # TOTP secrets encrypted with the key ring
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Numo9"
MFA_TOTP_PERIOD = 30
MFA_TOTP_DIGITS = 6
MFA_TOTP_TOLERANCE = 1  # accept the previous and next 30-second step (clock skew)
MFA_RECOVERY_CODE_COUNT = 10  # hashed, shown once, each single-use
MFA_RECOVERY_CODES_SHOW_ONCE = True
# "Remember this device for 30 days": a signed cookie bound to the user's password and
# authenticators — changing either invalidates it.
MFA_TRUST_ENABLED = True
MFA_TRUST_COOKIE_AGE = timedelta(days=30)
MFA_TRUST_COOKIE_NAME = "numo9_trusted_device"

# ---- Email (A-07 adds the provider and custom sending domains) ---------------------------------
EMAIL_BACKEND = env_str("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env_str("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", 1025)  # Mailpit in the dev stack
EMAIL_HOST_USER = env_str("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env_str("DJANGO_DEFAULT_FROM_EMAIL", "Numo9 <no-reply@numo9.ca>")

# ---- Background jobs: Celery (A-08-T01, numo9/celery.py, docs/architecture/jobs.md) -----------
# Redis is the broker and the result backend: by default the server of REDIS_URL (the shared
# cache uses database 0), broker in database 2 and results in database 3.
CELERY_BROKER_URL = env_str(
    "CELERY_BROKER_URL", redis_database(env_str("REDIS_URL", "redis://localhost:6379/0"), 2)
)
CELERY_RESULT_BACKEND = env_str(
    "CELERY_RESULT_BACKEND", redis_database(env_str("REDIS_URL", "redis://localhost:6379/0"), 3)
)
CELERY_RESULT_EXPIRES = timedelta(days=1)  # job outcomes users see are kept in JobRun (A-08-T02)
CELERY_RESULT_EXTENDED = True  # task name, args and queue stored with the result (job dashboard)
# Only JSON crosses the broker: no pickle, so a message can never run code in a worker.
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True
# At-least-once delivery: a task is acknowledged after it finishes, so a worker that dies
# mid-task leaves the message to be delivered again (idempotency keys, A-08-T03, make the second
# run harmless). One message reserved per worker process: no long job sits behind another.
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TRACK_STARTED = True
# Time limits: the soft limit raises SoftTimeLimitExceeded inside the task (clean up, record
# the failure); the hard limit kills the process. Override per task for long reports.
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", 25 * 60)
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", 30 * 60)
# Redis redelivers an unacknowledged message after the visibility timeout: it must be longer
# than the hard time limit, or a long task would run twice while still running.
CELERY_VISIBILITY_TIMEOUT = env_int("CELERY_VISIBILITY_TIMEOUT", 2 * 60 * 60)
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": CELERY_VISIBILITY_TIMEOUT}
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {"visibility_timeout": CELERY_VISIBILITY_TIMEOUT}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Queues: high / default / io / reports (numo9/jobs/queues.py); unnamed tasks go to default.
CELERY_TASK_QUEUES = QUEUES
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_DEFAULT_EXCHANGE = "numo9"
CELERY_TASK_DEFAULT_ROUTING_KEY = "default"
CELERY_TASK_CREATE_MISSING_QUEUES = False  # a typo in a queue name fails instead of piling up
CELERY_WORKER_SEND_TASK_EVENTS = True  # job dashboard (A-08-T08)
CELERY_TASK_SEND_SENT_EVENT = True
# Beat (A-08-T05, numo9/jobs/beat.py): schedules in the database (django-celery-beat), one
# execution per schedule tick across every running beat (Redis lock numo9:beat:<name>:<tick>).
CELERY_BEAT_SCHEDULER = "numo9.jobs.beat:LockedDatabaseScheduler"
JOBS_BEAT_LOCK_URL = env_str("JOBS_BEAT_LOCK_URL", "")  # empty: the broker's Redis
DJANGO_CELERY_BEAT_TZ_AWARE = True
# Job tray event stream (A-08-T06, numo9/jobs/api.py): checks every second, ends after 25 s
# (EventSource reconnects after JOBS_SSE_RETRY_MS) so a stream never holds a server worker long.
JOBS_SSE_POLL_SECONDS = 1.0
JOBS_SSE_MAX_SECONDS = 25.0
JOBS_SSE_RETRY_MS = 2000
# Code-defined schedules, written to the database when beat starts.
CELERY_BEAT_SCHEDULE = {
    # Job runs are kept 30 days after they finish (A-08 business rule).
    "numo9.jobs.purge_job_runs": {
        "task": "numo9.jobs.purge_job_runs",
        "schedule": crontab(minute=17, hour=7),  # 07:17 UTC = 02:17 / 03:17 Toronto
    },
}

# ---- File storage and documents inbox (A-06, docs/architecture/files.md) ------------------------
# S3-compatible object storage: Hetzner Object Storage in staging/prod (ADR-0002, buckets from
# S-02-T03), MinIO in the dev stack. Empty endpoint = AWS's default endpoint for the region.
NUMO9_FILES_S3_ENDPOINT_URL = env_str("NUMO9_FILES_S3_ENDPOINT_URL", "")
NUMO9_FILES_S3_REGION = env_str("NUMO9_FILES_S3_REGION", "hel1")
NUMO9_FILES_S3_ACCESS_KEY = env_str("NUMO9_FILES_S3_ACCESS_KEY", "")
NUMO9_FILES_S3_SECRET_KEY = env_str("NUMO9_FILES_S3_SECRET_KEY", "")
NUMO9_FILES_BUCKET = env_str("NUMO9_FILES_BUCKET", "numo9-files")
NUMO9_FILES_QUARANTINE_BUCKET = env_str("NUMO9_FILES_QUARANTINE_BUCKET", "numo9-quarantine")
# Signed download URLs and presigned upload forms live 5 minutes (A-06 business rule).
NUMO9_FILES_SIGNED_URL_SECONDS = env_int("NUMO9_FILES_SIGNED_URL_SECONDS", 300)
# ClamAV daemon (A-06-T04): the clamav service of the stack, INSTREAM over TCP.
NUMO9_CLAMD_HOST = env_str("NUMO9_CLAMD_HOST", "clamav")
NUMO9_CLAMD_PORT = env_int("NUMO9_CLAMD_PORT", 3310)
NUMO9_CLAMD_TIMEOUT = env_int("NUMO9_CLAMD_TIMEOUT", 60)
# Inbound email (A-06-T06/T07): docs+<token>@<NUMO9_INBOUND_DOMAIN>; the provider signs each
# webhook with NUMO9_INBOUND_WEBHOOK_SECRET (HMAC-SHA256). Empty secret = inbound refused.
NUMO9_INBOUND_DOMAIN = env_str("NUMO9_INBOUND_DOMAIN", "in.numo9.ca")
NUMO9_INBOUND_WEBHOOK_SECRET = env_str("NUMO9_INBOUND_WEBHOOK_SECRET", "")

# Audit log (A-04-T04): proxies in front of the app whose X-Forwarded-For is trusted for the
# client IP (Caddy in staging/prod: 1). 0 = use REMOTE_ADDR.
NUMO9_TRUSTED_PROXY_COUNT = env_int("NUMO9_TRUSTED_PROXY_COUNT", 0)

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
