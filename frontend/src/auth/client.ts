/**
 * Client for the authentication API (A-02-T10…T12): django-allauth headless, browser client,
 * under `/_allauth/browser/v1/` (docs/architecture/authentication.md), and the Numo9 JSON API
 * under `/api/v1/`.
 *
 * - Unsafe requests carry the CSRF token from `GET /api/v1/auth/csrf` (S-03-T01) in
 *   `X-CSRFToken`; the token is fetched once per page and fetched again after a 403 CSRF
 *   failure (login and logout rotate it).
 * - Cookies are same-origin (`credentials: "same-origin"`): the session never leaves the
 *   HttpOnly cookie, and tokens from emailed links travel in request bodies only.
 * - Every call resolves (it never throws on an HTTP error status): screens branch on
 *   `status`, the pending flow and the error codes, so each state has its own message.
 */
export const AUTH_API = "/_allauth/browser/v1";
export const CSRF_URL = "/api/v1/auth/csrf";

/** One error of an allauth answer: `{message, code, param?}`. */
export interface AuthError {
  message: string;
  code: string;
  param?: string;
}

export interface AuthFlow {
  id: string;
  is_pending?: boolean;
}

/** allauth headless answer body (success or error). */
export interface AuthBody {
  status?: number;
  data?: {
    flows?: AuthFlow[];
    user?: { email?: string; display?: string };
    [key: string]: unknown;
  };
  meta?: { is_authenticated?: boolean; [key: string]: unknown };
  errors?: AuthError[];
}

export interface ApiResult<Body> {
  /** HTTP status; 0 when the network request itself failed (offline, DNS, reset). */
  status: number;
  body: Body;
  /** `Retry-After` in seconds (429), when sent. */
  retryAfter?: number;
}

let csrf: Promise<string> | undefined;

async function csrfToken(fetcher: typeof fetch): Promise<string> {
  csrf ??= fetcher(CSRF_URL, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`${CSRF_URL} answered ${response.status}`);
      const body = (await response.json()) as { csrfToken?: unknown };
      if (typeof body.csrfToken !== "string") throw new Error(`${CSRF_URL}: no token`);
      return body.csrfToken;
    })
    .catch((error: unknown) => {
      csrf = undefined;
      throw error;
    });
  return csrf;
}

/** The CSRF token for a plain HTML form post (social sign-in redirect, A-02-T16). */
export function formCsrfToken(): Promise<string> {
  return csrfToken(fetch);
}

/** Forget the cached CSRF token (tests; after login/logout, which rotate it). */
export function resetCsrfToken(): void {
  csrf = undefined;
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  fetcher?: typeof fetch;
  /** Waits before a rate-limit retry (S-06-T06); tests pass a fake. */
  wait?: (ms: number) => Promise<void>;
}

/**
 * Per-organisation rate limit (S-06-T05/T06): a `429` with code `request.rate_limited` was refused
 * before the server did anything, so the request is sent again by itself after `Retry-After`
 * (doubling each time, at most `RATE_LIMIT_RETRIES` times, never waiting more than 30 s). Each
 * wait is announced with the `numo9:rate-limited` window event (`detail.seconds`), which the
 * app's `RateLimitToast` shows. Other `429`s (a locked sign-in) are returned as they are.
 */
export const RATE_LIMIT_EVENT = "numo9:rate-limited";
export const RATE_LIMIT_RETRIES = 3;
const RATE_LIMIT_CODE = "request.rate_limited";
const MAX_WAIT_SECONDS = 30;

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

async function rateLimitWait(response: Response, attempt: number): Promise<number | null> {
  if (response.status !== 429 || attempt >= RATE_LIMIT_RETRIES) return null;
  const after = Number(response.headers.get("Retry-After"));
  if (!Number.isFinite(after) || after <= 0 || after > MAX_WAIT_SECONDS) return null;
  try {
    const body = (await response.clone().json()) as { code?: unknown };
    if (body?.code !== RATE_LIMIT_CODE) return null;
  } catch {
    return null;
  }
  return Math.min(MAX_WAIT_SECONDS, Math.ceil(after) * 2 ** attempt);
}

function announceRateLimit(seconds: number): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(RATE_LIMIT_EVENT, { detail: { seconds } }));
}

/** JSON request to `url`; never throws for HTTP errors (see `ApiResult.status`). */
export async function apiRequest<Body = AuthBody>(
  url: string,
  { method = "GET", body, headers = {}, fetcher = fetch, wait = sleep }: RequestOptions = {},
): Promise<ApiResult<Body>> {
  const send = async (): Promise<Response> => {
    const all: Record<string, string> = { Accept: "application/json", ...headers };
    const form = typeof FormData !== "undefined" && body instanceof FormData;
    // A FormData body (file upload, B-03-T12) sets its own multipart boundary.
    if (body !== undefined && !form) all["Content-Type"] = "application/json";
    if (UNSAFE.has(method)) all["X-CSRFToken"] = await csrfToken(fetcher);
    return fetcher(url, {
      method,
      credentials: "same-origin",
      headers: all,
      body: body === undefined ? undefined : form ? (body as FormData) : JSON.stringify(body),
    });
  };
  let response: Response;
  try {
    response = await send();
    if (response.status === 403 && UNSAFE.has(method) && (await isCsrfFailure(response))) {
      resetCsrfToken(); // the token rotated (login/logout in another tab): fetch it again once
      response = await send();
    }
    for (let attempt = 0; ; attempt += 1) {
      const seconds = await rateLimitWait(response, attempt);
      if (seconds === null) break;
      announceRateLimit(seconds);
      await wait(seconds * 1000);
      response = await send();
    }
  } catch {
    return { status: 0, body: {} as Body };
  }
  let parsed: unknown = {};
  try {
    parsed = await response.json();
  } catch {
    parsed = {};
  }
  const retry = Number(response.headers.get("Retry-After"));
  return {
    status: response.status,
    body: (parsed ?? {}) as Body,
    retryAfter: Number.isFinite(retry) && retry > 0 ? retry : undefined,
  };
}

async function isCsrfFailure(response: Response): Promise<boolean> {
  try {
    const text = await response.clone().text();
    return /csrf/i.test(text);
  } catch {
    return false;
  }
}

/** Request to the allauth headless browser API: `authRequest("/auth/login", {…})`. */
export function authRequest(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResult<AuthBody>> {
  return apiRequest<AuthBody>(`${AUTH_API}${path}`, options);
}

/** id of the pending flow (`verify_email`, `mfa_authenticate`, `mfa_trust`, …), if any. */
export function pendingFlow(body: AuthBody): string | undefined {
  return body.data?.flows?.find((flow) => flow.is_pending)?.id;
}

export function isAuthenticated(body: AuthBody): boolean {
  return body.meta?.is_authenticated === true;
}

/** Error codes of an allauth answer, e.g. `["email_password_mismatch"]`. */
export function errorCodes(body: AuthBody): string[] {
  return (body.errors ?? []).map((error) => error.code);
}

/** Field errors by request parameter (`email`, `password`, …); errors without `param` go to "". */
export function fieldErrors(body: AuthBody): Record<string, AuthError[]> {
  const byField: Record<string, AuthError[]> = {};
  for (const error of body.errors ?? []) {
    const key = error.param ?? "";
    (byField[key] ??= []).push(error);
  }
  return byField;
}

/** Numo9 API error body (`numo9.i18n.exceptions`): `{detail, code}`. */
export interface Numo9Error {
  detail?: string;
  code?: string;
  [field: string]: unknown;
}
