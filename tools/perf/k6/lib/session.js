/**
 * Shared by the S-06-T09 baselines: sign in once per virtual user (CSRF token + allauth browser
 * login, the session cookie is kept between iterations) and list the practice's organisations.
 */
import http from "k6/http";
import { fail } from "k6";

export const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
export const EMAIL = __ENV.EMAIL || "fixture-admin@example.com";
export const PASSWORD = __ENV.PASSWORD || "";

let csrfToken = "";

export function signIn() {
  const csrf = http.get(`${BASE_URL}/api/v1/auth/csrf`, { tags: { endpoint: "auth" } });
  csrfToken = csrf.json("csrfToken");
  const login = http.post(
    `${BASE_URL}/_allauth/browser/v1/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    {
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, Referer: BASE_URL },
      tags: { endpoint: "auth" },
    },
  );
  if (login.status !== 200) fail(`sign-in failed (${login.status}): ${login.body}`);
  // The session rotates the CSRF token at sign-in.
  csrfToken = http
    .get(`${BASE_URL}/api/v1/auth/csrf`, { tags: { endpoint: "auth" } })
    .json("csrfToken");
  return csrfToken;
}

export function writeHeaders() {
  return {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-CSRFToken": csrfToken,
    Referer: BASE_URL,
  };
}

/** The organisations of the signed-in practice user (the directory's full list). */
export function organisations(limit) {
  const response = http.get(`${BASE_URL}/api/v1/practice/orgs?page_size=${limit || 2000}`, {
    headers: { Accept: "application/json" },
    tags: { endpoint: "setup" },
  });
  if (response.status !== 200) fail(`directory failed (${response.status})`);
  const rows = response.json("results") || [];
  const ids = rows.map((row) => row.id || row.public_id || row.organisation).filter(Boolean);
  if (!ids.length) fail("No organisations: run make_fixture_practice first.");
  return ids;
}

export function requirePassword() {
  if (!PASSWORD) fail("Set PASSWORD (make_fixture_practice --password).");
}

export function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}
