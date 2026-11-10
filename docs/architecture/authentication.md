# Authentication and sign-up

| | |
|---|---|
| **Deliverable** | A-02 · Authentication, sessions & sign-up (Phase 0) |
| **Code** | `backend/numo9/accounts/`, settings in `backend/numo9/settings/base.py` |
| **Library** | django-allauth 65 — headless (JSON API), browser client |

The web app talks to the authentication API under **`/_allauth/browser/v1/`** (allauth's
headless contract; the OpenAPI description is served at `/_allauth/openapi.html` in dev). Every
unsafe request carries the CSRF token from `GET /api/v1/auth/csrf` (S-03-T01). Responses always
say where the user stands: `meta.is_authenticated`, and `data.flows` with the pending step
(`verify_email`, `mfa_authenticate`, …) when a step is missing.

## Sign-up (A-02-T02)

`POST /_allauth/browser/v1/auth/signup`

| Field | Rule |
|---|---|
| `path` | `accountant` (free practice) or `organisation` (business on a trial) |
| `name` | the person's full name |
| `email` | login identifier, stored lower-cased; unique |
| `password` | ≥ 12 characters, not common, not similar to the email/name, not in a known breach |
| `practice_name` | required for `accountant` — creates the **practice**; the user is its practice admin |
| `organisation_name` | required for `organisation` — creates a **trial organisation**; the user is its owner |
| `locale` | optional, `en-ca` (default) or `fr-ca` |

- Everything is created in **one transaction** (user, email address, practice or organisation,
  membership).
- **Email verification is mandatory**: the answer is `401` with the pending flow `verify_email`
  and a link to `<NUMO9_FRONTEND_URL>/verify/<key>` is emailed (valid 3 days). The web app posts
  the key to `POST /auth/email/verify`, which verifies the address and signs the user in. An
  unverified user who logs in gets `401` with `verify_email` pending — never a session.
- **No account enumeration**: signing up with a registered email gives the same answer as a new
  sign-up, creates nothing, and emails the mailbox owner that an account already exists.
- **Passwords** are hashed with **Argon2id** (`PASSWORD_HASHERS`); older hashes are upgraded at
  the next login. The breached-password validator sends only the first five hex characters of
  the SHA-1 to the Pwned Passwords range API (k-anonymity, `Add-Padding`) and fails open, with a
  warning in the log, if the API is unreachable (`NUMO9_BREACHED_PASSWORD_CHECK`).

Tests: `backend/tests/test_auth_signup.py`.

## Login, logout and sessions (A-02-T03)

| Call | Answer |
|---|---|
| `POST /_allauth/browser/v1/auth/login` `{email, password}` | **200** signed in (`meta.is_authenticated: true`, `data.user`) · **401** pending step (e.g. `verify_email`, `mfa_authenticate`) or wrong email/password (`email_password_mismatch` — the same for an unknown email) · **400** malformed input · **429** rate limited or account locked, with `Retry-After` |
| `GET /_allauth/browser/v1/auth/session` | 200 signed in · 401 not signed in |
| `DELETE /_allauth/browser/v1/auth/session` | logs out: the session is flushed server-side; answer 401 (signed-out state) |

- **Session cookie hardening** — HttpOnly, SameSite=Lax everywhere; in staging/prod also Secure and
  the `__Host-` prefix (`__Host-numo9_session`, `__Host-numo9_csrf`): HTTPS only, exact host, no
  Domain, path `/`. The session id is rotated at login (no fixation) and the session is deleted
  at logout, so a copied cookie stops working. CSRF token required on login (`X-CSRFToken`).
- **Rate limits** (`ACCOUNT_RATE_LIMITS`, counters in the shared Redis cache in staging/prod):
  20 login attempts a minute per IP; 20 failed attempts a minute per IP; 10 failed attempts per
  account in 15 minutes (S-03-T07 turns this into a fixed 15-minute lockout).

Tests: `backend/tests/test_auth_login.py`.
