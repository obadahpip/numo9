/**
 * K-01-T17 — k6 benchmark of the report engine: p95 < 3 s for 12-month reports over a
 * 100,000-line general ledger.
 *
 *   python backend/manage.py seed_report_books --lines 100000 --password "$SEED_PASSWORD"
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 -e PASSWORD="$SEED_PASSWORD" tools/perf/k6/reports.js
 *
 * Load: 5 people (VUS) running reports on the seeded organisation, each pausing 0.5–1.5 s (THINK)
 * — under the organisation's default rate limit (600/min, S-06-T05). In turn: account activity
 * for the last 12 months (every account's debits, credits and net movement), the trial balance as
 * at today, a drill-down of one figure and the 12-month report as XLSX. Thresholds fail the run
 * when p95 of a report run or export reaches 3 s, a drill-down 1 s, or any request fails.
 */
import http from "k6/http";
import { check, fail, sleep } from "k6";
import exec from "k6/execution";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = __ENV.EMAIL || "seed-reports@numo9.test";
const PASSWORD = __ENV.PASSWORD || "";
const ORG_NAME = "Report Seed Interiors Inc.";
const [THINK_MIN, THINK_MAX] = (__ENV.THINK || "0.5-1.5").split("-").map(Number);

export const options = {
  noCookiesReset: true,
  scenarios: {
    reports: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:run}": ["p(95)<3000"],
    "http_req_duration{endpoint:export}": ["p(95)<3000"],
    "http_req_duration{endpoint:drill}": ["p(95)<1000"],
    "checks{endpoint:run}": ["rate==1"],
    http_req_failed: ["rate==0"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

let organisation = "";

function day(offset) {
  const date = new Date(Date.now() + offset * 86400000);
  return date.toISOString().slice(0, 10);
}

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
  const mine = http.get(`${BASE_URL}/api/v1/me/organisations`, { tags: { endpoint: "auth" } });
  const found = (mine.json() || []).find((o) => o.name === ORG_NAME);
  if (!found) fail(`${ORG_NAME} not found: run seed_report_books first.`);
  organisation = found.id;
}

export function setup() {
  if (!PASSWORD) fail("Set PASSWORD (the seeded owner's password, seed_report_books --password).");
  return {};
}

const REQUESTS = [
  (base, year) => [`${base}/account-activity/run?${year}`, "run"],
  (base) => [`${base}/trial-balance/run?as_of=${day(0)}`, "run"],
  (base) => [`${base}/account-activity/drill?account=7003&from=${day(-364)}&to=${day(0)}`, "drill"],
  (base, year) => [`${base}/account-activity/export?file=xlsx&${year}`, "export"],
];

export default function () {
  if (!organisation) signIn();
  const base = `${BASE_URL}/api/v1/o/${organisation}/reports`;
  const year = `date_from=${day(-364)}&date_to=${day(0)}`;
  const [url, endpoint] = REQUESTS[exec.scenario.iterationInTest % REQUESTS.length](base, year);
  const response = http.get(url, { headers: { Accept: "application/json" }, tags: { endpoint } });
  check(response, { [`${endpoint}: 200`]: (r) => r.status === 200 }, { endpoint });
  if (endpoint === "run") {
    check(
      response,
      { "run: rows and totals": (r) => Array.isArray(r.json("rows")) && r.json("rows").length > 0 },
      { endpoint },
    );
  }
  sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
}
