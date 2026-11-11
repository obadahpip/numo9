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

## Invitations (A-02-T08, A-02-T09)

`tenancy.Invitation` (`backend/numo9/tenancy/models.py`) — an emailed, single-use invitation to
join a practice or an organisation. It is a platform model (on the `OrgOwnedModel` allow-list):
it names a tenant and the address of someone who is not a member yet.

| Field | Meaning |
|---|---|
| `kind` | `practice_staff` · `organisation_owner` (a practice invites the owner of a client organisation it created) · `organisation_user` · `organisation_accountant` (an organisation invites its accountant) |
| `inviter` | the user who sent it |
| `practice` / `organisation` | the target: `practice` for `practice_staff`, `organisation` for the other three (database check) |
| `role` | a practice role (`practice_staff`), `owner` (`organisation_owner`), an organisation role (`organisation_user`) or an assignment role — what the accountant's practice will do (`organisation_accountant`); database check per kind |
| `email` | invited address, lower-cased |
| `token_hash` | SHA-256 of the 256-bit link token; the token itself is never stored |
| `expires_at` | 7 days after sending (`INVITATION_TTL`) |
| `accepted_at` / `accepted_by`, `revoked_at` | outcome — never both accepted and revoked |
| `send_count`, `last_sent_at` | resend bookkeeping |

**At most one pending invitation per email address and target** (partial unique constraints on
`(email, practice)` and `(email, organisation)` while neither accepted nor revoked); accepting or
revoking frees the slot. Status: `pending`, `accepted`, `revoked` or `expired` (past
`expires_at`).

Tests: `backend/tests/test_invitation_model.py`.

### Invitation service and API (A-02-T09)

Service: `backend/numo9/tenancy/invitations.py` · API: `backend/numo9/tenancy/invitations_api.py`.

| Flow | Who may send | Accepting creates |
|---|---|---|
| `practice_staff` | a practice admin of the practice | `PracticeMember` with the role |
| `organisation_owner` | a practice member who reaches the organisation through its practice assignment, while it has no owner | `OrganisationMember` (owner); the practice stays assigned |
| `organisation_user` | the organisation's owner or an admin | `OrganisationMember` with the role |
| `organisation_accountant` | the organisation's owner or an admin | `PracticeAssignment` of the accountant's practice (role = what the practice does) with the accountant as assigned staff — reactivated if it existed; an accountant in several practices picks one (`practice`); one with **no practice gets a pending practice** (`Practice.setup_pending`, finished in onboarding) |

| Call | Answer |
|---|---|
| `POST /api/v1/invitations` `{kind, email, role?, practice? \| organisation?}` | `201` and the email is sent · `403 invitation.not_allowed` (also for an unknown target) · `409 already_member` / `already_pending` / `has_owner` · `400 role_invalid` |
| `POST /api/v1/invitations/<id>/resend` | `200`: new link (the old one stops working), fresh 7-day expiry · `429 resend_too_soon` (1 minute) · `404` not yours |
| `POST /api/v1/invitations/<id>/revoke` | `200` · `409 not_pending` · `404` not yours |
| `POST /api/v1/invitations/preview` `{token}` | anyone with the link: target, inviter, role, expiry · `404 invalid` · `410 used` / `revoked` / `expired` |
| `POST /api/v1/invitations/accept` `{token, practice?}` | signed in **as the invited email**: `200` · `403 wrong_account` (names the invited address so the screen can offer to switch) · `410` used/revoked/expired · `400 choose_practice` |

- Links (`<NUMO9_FRONTEND_URL>/invite/<token>`) are emailed in the target's language; the token
  goes back to the API in the request body, never in a URL, so it stays out of access logs.
- An invitee who already has an account is attached, never duplicated; a new invitee signs up
  with the invited email first, then accepts.
- Sending again while one is waiting is refused (resend it); an expired one is replaced.
- The routes are not organisation-scoped (practice invitations have no organisation), so they are
  on the tenant-sweep exempt list; the service checks every object (404 for foreign invitations,
  the same 403 for an unknown and a foreign target). A-03 replaces the role checks with the
  permission catalogue.

Tests: `backend/tests/test_invitations.py`.

## Web screens (A-02-T10 … T12)

Code: `frontend/src/auth/` (screens and the API client), routes in `frontend/src/app/`. The
screens use the design system (`@numo9/ui` form kit, buttons, states) inside one public
frame (`AuthLayout`: wordmark, one card, no app shell, no promotions); every string is an i18n
message (`auth.*`, `form.*`).

**API client** (`frontend/src/auth/client.ts`): same-origin calls to `/_allauth/browser/v1/…`
and `/api/v1/…`; unsafe requests carry `X-CSRFToken` from `GET /api/v1/auth/csrf` (fetched once,
fetched again once after a CSRF failure); calls never throw on an HTTP status, so each screen
branches on the status, the pending flow and the error codes. Tokens from emailed links go in
request bodies only; the pages that receive them send `Referrer-Policy: no-referrer`.

**Local development**: `NUMO9_BACKEND_URL` (set to `http://backend:8000` in
`docker-compose.dev.yml`) makes Next.js forward `/api/v1/*` and `/_allauth/*` to Django
(`frontend/src/routing/backend.ts`); the dev settings trust `NUMO9_FRONTEND_URL` as a CSRF
origin (`DJANGO_CSRF_TRUSTED_ORIGINS` overrides). In staging/prod the reverse proxy routes them.

### Sign-up (A-02-T10)

| Route | Screen |
|---|---|
| `/signup` | Step 1 — choose *I'm an accountant* (free practice) or *I run a business* (30-day trial). `?path=accountant` / `?path=organisation` skips it. |
| | Step 2 — four fields: name, email, password (show/hide, strength meter, ≥ 12 characters), practice or business name. Client-side checks first (error summary + inline errors, focus on the first error); server field errors (e.g. breached password) land on their field; 429 / offline / 5xx get their own message. |
| | Step 3 — *Open the link we emailed you*: names the address, says the link works 3 days, what to do if nothing arrives. The same answer for an address that already has an account (no enumeration). |
| `/verify/<key>` | Posts the key once: **verified and signed in** (same browser) → *Continue to Numo9*; **verified, sign in** (other browser); **link doesn't work any more** (expired/used/invalid) → sign in, which emails a new link; **couldn't check** (network/server) → *Try again*. |

Focus moves to the heading at each step. Tests: `frontend/e2e/auth-signup.spec.ts` (flows at
360 and 1280 px, axe 0 serious/critical at every step, keyboard-only sign-up, validation, server
errors, rate limit, offline, every verify state), `frontend/src/auth/*.test.ts`.

### Login, 2FA challenge and password reset (A-02-T11)

| Route | Screen |
|---|---|
| `/login` | Email + password. Wrong email and wrong password get **one** message (no enumeration); a locked account (429) says for how many minutes and points to the reset, which unlocks it; an unverified address is told a new link was emailed. `?next=` returns to a same-site path after signing in (absolute, `//host`, back-slash and auth-screen targets go Home — no open redirect). `?reset=done` confirms a completed reset. |
| (step) / `/2fa` | **Authentication code** when the answer is the pending `mfa_authenticate` flow: `CodeInput` (6 boxes, auto-advance, submits when complete, Backspace/←/→/Home/End, **paste-aware** — the whole code pasted into any box, or an email line such as "Your Numo9 code: 482 913", fills every box; `autocomplete="one-time-code"`), *Remember this device for 30 days* (answers `mfa_trust`), *Use a recovery code instead*, guidance for a lost device. Wrong code: the boxes clear and focus returns to the first. A timed-out pending login sends the user back to sign in. `/2fa` shows the same step after a reload, or explains that no sign-in is waiting. |
| `/reset` | Request a link; the confirmation is the same for any address. |
| `/reset/<key>` | The key is checked first (dead link says so before any typing); new password + confirmation (strength meter, ≥ 12 characters); server password rules land on the field; success goes to `/login?reset=done` (every session was ended). |

`CodeInput` lives in the design system (`packages/ui/src/primitives/CodeInput.tsx`, story
*Primitives / CodeInput*). Tests: `frontend/e2e/auth-login.spec.ts` (keyboard-only sign-in with
2FA and remember-device, paste, recovery codes, lockout, unverified, `next` safety, `/2fa`, reset
request / new password / dead link; axe on every screen), `CodeInput.test.tsx`, `nextUrl.test.ts`.

### Invitation accept (A-02-T12)

`/invite/<token>` — the link from an invitation email. The page posts the token to
`POST /api/v1/invitations/preview` (body only, never in an API URL; the page sends
`Referrer-Policy: no-referrer`) and reads the session, then shows one state:

| State | Screen |
|---|---|
| Signed out | Who invited, to what, with which role ("Dana Lee invited you to join Refined Interiors Inc. as Purchasing."), the invited address and expiry date. *Sign in to accept* (returns here through `?next=`) or *Create an account* with the invited address. |
| Signed in as the invited email | *Accept invitation* → `POST …/accept`. An accountant in several practices is asked which practice serves the client (`invitation.choose_practice` → a practice picker, then accept again). |
| Signed in as another account | *This invitation is for another account*: names both addresses; *Sign out and continue* ends the session and shows the signed-out state; or stay and go Home. |
| Accepted | *You've joined …* with a link to the organisation's Home (Home for a practice). |
| Expired · already used · withdrawn · invalid | One heading per case and the server's explanation (`invitation.expired` with the date, `used`, `revoked`, `invalid`); used → sign in, others → Home. An invitation used or withdrawn between opening and accepting switches to that state. |
| Unreachable | Message and *Try again*. |

Tests: `frontend/e2e/auth-invite.spec.ts` (every state, at 360 and 1280 px, axe on each).
