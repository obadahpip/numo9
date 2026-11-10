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

## S-03-T02 — Content Security Policy with nonces

`frontend/src/middleware.ts` creates a 128-bit nonce per page request and sends the policy from
`frontend/src/security/csp.ts`; Next.js puts the nonce on its own scripts and stylesheets.

```text
default-src 'self';
script-src 'self' 'nonce-…' https://js.stripe.com https://*.js.stripe.com;
style-src 'self' 'nonce-…'; style-src-attr 'unsafe-inline';
img-src 'self' data: blob: https://*.stripe.com; font-src 'self' data:;
connect-src 'self' https://api.stripe.com [NUMO9_CSP_CONNECT_SRC];
frame-src https://js.stripe.com https://*.js.stripe.com https://hooks.stripe.com;
worker-src 'self' blob:; manifest-src 'self'; object-src 'none';
base-uri 'self'; form-action 'self'; frame-ancestors 'none';
report-uri /api/csp-report
```

- **Stripe is the only third party** (Elements/Checkout for U-04). No `'unsafe-inline'` or
  `'unsafe-eval'` for scripts (`'unsafe-eval'` is added only under `next dev`).
- `style-src-attr 'unsafe-inline'` allows React's `style` attributes (virtualised grids); inline
  `<style>` elements still need the nonce.
- **Reports**: `POST /api/csp-report` (Next.js route) accepts `application/csp-report` and
  `application/reports+json`, logs one JSON line `{"event": "csp.violation", …}` per report with
  query strings removed, refuses bodies over 16 KB (413) and logs at most 120 reports a minute.
- **Rollout**: `NUMO9_CSP_MODE=report-only` sends `Content-Security-Policy-Report-Only` — use it
  for the first week on a new environment, then remove it (default `enforce`).
- `NUMO9_CSP_CONNECT_SRC`: extra `https://` origins the browser calls (e.g. the API origin).

Tests: `frontend/src/security/csp.test.ts` (Vitest) and `frontend/e2e/csp.spec.ts`
(Playwright): every Phase 0 page has a nonce policy, all its scripts carry that nonce and the
console shows no CSP violation; a Stripe script and frame load; a script from another origin is
blocked and reported.

## S-03-T03 — Secrets management

SOPS + age encrypted environment files in the repository, decrypted only on the deploy host by
`infra/deploy/deploy.sh`; CI/CD credentials in GitHub Environments. Full procedure, inventory and
rotation steps: [Secrets and rotation runbook](secrets-runbook.md). Checks: gitleaks with
`.gitleaks.toml` (security workflow + pre-commit), `tools/ci/check_secrets.py`, and
`infra/secrets/tests/test_secrets.sh` (security workflow job `secrets`).
