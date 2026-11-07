"""Automated test settings."""

import dj_database_url

from .base import *  # noqa: F403
from .env import env_list, env_str

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "test-insecure-secret-key")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["testserver", "localhost"])

DATABASES = {"default": dj_database_url.parse(env_str("DATABASE_URL", "sqlite://:memory:"))}

# Fast hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
