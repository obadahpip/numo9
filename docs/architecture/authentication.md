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
  20 login attempts a minute per IP; 20 failed attempts a minute per IP. Per account: 10 failed
  attempts lock the address for 15 minutes, and a CAPTCHA hook after 5 failures — see
  [Security baseline § S-03-T07](../security/security-baseline.md#s-03-t07-brute-force-protection-on-login).

Tests: `backend/tests/test_auth_login.py`.

## Password reset (A-02-T04)

| Call | Answer |
|---|---|
| `POST /_allauth/browser/v1/auth/password/request` `{email}` | always **200** — the same for an unknown address (that mailbox is told no account exists); the account's address gets a link `<NUMO9_FRONTEND_URL>/reset/<key>` |
| `GET /_allauth/browser/v1/auth/password/reset` with header `X-Password-Reset-Key` | 200 key valid · 400 invalid/expired/used |
| `POST /_allauth/browser/v1/auth/password/reset` `{key, password}` | new password set → **401** (signed out; sign in again) · **400** `invalid_password_reset` or a password-rule error |

- The key is valid for **1 hour** (`PASSWORD_RESET_TIMEOUT = 3600`) and works **once**: it is
  bound to the current password hash, so it dies the moment the password changes.
- Setting the new password **ends every session** of the user (all browsers and devices); the
  user is not signed in automatically (`ACCOUNT_LOGIN_ON_PASSWORD_RESET = False`).
- A completed reset clears the login failure count and any lockout (S-03-T07); the user is
  emailed that the password changed.

Tests: `backend/tests/test_auth_password_reset.py`.

## Two-factor authentication — TOTP (A-02-T05)

allauth.mfa with Numo9 adjustments (`numo9/accounts/mfa.py`). Changing 2FA needs a fresh
password confirmation: `POST /auth/reauthenticate {password}` (valid 5 minutes), otherwise the
answer is `401` with the `reauthenticate` flow.

| Step | Call |
|---|---|
| Set-up data | `GET /_allauth/browser/v1/account/authenticators/totp` → `404` (not enrolled) with `meta.secret`, `meta.totp_url` (`otpauth://…&issuer=Numo9`) and `meta.qr_code` (SVG as a `data:` URI — allowed by the CSP) |
| Verify + activate | `POST …/account/authenticators/totp {code}` → `200`; `meta.recovery_codes` holds the **10 recovery codes — the only time they are shown** · wrong code `400` |
| New recovery codes | `POST …/account/authenticators/recovery-codes` → the new 10 (old ones stop working) |
| Login challenge | after the password, `401` with pending flow `mfa_authenticate` → `POST /auth/2fa/authenticate {code}` (TOTP or recovery code) |
| Remember this device | then pending `mfa_trust` → `POST /auth/2fa/trust {trust: true|false}` → `200` signed in |

- **TOTP**: 6 digits, 30-second steps, **±1 step** accepted for clock skew, a used code cannot be
  replayed. The secret is stored **encrypted** with the field-encryption key ring (AES-256-GCM,
  context `allauth.mfa.Authenticator.data`).
- **Recovery codes**: 10 codes like `k7m2p-x9qrt` (50 bits); only a password hash of each is
  stored (Argon2id in staging/prod), each works **once**, input is case- and dash-insensitive.
  Implemented by `HashedRecoveryCodes`, which replaces allauth's seed-derived codes at start-up;
  a test fails if an allauth upgrade bypasses it.
- **Remember this device**: a signed cookie (`numo9_trusted_device`, `__Host-` prefixed in
  staging/prod; HttpOnly, SameSite=Lax) valid **30 days**, bound to the user's password and
  authenticators — a password change or a new/removed authenticator voids it; it does not work
  for another account.

Tests: `backend/tests/test_auth_totp.py`.
