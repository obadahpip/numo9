"""Staging settings. Every secret and host must come from the environment."""

import dj_database_url

from .deployed import *  # noqa: F403
from .env import env_list, env_str

SECRET_KEY = env_str("DJANGO_SECRET_KEY", required=True)
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", required=True)

DATABASES = {
    "default": dj_database_url.parse(env_str("DATABASE_URL", required=True), conn_max_age=60)
}
