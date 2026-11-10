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

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "test-insecure-secret-key")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["testserver", "localhost"])

DATABASES = {"default": dj_database_url.parse(env_str("DATABASE_URL", "sqlite://:memory:"))}

# Fast hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Field encryption (S-03-T04): a fixed key derived from a public label when none is configured —
# for local data only; never valid in staging/prod (they require NUMO9_FIELD_ENCRYPTION_KEYS).
if not FIELD_ENCRYPTION_KEYS:
    FIELD_ENCRYPTION_KEYS = json.dumps(
        {"test-local": base64.b64encode(hashlib.sha256(b"numo9-test-field-key").digest()).decode()}
    )
    FIELD_ENCRYPTION_ACTIVE_KEY = "test-local"
