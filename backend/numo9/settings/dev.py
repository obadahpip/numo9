"""Local development settings."""

import dj_database_url

from .base import *  # noqa: F403
from .base import BASE_DIR, INSTALLED_APPS
from .env import env_bool, env_list, env_str

# Dev-only tooling (not installed in runtime images).
INSTALLED_APPS = [*INSTALLED_APPS, "django_migration_linter"]

SECRET_KEY = env_str("DJANGO_SECRET_KEY", "dev-insecure-secret-key-do-not-use-in-production")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]"])

_DEFAULT_DB_URL = "sqlite:///" + (BASE_DIR / "db.sqlite3").as_posix()

DATABASES = {
    "default": dj_database_url.parse(env_str("DATABASE_URL", _DEFAULT_DB_URL), conn_max_age=60)
}
