/**
 * S-06-T09 — k6 baseline of posting a journal: p95 < 500 ms, no failed posting.
 *
 * Posts through the perf-only endpoint (numo9/scale/api.py: the real post_journal service —
 * validation, period lock, gap-free numbering, audit), on only where NUMO9_PERF_ENDPOINTS=1.
 * Phase 1's manual-journal API replaces the URL here; the scenario and thresholds stay.
 *
 *   NUMO9_PERF_ENDPOINTS=1 gunicorn numo9.wsgi …
 *   k6 run -e BASE_URL=http://127.0.0.1:8000 -e PASSWORD="$FIXTURE_PASSWORD" \
 *          --summary-export docs/perf/baselines/<date>/post-journal.json tools/perf/k6/post-journal.js
 *
 * 10 bookkeepers post at once, spread over the practice's organisations; HOT=1 sends every
 * posting to one organisation instead (contention on its journal number sequence).
 */
import http from "k6/http";
import { check, sleep } from "k6";

import {
  BASE_URL,
  organisations,
  pick,
  requirePassword,
  signIn,
  writeHeaders,
} from "./lib/session.js";

const [THINK_MIN, THINK_MAX] = (__ENV.THINK || "0.2-1").split("-").map(Number);
const HOT = __ENV.HOT === "1";

export const options = {
  noCookiesReset: true,
  scenarios: {
    post: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || "60s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:post_journal}": ["p(95)<500"],
    "checks{endpoint:post_journal}": ["rate==1"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export function setup() {
  requirePassword();
  signIn();
  const orgs = organisations();
  return { orgs: HOT ? orgs.slice(0, 1) : orgs };
}

let signedIn = false;

export default function (data) {
  if (!signedIn) {
    signIn();
    signedIn = true;
  }
  const amount = (1 + Math.floor(Math.random() * 99999) / 100).toFixed(2);
  const response = http.post(
    `${BASE_URL}/api/v1/o/${pick(data.orgs)}/perf/journal`,
    JSON.stringify({ amount }),
    { headers: writeHeaders(), tags: { endpoint: "post_journal" } },
  );
  check(response, { "post journal: 201": (r) => r.status === 201 }, { endpoint: "post_journal" });
  if (THINK_MAX > 0) sleep(THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN));
}
