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
}

/** JSON request to `url`; never throws for HTTP errors (see `ApiResult.status`). */
export async function apiRequest<Body = AuthBody>(
  url: string,
  { method = "GET", body, headers = {}, fetcher = fetch }: RequestOptions = {},
): Promise<ApiResult<Body>> {
  const send = async (): Promise<Response> => {
    const all: Record<string, string> = { Accept: "application/json", ...headers };
    if (body !== undefined) all["Content-Type"] = "application/json";
    if (UNSAFE.has(method)) all["X-CSRFToken"] = await csrfToken(fetcher);
    return fetcher(url, {
      method,
      credentials: "same-origin",
      headers: all,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  };
  let response: Response;
  try {
    response = await send();
    if (response.status === 403 && UNSAFE.has(method) && (await isCsrfFailure(response))) {
      resetCsrfToken(); // the token rotated (login/logout in another tab): fetch it again once
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
