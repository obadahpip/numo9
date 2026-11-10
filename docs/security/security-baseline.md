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

## S-03-T04 — `EncryptedField` and key rotation

`numo9.security.fields.EncryptedField` stores a value envelope-encrypted (`numo9/security/crypto.py`):

- a random 256-bit **data key** per value encrypts it with AES-256-GCM; the data key is wrapped
  (AES-256-GCM) by a **key-encryption key** from the key ring;
- stored text: `n9e1:<key id>:<wrapped data key>:<ciphertext>` — the key id travels with the value;
- both layers authenticate `app_label.Model.field`, so a value copied into another column or
  edited in the database fails to decrypt;
- only `isnull` lookups (no filtering/ordering on encrypted values); cannot be indexed or unique;
  `max_length` validates the plain value.

Key ring (from the SOPS-encrypted environment, S-03-T03):

```text
NUMO9_FIELD_ENCRYPTION_KEYS={"2026-11": "<base64 32 bytes>"}
NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY=2026-11
```

`manage.py generate_field_key 2026-11` prints a new entry. `check --deploy` fails with
`security.E100` when the ring is missing or invalid and `security.E102` if the development key
(`*-local`, dev/test settings) is in it.

Rotation (no downtime): add the new key and make it active → deploy →
`manage.py rotate_field_encryption` (re-wraps every data key, all organisations, in batches;
`--dry-run` counts, `--check` fails while any value is on an old key) → remove the old key.
Tests: `backend/tests/test_encrypted_field.py`.

## S-03-T06 — Log scrubbing

`numo9/security/scrubbing.py` removes personal and secret data from every log line and every
Sentry event; whatever it removes reads `[REDACTED]`.

| Layer | Rule |
|---|---|
| By name | Values whose key names a secret: `password`, `secret`, `token`, `api_key`, `authorization`, `cookie`, `session`, `sin` / `nas` / `ssn`, `card`, `cvv`, `iban`, `bank`, `transit`, `account_number`, `dsn`, `signature`… (whole words: `business`, `account_id`, `company` are kept) |
| By shape | SIN (`ddd-ddd-ddd`, `ddd ddd ddd`, or 9 digits passing Luhn), card numbers (13–19 digits passing Luhn), Canadian bank accounts (`ttttt-iii-aaaaaaa`), `Bearer`/`Token`/`Basic` credentials, JWTs, Stripe `sk_`/`rk_`/`whsec_` keys, age private keys, `password=…`-style pairs, passwords in URLs |

Where it runs (`numo9/security/logging.py`):

- **Logs** — Django `LOGGING` sends every standard-library record and every
  `structlog.get_logger()` event through one `ProcessorFormatter`; the scrubber runs after the
  traceback is rendered to text and again after `%s` arguments are merged. JSON lines in
  staging/prod (`NUMO9_LOG_JSON`, default on), plain text locally; `django.db.backends` is kept at
  WARNING (SQL parameters).
- **Sentry** — started only when `SENTRY_DSN` is set (staging/prod); no user identity, request
  bodies, frame variables or SQL parameters are collected, and `before_send`,
  `before_send_transaction` and `before_breadcrumb` scrub request URL, query string, headers,
  cookies (dropped whole), extra, contexts, breadcrumbs and exception messages; the user is
  reduced to its id.

Tests: `backend/tests/test_log_scrubbing.py` — a log line with a SIN shows `[REDACTED]`
(standard logging, structlog, tracebacks, and a fresh prod-settings process), rule tables for
what is and is not redacted, and a real Sentry client with a capturing transport.

## S-03-T09 — Dependency and image scans gate the build

The Security workflow (`.github/workflows/security.yml`, on every pull request, on `main` and
weekly) runs each scanner with JSON output and hands the report to `tools/ci/scan_gate.py`:

| Scanner | Report | Fails the build on |
|---|---|---|
| `pip-audit` (backend `requirements/dev.txt`, `docs/requirements.txt`) | `pip-audit -f json` | any known vulnerability (pip-audit has no severity) |
| `pnpm audit` (whole workspace lockfile) | `pnpm audit --json` | advisories rated **high** or **critical** |
| Trivy (backend and frontend runtime images) | `trivy image --format json --ignore-unfixed` | fixable **HIGH**/**CRITICAL** vulnerabilities and **any secret** in an image |

A missing or malformed report fails too, so a scanner that crashed or could not reach its
database never counts as a pass. Reports are uploaded as workflow artefacts.

### Allow-list: `.security-allowlist.toml`

A finding passes only when it has an entry in the allow-list at the repository root:

```toml
[[finding]]
scanner = "npm"                     # pip-audit | npm | trivy
package = "example-lib"
id = "GHSA-xxxx-xxxx-xxxx"          # or any alias: CVE-…, PYSEC-…, Trivy rule id
justification = "Build-time only (Storybook); never shipped in the runtime image. Upgrade blocked until example-lib 3 supports React 19."
owner = "obadahpip"
expires = 2027-01-31
ticket = "https://github.com/obadahpip/numo9/issues/123"   # optional
```

- **justification** is required: at least 40 characters, no placeholder (`TODO`, `TBD`, `n/a`);
  it says why the risk is accepted and how it is mitigated;
- **owner** re-reviews the entry; **expires** is at most **90 days** ahead — an expired entry fails
  every scan job (and the `scan allow-list` job) until it is renewed with a fresh review or
  removed;
- entries match on scanner + package (pip names normalised) + id or alias; an entry that no longer
  matches anything is reported as a warning so it can be removed;
- the file is owned by the project lead (`CODEOWNERS`): adding an entry is a reviewed change.
  Upgrading the package is always preferred.

Tests: `tools/tests/test_scan_gate.py` (CI `infra` job) — a high npm advisory, a high/critical
Trivy vulnerability, a Trivy secret and any pip-audit finding fail; moderate findings pass; a
justified entry allows the finding by id or alias; missing justification/owner, expired or
too-distant expiry, duplicates and unreadable reports fail.

## S-03-T10 — Security headers checked in CI

Every response — web pages, Next.js API routes, static assets, Django JSON, errors and the admin —
carries the securityheaders.com set:

| Header | Web app (`frontend/src/security/headers.ts`, `next.config.ts`) | Backend (`numo9/security/headers.py` + Django) |
|---|---|---|
| `Content-Security-Policy` | pages: nonce policy (S-03-T02); `/api/*`: `default-src 'none'; frame-ancestors 'none'` | JSON/other: `default-src 'none'; frame-ancestors 'none'`; HTML (admin): `frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` (production builds) | same, HTTPS requests in staging/prod (S-03-T01) |
| `X-Frame-Options` | `DENY` | `DENY` |
| `X-Content-Type-Options` | `nosniff` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | same |
| `Permissions-Policy` | accelerometer, camera, display-capture, geolocation, gyroscope, magnetometer, microphone, usb off; `payment` for self + Stripe | same |
| `Cross-Origin-Opener-Policy` | `same-origin` | `same-origin` |
| Banners | no `X-Powered-By` (`poweredByHeader: false`) | gunicorn `Server` without version |

A view or route that sets its own CSP or Permissions-Policy keeps it.

**CI check** — `tools/ci/check_security_headers.py` grades live responses like
securityheaders.com (missing header or weak value = fail: no `frame-ancestors`, `'unsafe-eval'`,
`'unsafe-inline'` scripts without a nonce, HSTS under one year or without subdomains,
`unsafe-url` referrer, camera/microphone/geolocation not disabled, version banners). The
Security workflow job `security headers` builds the web app, starts it with `next start` and the
backend with gunicorn and prod settings behind `X-Forwarded-Proto: https`, and grades a page, a
404, an API route, JSON, a 403, a 404 and the admin login. Run locally:

```bash
python tools/ci/check_security_headers.py --hsts http://127.0.0.1:3000/o/acme/home
python tools/ci/check_security_headers.py --hsts --header "X-Forwarded-Proto: https" http://127.0.0.1:8000/healthz
```

Tests: `backend/tests/test_security_headers.py` (every route over HTTPS graded by the same rules,
each missing/weak header fails the grader), `frontend/src/security/headers.test.ts` (Vitest) and
`frontend/e2e/security-headers.spec.ts` (Playwright on the production build: page, 404, API
route, static asset).

## S-03-T11 — Threat model

[Threat model (STRIDE)](threat-model.md) for tenancy, authentication, billing and files: data
flow and trust boundaries, assets, actors, one STRIDE table per area mapping every threat to its
mitigation, owning atomic task and status, and the accepted residual risks. Re-reviewed before
each phase exit and whenever a deliverable adds a trust boundary.

## S-03-T07 — Brute-force protection on login

`numo9/security/bruteforce.py`, wired into the allauth adapter (`numo9/accounts/adapter.py`):

| Control | Rule | Answer |
|---|---|---|
| Account lockout | 10 failed logins for one email address within 15 minutes lock it for **15 minutes** — every attempt is refused, even with the right password, from any IP | `429`, code `too_many_login_attempts`, `Retry-After: <seconds left>` |
| Per-IP limits (allauth) | 20 login attempts and 20 failed attempts a minute per IP | `429` |
| CAPTCHA hook | after 5 failures for an address, a `captcha` token is required in the login body when `NUMO9_CAPTCHA_VERIFIER` names a `verify(token, remote_ip) -> bool` callable (provider wired in Q-02-T03); off when unset; a verifier error counts as "not verified" | `400`, code `captcha_required` |

- The lock is per **address**, whether or not an account exists, so it reveals nothing.
- Success clears the failure count (not an active lock); a completed password reset clears both.
- State is in the shared cache (Redis in staging/prod); keys hold a SHA-256 of the address.
- Settings: `NUMO9_LOGIN_LOCKOUT_THRESHOLD` (10), `NUMO9_LOGIN_LOCKOUT_SECONDS` (900),
  `NUMO9_LOGIN_CAPTCHA_AFTER` (5), `NUMO9_CAPTCHA_VERIFIER` (env, empty).

Tests: `backend/tests/test_bruteforce.py` — the 11th attempt is locked, the lock lasts exactly
15 minutes, applies from every IP and only to that address, unknown addresses behave the same,
casing does not dodge it, success resets the count, CAPTCHA required after 5 failures.

!!! note "Key rotation and 2FA secrets"
    TOTP secrets (A-02-T05) are encrypted with the same key ring but live in allauth's
    `Authenticator.data` JSON, which `rotate_field_encryption` does not walk. Keep an old key in
    the ring until every user has re-enrolled or a rotation step for `allauth.mfa` is added.
