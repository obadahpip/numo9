/**
 * V-01-T07 — k6 benchmark of the organisation directory: p95 < 300 ms over 2,000 organisations.
 *
 * Prepare a staging-size practice, then run against the API (dev stack, staging or a local
 * gunicorn):
 *
 *   python backend/manage.py seed_practice --orgs 2000 --password "$SEED_PASSWORD" --force
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 -e EMAIL=seed-admin@numo9.test \
 *          -e PASSWORD="$SEED_PASSWORD" tools/perf/k6/directory-search.js
 *
 * Load: 30 accountants (VUS) working the directory at once, each pausing 0.5–2 s between requests
 * (THINK) — about 25 directory requests a second, far more than a practice of 2,000 clients
 * generates. THINK=0 turns it into a saturation test (requests back to back).
 *
 * Each virtual user signs in once (CSRF token + allauth browser login), then sends the requests
 * an accountant makes while working the directory: the first page with facet counts, word and
 * accent-insensitive searches, BN fragments typed with spaces, filters, sorts, the full
 * 2,000-row list the virtualised grid loads, and the Ctrl/⌘+K "go to organisation" search.
 * Thresholds fail the run when p95 of the directory requests reaches 300 ms or any request fails.
 */
import http from "k6/http";
import { check, fail, sleep } from "k6";
import exec from "k6/execution";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = __ENV.EMAIL || "seed-admin@numo9.test";
const PASSWORD = __ENV.PASSWORD || "";
const PRACTICE = __ENV.PRACTICE_ID || "";
// Think time between two requests of one user, in seconds ("min-max"): reading the results,
// typing the next search (the search box itself waits 150 ms after the last key). THINK=0 sends
// requests back to back (a saturation test, not the acceptance scenario).
const [THINK_MIN, THINK_MAX] = (__ENV.THINK || "0.5-2").split("-").map(Number);

export const options = {
  // Keep each virtual user's session cookie between iterations (it signs in once).
  noCookiesReset: true,
  scenarios: {
    directory: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 30),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:directory}": ["p(95)<300"],
    "checks{endpoint:directory}": ["rate==1"],
    http_req_failed: ["rate==0"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

const WORDS = ["maple", "erable", "érable", "bakery", "quebec", "cedar", "lev", "dental", "supply"];
const BN_FRAGMENTS = ["123 4", "45 67", "9 1", "800 5", "34 56 7"];
const FILTERS = [
  "province=ON&status=paid",
  "province=QC&province=NB",
  "status=trial&sort=trial_ends",
  "payroll=yes&fye=12",
  "overdue=yes&sort=-overdue",
  "gst_cycle=monthly&unfiled=yes",
  "archived=include&status=archived",
];

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

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

function directory(query, name) {
  const practice = PRACTICE ? `practice=${PRACTICE}&` : "";
  const response = http.get(`${BASE_URL}/api/v1/practice/orgs?${practice}${query}`, {
    headers: { Accept: "application/json" },
    tags: { endpoint: "directory", request: name },
  });
  check(response, { [`${name}: 200`]: (r) => r.status === 200 }, { endpoint: "directory" });
  return response;
}

export function setup() {
  if (!PASSWORD) fail("Set PASSWORD (the seeded admin's password, seed_practice --password).");
  return {};
}

export default function () {
  if (!signedIn) signIn();
  const roll = exec.scenario.iterationInTest % 20;
  if (roll === 0) {
    directory("page_size=2000&facets=1", "full list (virtualised grid)");
  } else if (roll < 4) {
    directory("page_size=50", "first page + facets");
  } else if (roll < 10) {
    directory(`q=${encodeURIComponent(pick(WORDS))}&page_size=50`, "word search");
  } else if (roll < 13) {
    directory(`q=${encodeURIComponent(pick(BN_FRAGMENTS))}&page_size=50`, "BN search");
  } else if (roll < 17) {
    directory(`${pick(FILTERS)}&page_size=50`, "filters");
  } else {
    directory(
      `q=${encodeURIComponent(pick(WORDS))}&page_size=8&facets=0&columns=bn,province,status`,
      "go to organisation",
    );
  }
  if (THINK_MAX > 0) sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
  else if (THINK_MIN > 0) sleep(THINK_MIN);
}
