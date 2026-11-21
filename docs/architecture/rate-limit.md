# Per-organisation rate limit (S-06-T05)

Every API request made **inside an organisation** — `/api/v1/o/<org>/…` or with the
`X-Numo9-Org` header — takes one token from that organisation's bucket
(`numo9.scale.ratelimit.OrgRateLimitMiddleware`, right after the tenant middleware). Requests
outside an organisation (sign-in, `/me`, the console, public pages) are not limited here.

| | Default | Per package (`limits`, U-02) | Setting |
|---|---|---|---|
| Sustained rate | 600 requests a minute | `api_requests_per_minute` | `NUMO9_ORG_RATE_PER_MINUTE` |
| Burst | 100 requests at once | `api_burst` | `NUMO9_ORG_RATE_BURST` |

- **Token bucket in Redis.** One hash per organisation (`numo9:ratelimit:org:<id>`, database 5 of
  `REDIS_URL`, `NUMO9_RATE_LIMIT_REDIS_URL`) updated by a single Lua script, so every app server
  shares the bucket exactly and two requests can never take the same token. It refills at
  `per_minute / 60` tokens a second, up to the burst, and expires when idle.
- **When it's empty** the answer is `429` with code `request.rate_limited`, a translated
  message ("You're going a little fast. Try again in N seconds."), `Retry-After: N` (whole
  seconds until a token is back), `X-RateLimit-Limit`. Every limited response carries
  `X-RateLimit-Limit` and `X-RateLimit-Remaining`.
- **Never takes the service down.** Redis unreachable (250 ms timeouts) → the request goes
  through and a warning is logged.
- The organisation's policy (package limits or defaults) is cached 60 s.
- `NUMO9_ORG_RATE_LIMIT_ENABLED` (on). The test settings turn it off for the suite;
  `backend/tests/test_rate_limit.py` turns it on (in-process buckets, and the Lua script on Redis
  when `NUMO9_TEST_REDIS_URL` is set).

The web app retries a `429` on its own after `Retry-After` and shows a short toast
(S-06-T06, `frontend/src/auth/client.ts`).
