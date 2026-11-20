/**
 * A-09-T10 — k6 benchmark of the search API: p95 < 150 ms over 1,000,000 documents.
 *
 *   python backend/manage.py seed_search --docs 1000000 --password "$SEED_PASSWORD"
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 -e PASSWORD="$SEED_PASSWORD" tools/perf/k6/search.js
 *
 * Load: 5 people (VUS) searching the seeded organisation, each pausing 0.5–1.5 s (THINK) between
 * queries — about 300 searches a minute, under the organisation's default rate limit (600/min,
 * S-06-T05). The queries are the palette's kinds: names and prefixes, accents, codes, journal
 * numbers, amounts, typos, words matching a large share of the index and nothing at all.
 * Thresholds fail the run when p95 reaches 150 ms or any request fails.
 */
import http from "k6/http";
import { check, fail, sleep } from "k6";
import exec from "k6/execution";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const EMAIL = __ENV.EMAIL || "seed-search@numo9.test";
const PASSWORD = __ENV.PASSWORD || "";
const ORG_NAME = "Search Seed Bakery Inc.";
const [THINK_MIN, THINK_MAX] = (__ENV.THINK || "0.5-1.5").split("-").map(Number);

export const QUERIES = [
  "maple",
  "cedar roo",
  "érable",
  "erable renov",
  "MJ-0004242",
  "MJ-00042",
  "5400",
  "54",
  "1,130",
  "$2,500.00",
  "pinecrst",
  "rent",
  "year-end",
  "ma",
  "patel dental",
  "gatineau café",
  "invoice.pdf",
  "nguyen",
  "accrual",
  "zzzz",
];

export const options = {
  noCookiesReset: true,
  scenarios: {
    search: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:search}": ["p(95)<150"],
    "checks{endpoint:search}": ["rate==1"],
    http_req_failed: ["rate==0"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

let organisation = "";

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
  if (!found) fail(`${ORG_NAME} not found: run seed_search first.`);
  organisation = found.id;
}

export function setup() {
  if (!PASSWORD) fail("Set PASSWORD (the seeded owner's password, seed_search --password).");
  return {};
}

export default function () {
  if (!organisation) signIn();
  const q = QUERIES[exec.scenario.iterationInTest % QUERIES.length];
  const response = http.get(
    `${BASE_URL}/api/v1/o/${organisation}/search?q=${encodeURIComponent(q)}`,
    { headers: { Accept: "application/json" }, tags: { endpoint: "search" } },
  );
  check(
    response,
    {
      "search: 200": (r) => r.status === 200,
      "search: grouped answer": (r) => Array.isArray(r.json("records")),
    },
    { endpoint: "search" },
  );
  sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
}
