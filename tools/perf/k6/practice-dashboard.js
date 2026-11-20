/**
 * V-04-T10 — k6 benchmark of the practice home: p95 < 1.5 s over 2,000 organisations.
 *
 *   python backend/manage.py seed_practice --orgs 2000 --password "$SEED_PASSWORD" --force
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 -e EMAIL=seed-admin@numo9.test \
 *          -e PASSWORD="$SEED_PASSWORD" tools/perf/k6/practice-dashboard.js
 *
 * Load: 20 practice admins (VUS) opening their home at once, each pausing 1–3 s (THINK), the
 * whole practice and their own organisations in turn, plus a card's drill-down into the
 * directory (the same filters). Thresholds fail the run when p95 of the dashboard reaches 1.5 s,
 * a drill-down 300 ms, or any request fails.
 */
import http from "k6/http";
import { check, fail, sleep } from "k6";
import exec from "k6/execution";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = __ENV.EMAIL || "seed-admin@numo9.test";
const PASSWORD = __ENV.PASSWORD || "";
const PRACTICE = __ENV.PRACTICE_ID || "";
const [THINK_MIN, THINK_MAX] = (__ENV.THINK || "1-3").split("-").map(Number);

export const options = {
  noCookiesReset: true,
  scenarios: {
    dashboard: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 20),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:dashboard}": ["p(95)<1500"],
    "http_req_duration{endpoint:drilldown}": ["p(95)<300"],
    "checks{endpoint:dashboard}": ["rate==1"],
    http_req_failed: ["rate==0"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

let signedIn = false;

function signIn() {
  const csrf = http.get(`${BASE_URL}/api/v1/auth/csrf`, { tags: { endpoint: "auth" } });
  const token = csrf.json("csrfToken");
  const login = http.post(
    `${BASE_URL}/_allauth/browser/v1/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    {
      headers: { "Content-Type": "application/json", "X-CSRFToken": token, Referer: BASE_URL },
      tags: { endpoint: "auth" },
    },
  );
  if (login.status !== 200) fail(`sign-in failed (${login.status}): ${login.body}`);
  signedIn = true;
}

function query(params) {
  return Object.entries(params)
    .flatMap(([key, values]) =>
      (Array.isArray(values) ? values : [values]).map(
        (v) => `${encodeURIComponent(key)}=${encodeURIComponent(v)}`,
      ),
    )
    .join("&");
}

export function setup() {
  if (!PASSWORD) fail("Set PASSWORD (the seeded admin's password, seed_practice --password).");
  return {};
}

export default function () {
  if (!signedIn) signIn();
  const scope = exec.scenario.iterationInTest % 2 === 0 ? "all" : "mine";
  const practice = PRACTICE ? { practice: PRACTICE } : {};
  const response = http.get(
    `${BASE_URL}/api/v1/practice/dashboard?${query({ ...practice, scope })}`,
    { headers: { Accept: "application/json" }, tags: { endpoint: "dashboard", scope } },
  );
  const ok = check(
    response,
    {
      "dashboard: 200": (r) => r.status === 200,
      "dashboard: every widget ok": (r) => r.json("widgets").every((w) => w.status === "ok"),
    },
    { endpoint: "dashboard" },
  );
  if (ok) {
    const cards = response.json("widgets").filter((w) => w.filters);
    const card = cards[exec.scenario.iterationInTest % Math.max(1, cards.length)];
    if (card) {
      const drill = http.get(
        `${BASE_URL}/api/v1/practice/orgs?${query({ ...practice, ...card.filters, page_size: 50 })}`,
        { headers: { Accept: "application/json" }, tags: { endpoint: "drilldown" } },
      );
      check(drill, { "drill-down: 200": (r) => r.status === 200 }, { endpoint: "drilldown" });
    }
  }
  sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
}
