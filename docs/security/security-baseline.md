# Security baseline (S-03)

Deliverable S-03 · Branch `feature/S-03-security-baseline` · PIPEDA; PCI out of scope (Stripe
Elements only).

## S-03-T01 — Django security settings per environment

`python manage.py check --deploy --fail-level WARNING` reports **0 warnings** for staging and
prod (CI `backend` job and `backend/tests/test_security_settings.py`).

| Setting | dev / test | staging / prod | Where |
|---|---|---|---|
| `X_FRAME_OPTIONS` | `DENY` | `DENY` | `settings/base.py` |
| `SECURE_CONTENT_TYPE_NOSNIFF` | on | on | base |
| `SECURE_REFERRER_POLICY` | `strict-origin-when-cross-origin` | same | base |
| `SECURE_CROSS_ORIGIN_OPENER_POLICY` | `same-origin` | same | base |
| Session cookie | HttpOnly, SameSite=Lax | + Secure | base / `settings/deployed.py` |
| CSRF cookie | HttpOnly, SameSite=Lax | + Secure; `CSRF_TRUSTED_ORIGINS` from env | base / deployed |
| `SECURE_SSL_REDIRECT` | off (HTTP) | on (`/healthz` exempt for health checks) | deployed |
| `SECURE_PROXY_SSL_HEADER` | — | `X-Forwarded-Proto: https` from Caddy / tunnel | deployed |
| HSTS | off | 1 year, includeSubDomains, preload | deployed |
| `DEBUG` | dev: on | off | per environment |

Environment variables (staging/prod): `DJANGO_SECURE_SSL_REDIRECT` (default `true`),
`DJANGO_SECURE_HSTS_SECONDS` (default `31536000`), `DJANGO_CSRF_TRUSTED_ORIGINS`
(comma-separated `https://…` origins of the web app and console).

### CSRF with an HttpOnly cookie

JavaScript cannot read the CSRF cookie. The web app calls `GET /api/v1/auth/csrf` once per
session (response `{"csrfToken": "…"}`, never cached), then sends the token in the
`X-CSRFToken` header on every POST/PUT/PATCH/DELETE. Requests without it are refused with 403.
