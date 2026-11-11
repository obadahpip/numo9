import { vi } from "vitest";

import {
  apiRequest,
  authRequest,
  errorCodes,
  fieldErrors,
  isAuthenticated,
  pendingFlow,
  resetCsrfToken,
} from "./client";

function json(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function fakeFetch(...answers: (Response | Error)[]) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetcher = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    const next = answers.shift();
    if (!next) throw new Error("no more answers");
    if (next instanceof Error) throw next;
    return next;
  });
  return { fetcher: fetcher as unknown as typeof fetch, calls };
}

beforeEach(() => resetCsrfToken());

describe("apiRequest", () => {
  it("sends the CSRF token on unsafe requests, fetched once and cached", async () => {
    const { fetcher, calls } = fakeFetch(
      json(200, { csrfToken: "tok" }),
      json(401, { status: 401 }),
      json(200, { status: 200 }),
    );
    await authRequest("/auth/login", { method: "POST", body: { email: "a@b.ca" }, fetcher });
    await authRequest("/auth/signup", { method: "POST", body: {}, fetcher });
    expect(calls.map((c) => c.url)).toEqual([
      "/api/v1/auth/csrf",
      "/_allauth/browser/v1/auth/login",
      "/_allauth/browser/v1/auth/signup",
    ]);
    const headers = calls[1]!.init.headers as Record<string, string>;
    expect(headers["X-CSRFToken"]).toBe("tok");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(calls[1]!.init.credentials).toBe("same-origin");
    expect(calls[1]!.init.body).toBe('{"email":"a@b.ca"}');
  });

  it("GET carries no CSRF token and no body", async () => {
    const { fetcher, calls } = fakeFetch(json(200, { meta: { is_authenticated: true } }));
    const result = await authRequest("/auth/session", { fetcher });
    expect(result.status).toBe(200);
    expect(calls).toHaveLength(1);
    expect((calls[0]!.init.headers as Record<string, string>)["X-CSRFToken"]).toBeUndefined();
  });

  it("refetches the token once after a CSRF failure", async () => {
    const { fetcher, calls } = fakeFetch(
      json(200, { csrfToken: "old" }),
      json(403, { detail: "CSRF Failed: CSRF token incorrect." }),
      json(200, { csrfToken: "new" }),
      json(200, { status: 200 }),
    );
    const result = await apiRequest("/api/v1/invitations/accept", {
      method: "POST",
      body: {},
      fetcher,
    });
    expect(result.status).toBe(200);
    expect((calls[3]!.init.headers as Record<string, string>)["X-CSRFToken"]).toBe("new");
  });

  it("a 403 that is not about CSRF is returned as is", async () => {
    const { fetcher } = fakeFetch(
      json(200, { csrfToken: "t" }),
      json(403, { code: "invitation.wrong_account", detail: "This invitation is for x" }),
    );
    const result = await apiRequest("/api/v1/invitations/accept", {
      method: "POST",
      body: {},
      fetcher,
    });
    expect(result.status).toBe(403);
    expect(result.body).toMatchObject({ code: "invitation.wrong_account" });
  });

  it("network failure → status 0; Retry-After is parsed", async () => {
    const offline = fakeFetch(new TypeError("Failed to fetch"));
    expect((await authRequest("/auth/session", { fetcher: offline.fetcher })).status).toBe(0);

    const limited = fakeFetch(
      json(200, { csrfToken: "t" }),
      json(429, {}, { "Retry-After": "900" }),
    );
    const result = await authRequest("/auth/login", {
      method: "POST",
      body: {},
      fetcher: limited.fetcher,
    });
    expect(result).toMatchObject({ status: 429, retryAfter: 900 });
  });

  it("a non-JSON body is tolerated", async () => {
    const { fetcher } = fakeFetch(new Response("<html>bad gateway</html>", { status: 502 }));
    expect(await authRequest("/auth/session", { fetcher })).toMatchObject({
      status: 502,
      body: {},
    });
  });
});

describe("answer helpers", () => {
  const body = {
    data: { flows: [{ id: "login" }, { id: "mfa_authenticate", is_pending: true }] },
    meta: { is_authenticated: false },
    errors: [
      { message: "Bad code", code: "incorrect_code", param: "code" },
      { message: "General", code: "x" },
    ],
  };
  it("reads the pending flow, auth state, codes and field errors", () => {
    expect(pendingFlow(body)).toBe("mfa_authenticate");
    expect(pendingFlow({})).toBeUndefined();
    expect(isAuthenticated(body)).toBe(false);
    expect(isAuthenticated({ meta: { is_authenticated: true } })).toBe(true);
    expect(errorCodes(body)).toEqual(["incorrect_code", "x"]);
    expect(Object.keys(fieldErrors(body))).toEqual(["code", ""]);
  });
});
