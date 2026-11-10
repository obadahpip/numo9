"""HTTPS-only security settings shared by staging and prod (S-03-T01).

`python manage.py check --deploy` reports 0 warnings for both environments (CI). TLS ends at the
reverse proxy (Caddy / Cloudflare tunnel), which sets ``X-Forwarded-Proto: https``.
"""

import os

from numo9.security.logging import init_sentry, logging_config

from .base import *  # noqa: F403
from .env import env_bool, env_int, env_list, env_str

# ---- Transport -------------------------------------------------------------------------------
# Trust the proxy's scheme header (the app is only reachable through the proxy; port 8000 is
# bound to 127.0.0.1 on the host).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
# Health checks from Compose/deploy.sh call http://127.0.0.1:8000/healthz directly.
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
# HSTS: one year, subdomains, preload-ready (S-02-T08 Caddy sends the same policy).
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ---- Cookies: HTTPS only ------------------------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
LANGUAGE_COOKIE_SECURE = True
# __Host- prefix (A-02-T03): the browser only accepts these cookies over HTTPS, for the exact host
# (no Domain attribute, so no sibling subdomain can set or read them) and for path "/".
SESSION_COOKIE_NAME = "__Host-numo9_session"
CSRF_COOKIE_NAME = "__Host-numo9_csrf"

# ---- Shared cache (A-02-T03) ---------------------------------------------------------------------
# Login rate limits and account lockouts must be shared by every worker: Redis (Compose service
# `redis`, infra/staging/docker-compose.staging.yml).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env_str("REDIS_URL", "redis://redis:6379/0"),
        "KEY_PREFIX": "numo9",
    }
}

# ---- Secrets (S-03-T03) -----------------------------------------------------------------------
# Rotating DJANGO_SECRET_KEY without signing everyone out: the new key signs, the previous key(s)
# listed here still verify sessions, password-reset links and signed values until they expire
# (docs/security/secrets-runbook.md). Values come from the SOPS-encrypted environment file.
SECRET_KEY_FALLBACKS = env_list("DJANGO_SECRET_KEY_FALLBACKS", [])

# Origins allowed to send unsafe requests, e.g. "https://app.numo9.ca,https://console.numo9.ca".
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

# ---- Logs and error reports (S-03-T06) ------------------------------------------------------
LOGGING = logging_config(
    json=env_bool("NUMO9_LOG_JSON", True), level=env_str("NUMO9_LOG_LEVEL", "INFO")
)
# Sentry (EU region, data-residency register) only when a DSN is configured; every event scrubbed.
SENTRY_DSN = env_str("SENTRY_DSN", "")
init_sentry(
    SENTRY_DSN,
    # "staging" / "prod" from the settings module unless SENTRY_ENVIRONMENT says otherwise.
    environment=env_str(
        "SENTRY_ENVIRONMENT", os.environ.get("DJANGO_SETTINGS_MODULE", "").rpartition(".")[2]
    ),
    release=env_str("NUMO9_RELEASE", "") or None,
)
