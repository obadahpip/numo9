/**
 * U-07-T05/T11 — k6: opening a demo (template clone) takes < 10 s p95.
 *
 *   NUMO9_DEMO_OPEN_PER_HOUR=100000 gunicorn numo9.wsgi …
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 tools/perf/k6/demo-open.js
 *
 * 10 anonymous visitors press "Try the demo" at once, again and again: each iteration is a new
 * visitor (fresh cookies) — CSRF token, then POST /api/v1/demo, then the first contacts page.
 */
import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";

export const options = {
  scenarios: {
    open: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:demo_open}": ["p(95)<10000"],
    "checks{endpoint:demo_open}": ["rate==1"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export default function () {
  const token = http.get(`${BASE_URL}/api/v1/auth/csrf`).json("csrfToken");
  const opened = http.post(`${BASE_URL}/api/v1/demo`, null, {
    headers: { "X-CSRFToken": token, Referer: BASE_URL, Accept: "application/json" },
    tags: { endpoint: "demo_open" },
  });
  check(opened, { "demo opened: 201": (r) => r.status === 201 }, { endpoint: "demo_open" });
  if (opened.status === 201) {
    const org = opened.json("organisation");
    http.get(`${BASE_URL}/api/v1/o/${org}/contacts?limit=50`, { tags: { endpoint: "first_page" } });
  }
}
