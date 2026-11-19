/**
 * S-06-T09 — k6 baseline of the contacts list (B-01-T11 API): p95 < 300 ms.
 *
 *   python backend/manage.py make_fixture_practice --orgs 2000 --lines 200 \
 *          --password "$FIXTURE_PASSWORD" --scratch
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 -e PASSWORD="$FIXTURE_PASSWORD" \
 *          --summary-export docs/perf/baselines/<date>/contacts-list.json tools/perf/k6/contacts-list.js
 *
 * 20 accountants (VUS) open clients' contact lists at once: the first page, a role tab, a name
 * search, the archived view. Each picks a random organisation of the practice per request.
 */
import http from "k6/http";
import { check, sleep } from "k6";

import { BASE_URL, organisations, pick, requirePassword, signIn } from "./lib/session.js";

const [THINK_MIN, THINK_MAX] = (__ENV.THINK || "0.5-2").split("-").map(Number);

export const options = {
  noCookiesReset: true,
  scenarios: {
    contacts: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 20),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:contacts}": ["p(95)<300"],
    "checks{endpoint:contacts}": ["rate==1"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

const QUERIES = [
  "limit=50",
  "role=customer&limit=50",
  "role=supplier&limit=50",
  "q=maple&limit=50",
  "status=archived&limit=50",
];

export function setup() {
  requirePassword();
  signIn();
  return { orgs: organisations() };
}

let signedIn = false;

export default function (data) {
  if (!signedIn) {
    signIn();
    signedIn = true;
  }
  const query = pick(QUERIES);
  const response = http.get(`${BASE_URL}/api/v1/o/${pick(data.orgs)}/contacts?${query}`, {
    headers: { Accept: "application/json" },
    tags: { endpoint: "contacts", request: query.split("&")[0] },
  });
  check(response, { "contacts: 200": (r) => r.status === 200 }, { endpoint: "contacts" });
  if (THINK_MAX > 0) sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
}
