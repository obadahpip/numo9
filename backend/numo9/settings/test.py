"""Automated test settings."""

import base64
import hashlib
import json

import dj_database_url

from .base import *  # noqa: F403
from .base import FIELD_ENCRYPTION_KEYS, INSTALLED_APPS
from .env import env_list, env_str

# Test/CI-only: `manage.py lintmigrations` (S-01-T08) and the test-only app with concrete
# models for abstract bases such as OrgOwnedModel (A-01-T02).
INSTALLED_APPS = [*INSTALLED_APPS, "django_migration_linter", "tests.testapp"]
# The test-only app is held to the OrgOwnedModel rule too (A-01-T08).
TENANCY_BUSINESS_APP_PREFIXES = ("numo9.", "tests.")
# ...and the test-only API views to the permission-declaration check (A-03-T05).
RBAC_VIEW_MODULE_PREFIXES = ("numo9.", "tests.")
# Third-party migrations (django-allauth, A-02) are reviewed upstream, not by our linter.
MIGRATION_LINTER_OPTIONS = {
    "exclude_apps": ["account", "headless", "mfa", "usersessions", "django_celery_beat"],
    # Reviewed (A-03-T07): User.public_id is added nullable, filled row by row, then made
    # required + unique in one migration. The linter flags the NOT NULL / UNIQUE steps; they are
    # safe here — every existing row is filled first, and in Phase 0 there is no production
    # deployment whose old code could insert users while the migration runs.
    "ignore_name": ["0002_user_public_id"],
}

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "test-insecure-secret-key")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["testserver", "localhost"])

DATABASES = {"default": dj_database_url.parse(env_str("DATABASE_URL", "sqlite://:memory:"))}

# Fast hashing in tests only (tests/test_auth_signup.py checks the Argon2id configuration of base).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# No calls to the Pwned Passwords API from tests (the validator is tested with a stub).
BREACHED_PASSWORD_CHECK = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Celery (A-08-T01): in-process broker and results, so tests run a real worker thread without a
# Redis server (tests/test_celery.py). The Redis integration test runs when
# NUMO9_TEST_REDIS_URL is set.
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Field encryption (S-03-T04): a fixed key derived from a public label when none is configured —
# for local data only; never valid in staging/prod (they require NUMO9_FIELD_ENCRYPTION_KEYS).
if not FIELD_ENCRYPTION_KEYS:
    FIELD_ENCRYPTION_KEYS = json.dumps(
        {"test-local": base64.b64encode(hashlib.sha256(b"numo9-test-field-key").digest()).decode()}
    )
    FIELD_ENCRYPTION_ACTIVE_KEY = "test-local"

# Job tray event stream (A-08-T06): fast and short in tests.
JOBS_SSE_POLL_SECONDS = 0.02
JOBS_SSE_MAX_SECONDS = 1.0
