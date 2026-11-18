"""Staging settings. Every secret and host must come from the environment."""

from .database import database
from .deployed import *  # noqa: F403
from .env import env_list, env_str

SECRET_KEY = env_str("DJANGO_SECRET_KEY", required=True)
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", required=True)

# PgBouncer transaction pooling when NUMO9_DB_POOL=pgbouncer (S-06-T01, settings/database.py).
DATABASES = {"default": database(env_str("DATABASE_URL", required=True))}
