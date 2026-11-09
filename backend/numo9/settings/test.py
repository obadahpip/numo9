"""Automated test settings."""

import dj_database_url

from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .env import env_list, env_str

# Test/CI-only: `manage.py lintmigrations` (S-01-T08) and the test-only app with concrete
# models for abstract bases such as OrgOwnedModel (A-01-T02).
INSTALLED_APPS = [*INSTALLED_APPS, "django_migration_linter", "tests.testapp"]

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "test-insecure-secret-key")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["testserver", "localhost"])

DATABASES = {"default": dj_database_url.parse(env_str("DATABASE_URL", "sqlite://:memory:"))}

# Fast hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
